#!/usr/bin/env bash
# run_pipeline_v3.sh — Android emulator + NP Manager pipeline (NP-only)
#
# Input APK aur NP Manager APK private GitHub release assets se `gh api` se
# download hote hain — GitHub Actions runners pe yehi reliable method hai.
# REPO kabhi hardcode nahi — workflow ke "Resolve inputs" step se env me aata
# hai (github.repository), fallback `gh repo view` se current repo.

set -euo pipefail

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)}"
if [[ -z "$REPO" ]]; then
    echo "REPO env missing — workflow isko github.repository se set karta hai" >&2
    exit 1
fi

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
log "ENV: GITHUB_TOKEN set=$([ -n "${GITHUB_TOKEN:-}" ] && echo yes || echo NO)"
log "ENV: GMAIL_EMAIL set=$([ -n "${GMAIL_EMAIL:-}" ] && echo yes || echo NO)"

# ─── Cleanup helpers ──────────────────────────────────────────────────────────
cleanup_emulator_storage() {
    log "[CLEANUP] Wiping emulator sdcard..."
    adb shell "rm -rf /sdcard/NP_Manager /sdcard/Download/input.apk" 2>/dev/null || true
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
    log "Downloading ${label} (asset_id=${asset_id}, repo=${REPO})..."
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

# ─── Gmail (Google account) sign-in ───────────────────────────────────────────
# GMAIL_EMAIL set ho tabhi chalta hai. UI automation brittle hoti hai — fail pe
# pipeline rukti nahi, sirf warn; screenshots/logs artifacts me milte hain.
if [[ -n "${GMAIL_EMAIL:-}" ]]; then
    step "Gmail sign-in (${GMAIL_EMAIL})"
    export GMAIL_EMAIL GMAIL_PASS
    export SCREENSHOT_DIR="$SCREENSHOT_DIR"
    if python3 ~/github_automation/gmail_login.py 2>&1 | tee "$LOG_DIR/gmail_login.log"; then
        ok "Gmail sign-in confirmed — ${GMAIL_EMAIL} emulator pe logged in"
    else
        warn "Gmail sign-in poora nahi hua — gmail_*.png screenshots + gmail_login.log dekh lo (pipeline continue hogi)"
    fi
else
    log "GMAIL_EMAIL not set — Gmail sign-in stage skipped"
fi

# ─── Download input APK ───────────────────────────────────────────────────────
step "Downloading input APK"
INPUT_APK="$APK_DIR/input.apk"

if ! download_github_asset "${APK_ASSET_ID:-}" "$INPUT_APK" "input APK"; then
    fail "Cannot download input APK — aborting"
    exit 1
fi
log "Input APK: $(stat -c%s "$INPUT_APK") bytes"

# ─── Download NP Manager APK ──────────────────────────────────────────────────
step "Downloading NP Manager APK"

NP_APK="$TOOL_DIR/np_manager.apk"
if ! download_github_asset "${NP_ASSET_ID:-}" "$NP_APK" "NP Manager APK"; then
    warn "NP Manager APK unavailable — NP stage will pass-through input APK"
    NP_APK=""
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

# ─── NP Manager stage ─────────────────────────────────────────────────────────
step "NP Manager (15 tools)"

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
rm -f "$NP_OUTPUT" || true
