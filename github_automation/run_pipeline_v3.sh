#!/usr/bin/env bash
# run_pipeline_v3.sh — Android hardening pipeline (private, no public server)
#
# Uses `gh api` (GitHub CLI) to download private release assets — this is the
# ONLY reliable method on GitHub Actions runners for private repo assets.
# GITHUB_TOKEN is auto-configured for `gh` on every GitHub Actions runner.

set -euo pipefail

# Fallback in case GITHUB_ENV didn't populate REPO
REPO="${REPO:-Igoanet/apk-emulator-runner}"

WORK_DIR="$HOME/fud-work"
APK_DIR="$WORK_DIR/apks"
TOOL_DIR="$HOME/apk-tools"
OUTPUT_DIR="$WORK_DIR/output"
SCREENSHOT_DIR="$WORK_DIR/screenshots"
LOG_DIR="$WORK_DIR/logs"

mkdir -p "$APK_DIR" "$TOOL_DIR" "$OUTPUT_DIR" "$SCREENSHOT_DIR" "$LOG_DIR"

# ─── Logging ──────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_DIR/pipeline.log"; }
step() { echo; log "═══ $* ═══"; }
ok()   { log "✓ $*"; }
warn() { log "⚠ $*"; }
fail() { log "✗ $*"; }

# ─── Debug: show key env vars ─────────────────────────────────────────────────
log "ENV: REPO=${REPO:-UNSET}"
log "ENV: RUN_ID=${RUN_ID:-UNSET}"
log "ENV: APK_ASSET_ID=${APK_ASSET_ID:-UNSET}"
log "ENV: NP_ASSET_ID=${NP_ASSET_ID:-UNSET}"
log "ENV: MT_ASSET_ID=${MT_ASSET_ID:-UNSET}"
log "ENV: APKTOOLM_ASSET_ID=${APKTOOLM_ASSET_ID:-UNSET}"
log "ENV: GITHUB_TOKEN set=$([ -n "${GITHUB_TOKEN:-}" ] && echo yes || echo NO)"

# ─── Cleanup helpers ──────────────────────────────────────────────────────────
cleanup_emulator_storage() {
    log "[CLEANUP] Wiping emulator sdcard..."
    adb shell "rm -rf /sdcard/NP_Manager /sdcard/Download/input.apk" 2>/dev/null || true
    adb shell "rm -rf /sdcard/MT_Manager /sdcard/fud_work" 2>/dev/null || true
}

cleanup_local_work() {
    log "[CLEANUP] Removing local staging files..."
    rm -rf "$TOOL_DIR" "$APK_DIR" || true
}

trap 'cleanup_emulator_storage; cleanup_local_work' EXIT

# ─── Download a private GitHub release asset via gh CLI ───────────────────────
# gh CLI is pre-installed on all GitHub Actions runners and auto-uses GITHUB_TOKEN.
download_github_asset() {
    local asset_id="$1" dest="$2" label="$3"
    if [[ -z "$asset_id" ]]; then
        warn "${label}: no asset ID provided — skipping"
        return 1
    fi
    log "Downloading ${label} (asset_id=${asset_id}, repo=${REPO:-UNSET})..."
    local API_PATH="/repos/${REPO}/releases/assets/${asset_id}"

    for attempt in 1 2 3; do
        if gh api \
            --header "Accept: application/octet-stream" \
            "$API_PATH" \
            > "$dest" 2>>"$LOG_DIR/curl.log"; then
            local size
            size=$(stat -c%s "$dest" 2>/dev/null || echo 0)
            if [[ $size -gt 1000 ]]; then
                ok "${label} ready (${size} bytes)"
                return 0
            else
                warn "${label}: downloaded but file too small (${size} bytes) — may be error JSON"
                cat "$dest" >> "$LOG_DIR/curl.log" 2>/dev/null || true
                rm -f "$dest"
            fi
        fi
        warn "${label} download failed (attempt ${attempt}/3)"
        sleep 5
    done
    return 1
}

# ─── Wait for emulator boot ───────────────────────────────────────────────────
step "Waiting for emulator to boot"
for i in $(seq 1 60); do
    BOOT=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || echo "0")
    if [[ "$BOOT" == "1" ]]; then ok "Emulator booted"; break; fi
    sleep 5
    [[ $((i % 6)) -eq 0 ]] && log "  Waiting... ${i}/60"
done

adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard           || true
adb shell input keyevent KEYCODE_HOME   || true
sleep 2

# ─── Download input APK ───────────────────────────────────────────────────────
step "Downloading input APK"
INPUT_APK="$APK_DIR/input.apk"

if ! download_github_asset "${APK_ASSET_ID:-}" "$INPUT_APK" "input APK"; then
    fail "Cannot download input APK — aborting"
    exit 1
fi
log "Input APK: $(stat -c%s "$INPUT_APK") bytes"

# ─── Download tool APKs ───────────────────────────────────────────────────────
step "Downloading tool APKs"

NP_APK="$TOOL_DIR/np_manager.apk"
if ! download_github_asset "${NP_ASSET_ID:-}" "$NP_APK" "NP Manager APK"; then
    warn "NP Manager APK unavailable — Phase 1 (NP) will be skipped"
    NP_APK=""
fi

MT_APK="$TOOL_DIR/mt_manager.apk"
if ! download_github_asset "${MT_ASSET_ID:-}" "$MT_APK" "MT Manager APK"; then
    warn "MT Manager APK unavailable — Phase 2 (MT) will be skipped"
    MT_APK=""
fi

ATOOLM_APK="$TOOL_DIR/apktool_m.apk"
if ! download_github_asset "${APKTOOLM_ASSET_ID:-}" "$ATOOLM_APK" "APKTool M APK"; then
    warn "APKTool M APK unavailable — Phase 3 (ATM) will be skipped"
    ATOOLM_APK=""
fi

# ─── Install APK on emulator and verify it runs ───────────────────────────────
try_install() {
    local apk="$1"
    adb install -r "$apk" 2>&1
    return $?
}

get_pkg_name() {
    aapt dump badging "$1" 2>/dev/null | grep "^package:" | sed "s/.*name='\([^']*\)'.*/\1/" || echo ""
}

# ─── Phase 1: NP Manager ─────────────────────────────────────────────────────
step "Phase 1 — NP Manager (15 tools)"

NP_OUTPUT="$OUTPUT_DIR/np_output.apk"
CURRENT_INPUT="$INPUT_APK"

if [[ -n "$NP_APK" && -f "$NP_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export OUTPUT_DIR="$OUTPUT_DIR"
    export SCREENSHOT_DIR="$SCREENSHOT_DIR"
    export NP_APK="$NP_APK"

    if python3 ~/github_automation/np_manager_v3.py 2>&1 | tee "$LOG_DIR/np_manager.log"; then
        NP_OUT=$(find "$OUTPUT_DIR" -name "*.apk" -newer "$INPUT_APK" 2>/dev/null | head -1)
        [[ -f "$OUTPUT_DIR/np_output.apk" ]] && NP_OUT="$OUTPUT_DIR/np_output.apk"

        if [[ -n "$NP_OUT" && -f "$NP_OUT" ]]; then
            cp "$NP_OUT" "$NP_OUTPUT"
            CURRENT_INPUT="$NP_OUTPUT"
            ok "NP Manager done → $(stat -c%s "$NP_OUTPUT") bytes"
        else
            warn "NP Manager produced no output — using input APK"
            cp "$INPUT_APK" "$NP_OUTPUT"
            CURRENT_INPUT="$NP_OUTPUT"
        fi
    else
        warn "NP Manager script failed — using input APK"
        cp "$INPUT_APK" "$NP_OUTPUT"
        CURRENT_INPUT="$NP_OUTPUT"
    fi
else
    warn "Skipping NP Manager (not available)"
    cp "$INPUT_APK" "$NP_OUTPUT"
    CURRENT_INPUT="$NP_OUTPUT"
fi

rm -f "$INPUT_APK" || true

# ─── Phase 2: MT Manager ─────────────────────────────────────────────────────
step "Phase 2 — MT Manager (8 tools)"

MT_OUTPUT="$OUTPUT_DIR/mt_output.apk"

if [[ -n "$MT_APK" && -f "$MT_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export MT_APK="$MT_APK"

    if python3 ~/github_automation/mt_manager_auto.py 2>&1 | tee "$LOG_DIR/mt_manager.log"; then
        MT_OUT=$(find "$OUTPUT_DIR" -name "*.apk" -newer "$CURRENT_INPUT" 2>/dev/null | head -1)
        [[ -f "$OUTPUT_DIR/mt_output.apk" ]] && MT_OUT="$OUTPUT_DIR/mt_output.apk"

        if [[ -n "$MT_OUT" && -f "$MT_OUT" ]]; then
            cp "$MT_OUT" "$MT_OUTPUT"
            CURRENT_INPUT="$MT_OUTPUT"
            ok "MT Manager done → $(stat -c%s "$MT_OUTPUT") bytes"
        else
            warn "MT Manager produced no output — using previous APK"
            cp "$CURRENT_INPUT" "$MT_OUTPUT"
        fi
    else
        warn "MT Manager script failed — using previous APK"
        cp "$CURRENT_INPUT" "$MT_OUTPUT"
        CURRENT_INPUT="$MT_OUTPUT"
    fi
else
    warn "Skipping MT Manager (not available)"
    cp "$CURRENT_INPUT" "$MT_OUTPUT"
    CURRENT_INPUT="$MT_OUTPUT"
fi

rm -f "$NP_OUTPUT" || true

# ─── Phase 3: APKTool M ──────────────────────────────────────────────────────
step "Phase 3 — APKTool M (decompile + resource fix + rebuild)"

ATM_OUTPUT="$OUTPUT_DIR/atm_output.apk"

if [[ -n "$ATOOLM_APK" && -f "$ATOOLM_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export APKTOOL_M_APK="$ATOOLM_APK"

    if python3 ~/github_automation/apktool_m_auto.py 2>&1 | tee "$LOG_DIR/apktool_m.log"; then
        ATM_OUT=$(find "$OUTPUT_DIR" -name "*.apk" -newer "$CURRENT_INPUT" 2>/dev/null | head -1)
        [[ -f "$OUTPUT_DIR/atm_output.apk" ]] && ATM_OUT="$OUTPUT_DIR/atm_output.apk"

        if [[ -n "$ATM_OUT" && -f "$ATM_OUT" ]]; then
            cp "$ATM_OUT" "$ATM_OUTPUT"
            CURRENT_INPUT="$ATM_OUTPUT"
            ok "APKTool M done → $(stat -c%s "$ATM_OUTPUT") bytes"
        else
            warn "APKTool M produced no output — using previous APK"
            cp "$CURRENT_INPUT" "$ATM_OUTPUT"
        fi
    else
        warn "APKTool M failed — using previous APK"
        cp "$CURRENT_INPUT" "$ATM_OUTPUT"
        CURRENT_INPUT="$ATM_OUTPUT"
    fi
else
    warn "Skipping APKTool M (not available)"
    cp "$CURRENT_INPUT" "$ATM_OUTPUT"
    CURRENT_INPUT="$ATM_OUTPUT"
fi

rm -f "$MT_OUTPUT" || true

# ─── APK install verification ─────────────────────────────────────────────────
step "Verifying APK installs on emulator"

if try_install "$CURRENT_INPUT" >> "$LOG_DIR/install_test.log" 2>&1; then
    ok "APK installs successfully"
    PKG=$(get_pkg_name "$CURRENT_INPUT")
    [[ -n "$PKG" ]] && { adb uninstall "$PKG" 2>/dev/null || true; }
else
    warn "Install failed — attempting zipalign fix..."
    ALIGNED="${CURRENT_INPUT%.apk}_aligned.apk"
    if command -v zipalign &>/dev/null; then
        zipalign -v -f 4 "$CURRENT_INPUT" "$ALIGNED" >> "$LOG_DIR/install_test.log" 2>&1 || true
        if [[ -f "$ALIGNED" ]] && try_install "$ALIGNED" >> "$LOG_DIR/install_test.log" 2>&1; then
            cp "$ALIGNED" "$CURRENT_INPUT"
            ok "APK installs after zipalign fix"
            PKG=$(get_pkg_name "$CURRENT_INPUT")
            [[ -n "$PKG" ]] && { adb uninstall "$PKG" 2>/dev/null || true; }
        else
            warn "Still fails after zipalign — delivering as-is"
        fi
        rm -f "$ALIGNED" || true
    fi
fi

# ─── Package final output ─────────────────────────────────────────────────────
step "Packaging final output"

FINAL_OUTPUT="$OUTPUT_DIR/android_hardened.apk"
cp "$CURRENT_INPUT" "$FINAL_OUTPUT"
FINAL_SIZE=$(stat -c%s "$FINAL_OUTPUT")

ok "Pipeline complete — ${FINAL_SIZE} bytes → $FINAL_OUTPUT"
log "(Artifact upload handled by GitHub Actions YAML)"

cp -r "$SCREENSHOT_DIR" "$OUTPUT_DIR/screenshots" 2>/dev/null || true
rm -f "$ATM_OUTPUT" || true
