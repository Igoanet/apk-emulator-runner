#!/usr/bin/env bash
# run_pipeline_v3.sh — Android hardening pipeline for GitHub Actions emulator
#
# Stages (in order):
#   1. Download input APK + tool APKs from Replit API server
#   2. NP Manager (15 selected tools)  → np_output.apk
#   3. MT Manager  (8 selected tools)  → mt_output.apk
#   4. APKTool M   (Decompile+Fix+Rebuild) → atm_output.apk
#   5. Upload final APK as GitHub Actions artifact
#
# Env vars expected (from GitHub Actions):
#   APK_URL         — HTTPS URL to download the input APK (from Replit API)
#   API_BASE_URL    — base URL of Replit API server (e.g. https://xxx.replit.dev)
#   NP_APK_URL      — URL to download NP Manager APK
#   MT_APK_URL      — URL to download MT Manager APK (optional)
#   APKTOOL_M_URL   — URL to download APKTool M APK (optional)
#   RUN_ID          — Pipeline run ID (passed to API server for status updates)

set -euo pipefail

WORK_DIR="$HOME/fud-work"
APK_DIR="$WORK_DIR/apks"
TOOL_DIR="$HOME/apk-tools"
OUTPUT_DIR="$WORK_DIR/output"
SCREENSHOT_DIR="$WORK_DIR/screenshots"
LOG_DIR="$WORK_DIR/logs"

mkdir -p "$APK_DIR" "$TOOL_DIR" "$OUTPUT_DIR" "$SCREENSHOT_DIR" "$LOG_DIR"

# ─── Logging helpers ──────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_DIR/pipeline.log"; }
step() { echo; log "═══ $* ═══"; }
ok()   { log "✓ $*"; }
warn() { log "⚠ $*"; }
fail() { log "✗ $*"; }

# ─── Status update to Replit API ──────────────────────────────────────────────
update_status() {
    local phase="$1" message="$2"
    if [[ -n "${API_BASE_URL:-}" && -n "${RUN_ID:-}" ]]; then
        curl -s -X POST "${API_BASE_URL}/api/pipeline/status" \
            -H "Content-Type: application/json" \
            -d "{\"runId\":\"${RUN_ID}\",\"phase\":\"${phase}\",\"message\":\"${message}\"}" \
            --max-time 10 || true
    fi
    log "[STATUS] ${phase}: ${message}"
}

# ─── Download helper (with retry) ────────────────────────────────────────────
download_with_retry() {
    local url="$1" dest="$2" label="$3"
    for attempt in 1 2 3; do
        log "Downloading ${label} (attempt ${attempt})..."
        if curl -L --max-time 120 --retry 2 -o "$dest" "$url" 2>>"$LOG_DIR/curl.log"; then
            local size
            size=$(stat -c%s "$dest" 2>/dev/null || echo 0)
            if [[ $size -gt 1000 ]]; then
                ok "${label} downloaded (${size} bytes)"
                return 0
            fi
        fi
        warn "${label} download failed (attempt ${attempt})"
        sleep 5
    done
    return 1
}

# ─── Wait for emulator to be fully booted ────────────────────────────────────
step "Waiting for emulator to boot"
for i in $(seq 1 60); do
    BOOT=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || echo "0")
    if [[ "$BOOT" == "1" ]]; then
        ok "Emulator booted"
        break
    fi
    sleep 5
    [[ $((i % 6)) -eq 0 ]] && log "  Waiting... ${i}/60"
done

# Unlock screen
adb shell input keyevent KEYCODE_WAKEUP  || true
adb shell wm dismiss-keyguard            || true
adb shell input keyevent KEYCODE_HOME    || true
sleep 2

# ─── Download input APK ───────────────────────────────────────────────────────
step "Downloading input APK"
INPUT_APK="$APK_DIR/input.apk"

if ! download_with_retry "${APK_URL}" "$INPUT_APK" "input APK"; then
    fail "Cannot download input APK — aborting"
    exit 1
fi
APK_SIZE=$(stat -c%s "$INPUT_APK")
log "Input APK: ${APK_SIZE} bytes"

# ─── Download tool APKs ───────────────────────────────────────────────────────
step "Downloading tool APKs"

NP_APK="$TOOL_DIR/np_manager.apk"
if download_with_retry "${NP_APK_URL:-}" "$NP_APK" "NP Manager APK" 2>/dev/null; then
    ok "NP Manager APK ready"
else
    warn "NP Manager APK unavailable — Phase 1 (NP) will be skipped"
    NP_APK=""
fi

MT_APK="$TOOL_DIR/mt_manager.apk"
if download_with_retry "${MT_APK_URL:-}" "$MT_APK" "MT Manager APK" 2>/dev/null; then
    ok "MT Manager APK ready"
else
    warn "MT Manager APK unavailable — Phase 2 (MT) will be skipped"
    MT_APK=""
fi

ATOOLM_APK="$TOOL_DIR/apktool_m.apk"
if download_with_retry "${APKTOOL_M_URL:-}" "$ATOOLM_APK" "APKTool M APK" 2>/dev/null; then
    ok "APKTool M APK ready"
else
    warn "APKTool M APK unavailable — Phase 3 (ATM) will be skipped"
    ATOOLM_APK=""
fi

# ─── Phase 1: NP Manager ─────────────────────────────────────────────────────
step "Phase 1 — NP Manager (15 tools)"
update_status "np_manager" "starting"

NP_OUTPUT="$OUTPUT_DIR/np_output.apk"
CURRENT_INPUT="$INPUT_APK"

if [[ -n "$NP_APK" && -f "$NP_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export OUTPUT_DIR="$OUTPUT_DIR"
    export SCREENSHOT_DIR="$SCREENSHOT_DIR"
    export NP_APK="$NP_APK"

    if python3 ~/github_automation/np_manager_v3.py 2>&1 | tee "$LOG_DIR/np_manager.log"; then
        # Look for NP Manager output APK
        if [[ -f "$OUTPUT_DIR/np_output.apk" ]]; then
            NP_OUT="$OUTPUT_DIR/np_output.apk"
        else
            # np_manager_v3.py saves to OUTPUT_DIR with the input filename
            NP_OUT=$(find "$OUTPUT_DIR" -name "*.apk" -newer "$INPUT_APK" 2>/dev/null | head -1)
        fi

        if [[ -n "$NP_OUT" && -f "$NP_OUT" ]]; then
            cp "$NP_OUT" "$NP_OUTPUT"
            CURRENT_INPUT="$NP_OUTPUT"
            ok "NP Manager done → $(stat -c%s "$NP_OUTPUT") bytes"
            update_status "np_manager" "done"
        else
            warn "NP Manager produced no output — using input APK"
            cp "$INPUT_APK" "$NP_OUTPUT"
            CURRENT_INPUT="$NP_OUTPUT"
            update_status "np_manager" "no_output_fallback"
        fi
    else
        warn "NP Manager script failed — using input APK"
        cp "$INPUT_APK" "$NP_OUTPUT"
        CURRENT_INPUT="$NP_OUTPUT"
        update_status "np_manager" "failed_fallback"
    fi
else
    warn "Skipping NP Manager (APK not available)"
    cp "$INPUT_APK" "$NP_OUTPUT"
    CURRENT_INPUT="$NP_OUTPUT"
    update_status "np_manager" "skipped"
fi

# ─── Phase 2: MT Manager ──────────────────────────────────────────────────────
step "Phase 2 — MT Manager (8 tools)"
update_status "mt_manager" "starting"

MT_OUTPUT="$OUTPUT_DIR/mt_output.apk"

if [[ -n "$MT_APK" && -f "$MT_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export OUTPUT_DIR="$OUTPUT_DIR"
    export MT_APK="$MT_APK"

    if python3 ~/github_automation/mt_manager_auto.py 2>&1 | tee "$LOG_DIR/mt_manager.log"; then
        MT_OUT=$(find "$OUTPUT_DIR" -name "mt_output.apk" 2>/dev/null | head -1)
        if [[ -n "$MT_OUT" && -f "$MT_OUT" ]]; then
            cp "$MT_OUT" "$MT_OUTPUT"
            CURRENT_INPUT="$MT_OUTPUT"
            ok "MT Manager done → $(stat -c%s "$MT_OUTPUT") bytes"
            update_status "mt_manager" "done"
        else
            warn "MT Manager produced no output — using NP output"
            cp "$NP_OUTPUT" "$MT_OUTPUT"
            CURRENT_INPUT="$MT_OUTPUT"
            update_status "mt_manager" "no_output_fallback"
        fi
    else
        warn "MT Manager script failed — using NP output"
        cp "$NP_OUTPUT" "$MT_OUTPUT"
        CURRENT_INPUT="$MT_OUTPUT"
        update_status "mt_manager" "failed_fallback"
    fi
else
    warn "Skipping MT Manager (APK not available)"
    cp "$NP_OUTPUT" "$MT_OUTPUT"
    CURRENT_INPUT="$MT_OUTPUT"
    update_status "mt_manager" "skipped"
fi

# ─── Phase 3: APKTool M ───────────────────────────────────────────────────────
step "Phase 3 — APKTool M (Decompile → Resource Fix → Rebuild)"
update_status "apktool_m" "starting"

ATM_OUTPUT="$OUTPUT_DIR/atm_output.apk"

if [[ -n "$ATOOLM_APK" && -f "$ATOOLM_APK" ]]; then
    export INPUT_APK="$CURRENT_INPUT"
    export OUTPUT_DIR="$OUTPUT_DIR"
    export APKTOOL_M_APK="$ATOOLM_APK"

    if python3 ~/github_automation/apktool_m_auto.py 2>&1 | tee "$LOG_DIR/apktool_m.log"; then
        ATM_OUT=$(find "$OUTPUT_DIR" -name "atm_output.apk" 2>/dev/null | head -1)
        if [[ -n "$ATM_OUT" && -f "$ATM_OUT" ]]; then
            cp "$ATM_OUT" "$ATM_OUTPUT"
            CURRENT_INPUT="$ATM_OUTPUT"
            ok "APKTool M done → $(stat -c%s "$ATM_OUTPUT") bytes"
            update_status "apktool_m" "done"
        else
            warn "APKTool M produced no output — using MT output"
            cp "$MT_OUTPUT" "$ATM_OUTPUT"
            CURRENT_INPUT="$ATM_OUTPUT"
            update_status "apktool_m" "no_output_fallback"
        fi
    else
        warn "APKTool M script failed — using MT output"
        cp "$MT_OUTPUT" "$ATM_OUTPUT"
        CURRENT_INPUT="$ATM_OUTPUT"
        update_status "apktool_m" "failed_fallback"
    fi
else
    warn "Skipping APKTool M (APK not available)"
    cp "$MT_OUTPUT" "$ATM_OUTPUT"
    CURRENT_INPUT="$ATM_OUTPUT"
    update_status "apktool_m" "skipped"
fi

# ─── Final output ─────────────────────────────────────────────────────────────
step "Packaging final output"

FINAL_OUTPUT="$OUTPUT_DIR/android_hardened.apk"
cp "$CURRENT_INPUT" "$FINAL_OUTPUT"

FINAL_SIZE=$(stat -c%s "$FINAL_OUTPUT")
log "Final output: ${FINAL_SIZE} bytes"

# Upload to Replit API so bot.py can download it
if [[ -n "${API_BASE_URL:-}" && -n "${RUN_ID:-}" ]]; then
    log "Uploading result to Replit API..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${API_BASE_URL}/api/pipeline/upload" \
        -F "runId=${RUN_ID}" \
        -F "file=@${FINAL_OUTPUT};filename=android_hardened.apk" \
        --max-time 120) || true
    log "Upload response: ${HTTP_CODE}"

    if [[ "$HTTP_CODE" == "200" ]]; then
        ok "Output uploaded to Replit API"
        update_status "complete" "output_uploaded size=${FINAL_SIZE}"
    else
        warn "Upload failed (HTTP ${HTTP_CODE}) — artifact will be used instead"
        update_status "complete" "upload_failed artifact_fallback"
    fi
fi

# Copy screenshots to output for artifact
cp -r "$SCREENSHOT_DIR" "$OUTPUT_DIR/screenshots" 2>/dev/null || true
cp -r "$LOG_DIR" "$OUTPUT_DIR/logs" 2>/dev/null || true

ok "Pipeline complete: ${FINAL_OUTPUT}"
log "Summary:"
log "  Input:    $(stat -c%s "$INPUT_APK") bytes"
log "  NP out:   $(stat -c%s "$NP_OUTPUT" 2>/dev/null || echo N/A) bytes"
log "  MT out:   $(stat -c%s "$MT_OUTPUT" 2>/dev/null || echo N/A) bytes"
log "  ATM out:  $(stat -c%s "$ATM_OUTPUT" 2>/dev/null || echo N/A) bytes"
log "  Final:    ${FINAL_SIZE} bytes"
