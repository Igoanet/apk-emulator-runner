#!/bin/bash
set -e

echo "========================================"
echo "APK FUD Pipeline v20 - Full Tool Chain"
echo "========================================"

# Wait for ADB device
adb wait-for-device
echo "=== Device Connected ==="
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release

# Create work directories
mkdir -p ~/fud-work/input ~/fud-work/output ~/fud-work/screenshots ~/apk-tools

# Download APK Tools from VPS if available
VPS_HOST="${VPS_HOST:-13.60.208.8}"
echo "=== Downloading APK Tools from VPS ==="

# Try to download tools from VPS
curl -s "http://${VPS_HOST}/input/np_manager.apk" -o ~/apk-tools/np_manager.apk 2>/dev/null || echo "NP Manager not available on VPS"
curl -s "http://${VPS_HOST}/input/mt_manager.apk" -o ~/apk-tools/mt_manager.apk 2>/dev/null || echo "MT Manager not available on VPS"
curl -s "http://${VPS_HOST}/input/apktool_m.apk" -o ~/apk-tools/apktool_m.apk 2>/dev/null || echo "APKTool M not available on VPS"

# Check local attached_assets if VPS download failed
if [ ! -f ~/apk-tools/np_manager.apk ] && [ -f attached_assets/NP_Manager_*.apk ]; then
  cp attached_assets/NP_Manager_*.apk ~/apk-tools/np_manager.apk
fi

ls -lh ~/apk-tools/

# Download input APK
echo "=== Download Input APK ==="
APK_URL="${APK_URL:-}"
if echo "$APK_URL" | grep -q "^http"; then
  wget -q "$APK_URL" -O ~/fud-work/input/base.apk && echo "Downloaded $(stat -c%s ~/fud-work/input/base.apk) bytes" || echo "wget failed"
else
  echo "No APK URL provided"
fi
test -s ~/fud-work/input/base.apk || { echo "APK empty"; exit 1; }

# Run full pipeline
echo "=== Running Full Pipeline ==="
export NP_APK="${NP_APK:-$HOME/apk-tools/np_manager.apk}"
export INPUT_APK="$HOME/fud-work/input/base.apk"
export OUTPUT_DIR="$HOME/fud-work/output"
export SCREENSHOT_DIR="$HOME/fud-work/screenshots"
export NP_MANAGER_EMAIL
export NP_MANAGER_PASS
python3 scripts/np_manager_auto.py || echo "Pipeline completed with errors"

# List outputs
echo "=== Output Files ==="
ls -lh ~/fud-work/output/ || echo "No output"

echo "=== Done ==="
