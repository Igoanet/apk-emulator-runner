"""Phase 2: NP Manager Premium (Android — 39 Functions)."""
import os, time
from config import TEMP_DIR
from utils.logger import setup_logger
from utils.adb_helper import adb_push, adb_trigger_tasker, adb_wait_for_file, adb_pull

logger = setup_logger()

# 39 NP Manager functions grouped by category:
# DEX Obfuscation (9): F1-F9
# DEX Manipulation (4): F10-F13
# Package & Identity (4): F14-F17
# Resource Obfuscation (6): F18-F23
# Signing & Signature (5): F24-F28
# Hardening & Protection (6): F29-F34
# Injection & Editing (4): F35-F38
# Extras (1): F39

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 2: NP Manager Premium (39 Functions)")
    logger.info("="*60)

    # Push to device
    remote_input = "/sdcard/input_payload.apk"
    ok, _, err = adb_push(input_apk, remote_input, timeout=120)
    if not ok:
        logger.warning(f"[!] Phase 2 skip — no Android device: {err}")
        return input_apk

    logger.info("[*] Triggering NP Manager (39 functions) via Tasker...")
    adb_trigger_tasker("NP_MANAGER_AUTOMATION")

    logger.info("[*] NP Manager automation running on Android device...")
    logger.info("    ═════════════════════════════════════════════════")
    logger.info("    F1: DEX Obfuscation Dictionary Extraction")
    logger.info("    F2: Against DEX Confusion")
    logger.info("    F3: Change Package/Class Name")
    logger.info("    F4: DEX Split")
    logger.info("    F5: Add Crash Log")
    logger.info("    F6: DEX Merge")
    logger.info("    F7: One-Click Randomly Sign APK")
    logger.info("    F8: One-Click Injection Function")
    logger.info("    F9: View Signature")
    logger.info("    F10: Injection Signature Verification")
    logger.info("    F11: APK Cloner")
    logger.info("    F12: Super Obfuscation")
    logger.info("    F13: Sign APK")
    logger.info("    F14: Obfuscate APK")
    logger.info("    F15: Control Flow Obfuscation")
    logger.info("    F16: APK VM Protection")
    logger.info("    F17: DEX String Decryption")
    logger.info("    F18: RES Confusion 3.0")
    logger.info("    F19: Test Signature Check Strength")
    logger.info("    F20: RES Anti-Resource Obfuscation")
    logger.info("    F21: APK Pseudo-Encryption")
    logger.info("    F22: Anti-APK Pseudo-Encryption")
    logger.info("    F23: General Editor")
    logger.info("    F24: XML Translation Schema")
    logger.info("    F25: APK DEX2C")
    logger.info("    F26: APK DEX2C Pro")
    logger.info("    F27: Modify File Time in APK")
    logger.info("    F28: APK Function Extracts Shell")
    logger.info("    F29: APK Alignment Optimization")
    logger.info("    F30: Encrypt Resource Files")
    logger.info("    F31: Encrypt Asset File Contents")
    logger.info("    F32: One-Click App Protection")
    logger.info("    F33: Data Reuse Optimization")
    logger.info("    F34: Remove Debugging Information")
    logger.info("    F35: APK Encrypt Strings")
    logger.info("    F36: Random SourceFile Name")
    logger.info("    F37: Set Entry by Old APK")
    logger.info("    F38: Decompile XML Under RES")
    logger.info("    F39: XML Translation Schema (second pass)")
    logger.info("    ═════════════════════════════════════════════════")
    logger.info("    Waiting for NP Manager to complete...")

    # Poll for output (25 min max)
    remote_output = "/sdcard/final_output.apk"
    found = adb_wait_for_file(remote_output, poll_interval=60, max_wait=1800)
    if not found:
        logger.warning("[!] Phase 2 skip — NP Manager output timeout")
        return input_apk

    local_output = str(TEMP_DIR / "protected_payload.apk")
    ok, _, err = adb_pull(remote_output, local_output, timeout=120)
    if not ok:
        logger.warning(f"[!] Phase 2 skip — pull failed: {err}")
        return input_apk
    if not os.path.exists(local_output) or os.path.getsize(local_output) == 0:
        logger.warning("[!] Phase 2 skip — pulled file empty")
        return input_apk

    logger.info(f"[+] Phase 2 Complete: {local_output}")
    return local_output
