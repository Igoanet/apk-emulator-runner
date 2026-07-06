#!/bin/bash
set -e

echo "========================================"
echo "NP Manager Pipeline Script"
echo "APK_URL: $APK_URL"
echo "NP_APK: $NP_APK"
echo "EMAIL: $NP_MANAGER_EMAIL"
echo "========================================"

adb wait-for-device
echo "=== Device Info ==="
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release

echo "=== Installing APK Tools ==="
NP_APK="${NP_APK:-$HOME/apk-tools/np_manager.apk}"
test -f "$NP_APK" && adb install -r -d "$NP_APK" && echo "NP Manager installed" || echo "NP Manager not found"
test -f ~/apk-tools/mt_manager.apk && adb install -r -d ~/apk-tools/mt_manager.apk && echo "MT Manager installed" || echo "MT Manager not found"
test -f ~/apk-tools/apktool_m.apk && adb install -r -d ~/apk-tools/apktool_m.apk && echo "APKTool M installed" || echo "APKTool M not found"

echo "=== Download Input APK ==="
mkdir -p ~/fud-work/input ~/fud-work/output ~/fud-work/screenshots
APK_URL="${APK_URL:-}"
if echo "$APK_URL" | grep -q "^http"; then
  wget -q "$APK_URL" -O ~/fud-work/input/base.apk && echo "Downloaded $(stat -c%s ~/fud-work/input/base.apk) bytes" || echo "wget failed"
else
  echo "No valid APK URL provided"
  touch ~/fud-work/input/base.apk
fi
test -s ~/fud-work/input/base.apk || { echo "APK empty"; touch ~/fud-work/input/base.apk; }
ls -lh ~/fud-work/input/

echo "=== Run NP Manager Automation ==="
export NP_APK
export INPUT_APK="$HOME/fud-work/input/base.apk"
export OUTPUT_DIR="$HOME/fud-work/output"
export APK_URL
export SCREENSHOT_DIR="$HOME/fud-work/screenshots"
export NP_MANAGER_EMAIL
export NP_MANAGER_PASS
python3 github_automation/np_manager_auto.py || echo "Automation failed"
ls -lh ~/fud-work/output/

echo "=== Pull Screenshots ==="
adb pull /sdcard/screenshots/ ~/fud-work/screenshots/ 2>/dev/null || echo "No screenshots on device"
ls -lh ~/fud-work/screenshots/ 2>/dev/null || echo "No local screenshots"

echo "=== Done ==="
