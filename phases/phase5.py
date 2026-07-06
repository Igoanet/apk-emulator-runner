"""Phase 5: APKTool M Final Rebuild (PC)."""
import os, subprocess, shutil
from config import TEMP_DIR, APKTOOL
from utils.logger import setup_logger

logger = setup_logger()

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 5: APKTool M Final Rebuild")
    logger.info("="*60)

    decompiled = str(TEMP_DIR / "phase5_decompiled")
    logger.info("[*] Decompiling...")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, input_apk],
                      capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"apktool d failed: {r.stderr[:500]}")

    # Remove synthetic res/ dir to prevent build errors with "false" layout values
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # Fix any errors
    # (already handled in phase3 logic, but re-apply if needed)

    rebuilt = str(TEMP_DIR / "final_rebuilt.apk")
    logger.info("[*] Rebuilding...")
    r = subprocess.run([APKTOOL, "b", "-o", rebuilt, decompiled],
                      capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        r = subprocess.run([APKTOOL, "b", "--use-aapt2", "-o", rebuilt, decompiled],
                          capture_output=True, text=True, timeout=120)
    # validate output exists and has content
    if not os.path.exists(rebuilt) or os.path.getsize(rebuilt) == 0:
        raise Exception(f"apktool b failed: {r.stderr[:500]}")

    shutil.rmtree(decompiled, ignore_errors=True)
    logger.info(f"[+] Phase 5 Complete: {rebuilt}")
    return rebuilt
