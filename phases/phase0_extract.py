"""Phase 0: Extract Payload Properties (PC) — aapt dump badging."""
import os, subprocess, re
from config import AAPT
from utils.logger import setup_logger

logger = setup_logger()


def run(input_apk):
    """Extract package name, app label, icon path. Save as base_info dict."""
    logger.info("=" * 60)
    logger.info("[*] PHASE 0: Extract Payload Properties")
    logger.info("=" * 60)

    info = {"apk_path": input_apk, "name": None, "label": None, "icon": None}

    # aapt dump badging
    r = subprocess.run([AAPT, "d", "badging", input_apk],
                       capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        for line in r.stdout.split("\n"):
            if line.startswith("package:"):
                m = re.search(r"name='([^']+)'", line)
                if m:
                    info["name"] = m.group(1)
                m = re.search(r"versionCode='(\d+)'", line)
                if m:
                    info["versionCode"] = m.group(1)
            if line.startswith("application-label:"):
                m = re.search(r"application-label:'(.+)'", line)
                if m:
                    info["label"] = m.group(1)
            if line.startswith("application-icon-"):
                m = re.search(r"application-icon-\d+:'(.+)'", line)
                if m:
                    info["icon"] = m.group(1)
            if line.startswith("sdkVersion:"):
                m = re.search(r"sdkVersion:'(\d+)'", line)
                if m:
                    info["minSdk"] = m.group(1)
            if line.startswith("targetSdkVersion:"):
                m = re.search(r"targetSdkVersion:'(\d+)'", line)
                if m:
                    info["targetSdk"] = m.group(1)

    logger.info(f"[+] Package: {info.get('name')}")
    logger.info(f"[+] Label: {info.get('label')}")
    logger.info(f"[+] Min SDK: {info.get('minSdk')}")
    logger.info(f"[+] Target SDK: {info.get('targetSdk')}")
    logger.info("[+] Phase 0 Complete")
    return info
