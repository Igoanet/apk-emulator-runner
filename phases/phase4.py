"""Phase 4: MT Manager VIP (Android — 30 Functions)."""
import os
from config import TEMP_DIR
from utils.logger import setup_logger
from utils.adb_helper import adb_push, adb_trigger_tasker, adb_wait_for_file, adb_pull

logger = setup_logger()

# 30 MT Manager functions:
# Core Obfuscation (5): F1-F5
# DEX Manipulation (5): F6-F10
# Resource & XML (6): F11-F16
# Signature & Verification (6): F17-F22
# Injection (3): F23-F25
# Comparison & Repair (4): F26-F29
# Custom Keys (1): F30

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 4: MT Manager VIP (30 Functions)")
    logger.info("="*60)

    remote_input = "/sdcard/input_mt.apk"
    ok, _, err = adb_push(input_apk, remote_input, timeout=120)
    if not ok:
        logger.warning(f"[!] Phase 4 skip — no Android device: {err}")
        return input_apk

    logger.info("[*] Triggering MT Manager (30 functions) via Tasker...")
    adb_trigger_tasker("MT_MANAGER_AUTOMATION")

    logger.info("[*] MT Manager automation running on Android device...")
    logger.info("    ═════════════════════════════════════════════════")
    logger.info("    F1: Sign APK")
    logger.info("    F2: Clone APK")
    logger.info("    F3: Optimize APK")
    logger.info("    F4: Dex Redivision")
    logger.info("    F5: Dex Anti-Confusion")
    logger.info("    F6: Decrypt Dex Strings")
    logger.info("    F7: Resources Confusion")
    logger.info("    F8: Resources Anti-Confusion")
    logger.info("    F9: Resources Minification")
    logger.info("    F10: Xml Batch Replacement")
    logger.info("    F11: Xml Translation Mode")
    logger.info("    F12: Kill Signature Verification")
    logger.info("    F13: APK Data Multiplexing")
    logger.info("    F14: Inject Documents Provider")
    logger.info("    F15: Inject Logging")
    logger.info("    F16: Full AXml Editing")
    logger.info("    F17: AXml Code Search/Replace")
    logger.info("    F18: Smali-to-Java Conversion")
    logger.info("    F19: Arsc Editor++")
    logger.info("    F20: Arsc Resource Search")
    logger.info("    F21: Dex Editor++ Flowcharts")
    logger.info("    F22: Dex Repair")
    logger.info("    F23: Dex De-obfuscation")
    logger.info("    F24: Dex Comparison")
    logger.info("    F25: Arsc Comparison")
    logger.info("    F26: Text Comparison")
    logger.info("    F27: Hex Editor (Save)")
    logger.info("    F28: Remove APK Signature Verification")
    logger.info("    F29: Convert APKS/XAPK to APK")
    logger.info("    F30: Custom APK Signing Keys")
    logger.info("    ═════════════════════════════════════════════════")
    logger.info("    Waiting for MT Manager to complete...")

    remote_output = "/sdcard/mt_output.apk"
    found = adb_wait_for_file(remote_output, poll_interval=60, max_wait=900)
    if not found:
        logger.warning("[!] Phase 4 skip — MT Manager output timeout")
        return input_apk

    local_output = str(TEMP_DIR / "mt_cleaned.apk")
    ok, _, err = adb_pull(remote_output, local_output, timeout=120)
    if not ok:
        logger.warning(f"[!] Phase 4 skip — pull failed: {err}")
        return input_apk
    if not os.path.exists(local_output) or os.path.getsize(local_output) == 0:
        logger.warning("[!] Phase 4 skip — pulled file empty")
        return input_apk

    logger.info(f"[+] Phase 4 Complete: {local_output}")
    return local_output
