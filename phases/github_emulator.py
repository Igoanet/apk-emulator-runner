"""GitHub Emulator Bridge — Phase 4 (fully private, no public server).

Architecture (zero public ports):
  1. Create a private draft GitHub release in the target repo
  2. Upload input APK + tool APKs as release assets
  3. Trigger repository_dispatch with asset IDs (not URLs)
  4. GitHub Actions downloads assets using its built-in GITHUB_TOKEN
  5. Workflow uploads output as a GitHub Actions artifact
  6. This process polls run status via GitHub API and downloads the artifact
  7. Draft release is deleted when done

Requires: GITHUB_EMULATOR_PAT (repo + workflow scopes)
"""
import os, time, json, zipfile, io
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger()

GITHUB_TOKEN  = os.environ.get("GITHUB_EMULATOR_PAT", "")
REPO          = "Igoanet/apk-emulator-runner"
WORKFLOW_FILE = "emulator-runner-v3.yml"
_BASE         = "https://api.github.com"
_POLL         = 30          # seconds between status polls
_MAX_WAIT     = 50 * 60     # 50 minute hard timeout


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _hdrs(accept="application/vnd.github.v3+json"):
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": accept,
        "User-Agent": "apk-fud-bot/8",
    }


def _req(method, path, body=None):
    import requests
    url = f"{_BASE}{path}"
    kw = dict(headers=_hdrs(), timeout=60)
    if body is not None:
        kw["json"] = body
    r = requests.request(method, url, **kw)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


def _upload_asset(upload_url_template: str, filename: str, data: bytes) -> dict:
    import requests
    url = upload_url_template.split("{")[0] + f"?name={filename}"
    r = requests.post(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/octet-stream",
        "User-Agent": "apk-fud-bot/8",
    }, data=data, timeout=300)
    r.raise_for_status()
    return r.json()


def _download_artifact(archive_url: str) -> bytes:
    """Download artifact archive — follows GitHub's redirect to S3."""
    import requests
    r = requests.get(archive_url, headers=_hdrs(), allow_redirects=True, timeout=180)
    r.raise_for_status()
    return r.content


# ── Main entry point ──────────────────────────────────────────────────────────

def trigger_and_wait(embedded_apk: str, output_apk: str) -> bool:
    """
    Upload APK → trigger GitHub Actions → wait → download result.
    Returns True on success, False on failure/timeout.
    """
    if not GITHUB_TOKEN:
        logger.error("[GH-EMU] GITHUB_EMULATOR_PAT not set — cannot run emulator phase")
        return False

    if not os.path.exists(embedded_apk):
        logger.error(f"[GH-EMU] Input APK not found: {embedded_apk}")
        return False

    from config import NP_MANAGER_APK, MT_MANAGER_APK, APKTOOL_M_APK

    apk_bytes = Path(embedded_apk).read_bytes()
    filename  = os.path.basename(embedded_apk)
    size_mb   = len(apk_bytes) / 1024 / 1024
    logger.info(f"[GH-EMU] Input: {filename} ({size_mb:.1f} MB)")

    release_id  = None
    tag         = f"run-{int(time.time())}"

    try:
        # ── 1. Create private draft release ──────────────────────────────────
        st, rel = _req("POST", f"/repos/{REPO}/releases", {
            "tag_name": tag,
            "name": f"Pipeline {tag}",
            "draft": True,
            "prerelease": True,
        })
        if st not in (200, 201):
            logger.error(f"[GH-EMU] Release create failed ({st}): {rel}")
            return False
        release_id  = rel["id"]
        upload_url  = rel["upload_url"]
        logger.info(f"[GH-EMU] Draft release created (id={release_id}, tag={tag})")

        # ── 2. Upload input APK ───────────────────────────────────────────────
        logger.info("[GH-EMU] Uploading input APK...")
        a = _upload_asset(upload_url, filename, apk_bytes)
        apk_asset_id = a["id"]
        logger.info(f"[GH-EMU] Input APK → asset_id={apk_asset_id}")

        # ── 3. Upload tool APKs ───────────────────────────────────────────────
        tool_ids: dict[str, str] = {}
        for tool_name, tool_path in [
            ("np_manager.apk",  str(NP_MANAGER_APK)),
            ("mt_manager.apk",  str(MT_MANAGER_APK)),
            ("apktool_m.apk",   str(APKTOOL_M_APK)),
        ]:
            if os.path.exists(tool_path):
                sz = os.path.getsize(tool_path)
                logger.info(f"[GH-EMU] Uploading {tool_name} ({sz/1024/1024:.1f} MB)...")
                tb = Path(tool_path).read_bytes()
                ta = _upload_asset(upload_url, tool_name, tb)
                tool_ids[tool_name] = str(ta["id"])
                logger.info(f"[GH-EMU] {tool_name} → asset_id={ta['id']}")
            else:
                logger.warning(f"[GH-EMU] {tool_name} not found — stage will be skipped")

        # ── 4. Trigger workflow ───────────────────────────────────────────────
        trigger_time = time.time()
        dispatch_payload = {
            "event_type": "run-fud-pipeline",
            "client_payload": {
                "run_id":             tag,
                "repo":               REPO,
                "apk_asset_id":       str(apk_asset_id),
                "np_asset_id":        tool_ids.get("np_manager.apk",  ""),
                "mt_asset_id":        tool_ids.get("mt_manager.apk",  ""),
                "apktoolm_asset_id":  tool_ids.get("apktool_m.apk",   ""),
                "np_manager_email":   os.environ.get("NP_MANAGER_EMAIL", ""),
                "np_manager_pass":    os.environ.get("NP_MANAGER_PASS",  ""),
            },
        }
        st, _ = _req("POST", f"/repos/{REPO}/dispatches", dispatch_payload)
        if st not in (200, 201, 204):
            logger.error(f"[GH-EMU] Dispatch failed ({st})")
            return False
        logger.info("[GH-EMU] Workflow dispatched — waiting for run to appear...")

        # ── 5. Find the new workflow run ──────────────────────────────────────
        run_id = None
        for attempt in range(24):           # up to ~2 min
            time.sleep(5)
            st, runs_data = _req("GET",
                f"/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}"
                f"/runs?per_page=5&event=repository_dispatch")
            if st == 200:
                for run in runs_data.get("workflow_runs", []):
                    ca = run.get("created_at", "")
                    try:
                        run_ts = time.mktime(time.strptime(ca, "%Y-%m-%dT%H:%M:%SZ"))
                    except Exception:
                        run_ts = 0
                    if run_ts >= trigger_time - 60:
                        run_id = run["id"]
                        break
            if run_id:
                break

        if not run_id:
            logger.error("[GH-EMU] Could not locate workflow run after 2 minutes")
            return False
        logger.info(f"[GH-EMU] Workflow run ID: {run_id}")

        # ── 6. Poll until complete ────────────────────────────────────────────
        started = time.time()
        while time.time() - started < _MAX_WAIT:
            time.sleep(_POLL)
            st, run = _req("GET", f"/repos/{REPO}/actions/runs/{run_id}")
            if st != 200:
                logger.warning(f"[GH-EMU] Poll failed ({st}), retrying...")
                continue
            status     = run.get("status",     "unknown")
            conclusion = run.get("conclusion", "")
            elapsed    = int(time.time() - started)
            logger.info(f"[GH-EMU] [{elapsed}s] {status} / {conclusion or '...'}")
            if status == "completed":
                if conclusion != "success":
                    logger.error(f"[GH-EMU] Workflow ended: {conclusion}")
                    return False
                break
        else:
            logger.error(f"[GH-EMU] Timed out after {_MAX_WAIT // 60} min")
            return False

        # ── 7. Download output artifact ───────────────────────────────────────
        logger.info("[GH-EMU] Fetching artifact list...")
        st, arts = _req("GET", f"/repos/{REPO}/actions/runs/{run_id}/artifacts")
        if st != 200:
            logger.error(f"[GH-EMU] Failed to list artifacts ({st})")
            return False

        art = None
        for a in arts.get("artifacts", []):
            if a.get("name", "").startswith("fud-pipeline-output"):
                art = a
                break

        if not art:
            logger.error("[GH-EMU] fud-pipeline-output artifact not found")
            return False

        logger.info(f"[GH-EMU] Downloading artifact: {art['name']} ({art.get('size_in_bytes',0)//1024} KB)")
        zip_bytes = _download_artifact(art["archive_download_url"])

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            apk_files = [n for n in z.namelist() if n.endswith(".apk")]
            if not apk_files:
                logger.error("[GH-EMU] No APK in artifact zip")
                return False
            chosen = next((n for n in apk_files if "hardened" in n), apk_files[0])
            with z.open(chosen) as f:
                Path(output_apk).write_bytes(f.read())

        sz = Path(output_apk).stat().st_size
        logger.info(f"[GH-EMU] ✓ Output: {output_apk} ({sz:,} bytes)")
        return True

    except Exception as exc:
        logger.error(f"[GH-EMU] Unexpected error: {exc}")
        import traceback
        logger.error(traceback.format_exc())
        return False

    finally:
        # Always delete the draft release to keep the repo clean
        if release_id:
            try:
                _req("DELETE", f"/repos/{REPO}/releases/{release_id}")
                logger.info(f"[GH-EMU] Draft release {release_id} deleted")
            except Exception:
                pass
