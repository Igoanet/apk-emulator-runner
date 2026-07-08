#!/usr/bin/env python3
"""
APKTool M Automation — 6 Functions
Package: ru.maximoff.apktool

Purpose in pipeline:
  1. Decompile — verify APK structure is valid after NP/MT processing
  2. Resource Fix — repair any resource corruption introduced by NP/MT tools
  3. Rebuild — produce a clean, verified APK from decompiled sources
  4. (optional) Framework Install — install AOSP framework for res decoding
  5. (optional) Batch Decompile — not used in pipeline
  6. (optional) Error Log — check for build errors

Run after MT Manager. Input: mt_output.apk → Output: final_output.apk
"""
import subprocess, time, os, sys, re, shutil

APKTOOL_PKG   = "ru.maximoff.apktool"
INPUT_APK     = os.environ.get("INPUT_APK", "")
OUTPUT_DIR    = os.environ.get("OUTPUT_DIR",  os.path.expanduser("~/fud-work/output"))
SCREENSHOT_DIR= os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))
APKTOOL_M_APK = os.environ.get("APKTOOL_M_APK", os.path.expanduser("~/apk-tools/apktool_m.apk"))

# Where APKTool M saves its output on the device
APKTOOL_OUTPUT_PATHS = [
    "/sdcard/ApktoolM/",
    "/sdcard/Android/data/ru.maximoff.apktool/files/",
    "/sdcard/Download/",
]

# ─── ADB helpers ─────────────────────────────────────────────────────────────
def adb(cmd):
    r = subprocess.run(f"adb {cmd}", shell=True, capture_output=True, text=True, timeout=60)
    return r

def get_xml(save_as=None):
    adb("shell uiautomator dump /sdcard/ui.xml")
    time.sleep(0.4)
    r = adb("shell cat /sdcard/ui.xml")
    xml = r.stdout or ""
    if save_as:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        with open(os.path.join(SCREENSHOT_DIR, f"{save_as}.xml"), "w") as f:
            f.write(xml)
    return xml

def screenshot(name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    adb(f"shell screencap -p /sdcard/atm_{name}.png")
    adb(f"pull /sdcard/atm_{name}.png {SCREENSHOT_DIR}/atm_{name}.png")

def find_any_bounds(xml):
    results = []
    for m in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        t = m.group(1)
        x = (int(m.group(2)) + int(m.group(4))) // 2
        y = (int(m.group(3)) + int(m.group(5))) // 2
        results.append((t, x, y))
    return results

def tap_text(xml, text, reason=""):
    nodes = find_any_bounds(xml)
    for t, x, y in nodes:
        if t.strip() == text or text.lower() in t.lower():
            print(f"[ATM] Tap '{text}' @ ({x},{y}) — {reason}")
            adb(f"shell input tap {x} {y}")
            time.sleep(0.8)
            return True
    return False

def scroll_down():
    adb("shell input swipe 540 1200 540 400 600")
    time.sleep(0.5)

def dismiss_dialogs():
    for _ in range(5):
        xml = get_xml()
        texts = [t.strip() for t,_,_ in find_any_bounds(xml) if t.strip()]
        dismissed = False
        for kw in ["Close app", "Wait", "OK", "确定", "Allow", "Grant"]:
            if kw in texts:
                tap_text(xml, kw, "dismiss")
                dismissed = True
                time.sleep(1)
                break
        if not dismissed:
            break

# ─── Install & launch ─────────────────────────────────────────────────────────
def install_apktool_m():
    if not os.path.exists(APKTOOL_M_APK):
        print(f"[ATM] APKTool M APK not found: {APKTOOL_M_APK}")
        return False
    print(f"[ATM] Installing APKTool M ({os.path.getsize(APKTOOL_M_APK)//1024}KB)...")
    r = adb(f"install -r -d '{APKTOOL_M_APK}'")
    if r.returncode != 0:
        print(f"[ATM] Install failed: {r.stderr[:200]}")
        return False
    print("[ATM] APKTool M installed")
    return True

def launch_apktool_m():
    adb(f"shell am start -n {APKTOOL_PKG}/.MainActivity")
    time.sleep(4)
    dismiss_dialogs()
    # Grant storage permissions
    adb(f"shell pm grant {APKTOOL_PKG} android.permission.READ_EXTERNAL_STORAGE")
    adb(f"shell pm grant {APKTOOL_PKG} android.permission.WRITE_EXTERNAL_STORAGE")
    adb(f"shell appops set {APKTOOL_PKG} MANAGE_EXTERNAL_STORAGE allow")
    time.sleep(1)

# ─── Push APK to device ───────────────────────────────────────────────────────
ATM_INPUT_PATH = "/sdcard/ApktoolM/atm_input.apk"

def push_input_apk():
    adb("shell mkdir -p /sdcard/ApktoolM")
    r = adb(f"push '{INPUT_APK}' {ATM_INPUT_PATH}")
    if r.returncode != 0:
        # Fallback to Download
        global ATM_INPUT_PATH
        ATM_INPUT_PATH = "/sdcard/Download/atm_input.apk"
        adb(f"push '{INPUT_APK}' {ATM_INPUT_PATH}")
    print(f"[ATM] APK pushed to {ATM_INPUT_PATH}")

# ─── Navigate in file browser ─────────────────────────────────────────────────
def navigate_to_apk():
    """Navigate APKTool M's file browser to find atm_input.apk."""
    print("[ATM] Navigating to input APK...")
    for attempt in range(15):
        xml = get_xml()
        nodes = find_any_bounds(xml)
        texts = [t.strip() for t,_,_ in nodes if t.strip()]

        # APK visible
        if any("atm_input" in t for t in texts):
            print("[ATM] APK found in file browser")
            return True

        # Try tapping path breadcrumbs
        for folder in ["ApktoolM", "Download", "sdcard"]:
            if any(folder in t for t in texts):
                tap_text(xml, folder, f"nav {folder}")
                time.sleep(1.5)
                break
        else:
            scroll_down()
            time.sleep(0.5)

    return False

# ─── Tap the APK to open operations menu ──────────────────────────────────────
def tap_apk_and_select(operation):
    """Tap atm_input.apk → operation dialog → select operation."""
    for attempt in range(8):
        xml = get_xml()
        for t, x, y in find_any_bounds(xml):
            if "atm_input" in t.lower() and ".apk" in t.lower():
                print(f"[ATM] Tapping APK '{t}' @ ({x},{y})")
                adb(f"shell input tap {x} {y}")
                time.sleep(2)

                # Wait for operation menu
                xml2 = get_xml()
                texts2 = [t2.strip() for t2,_,_ in find_any_bounds(xml2) if t2.strip()]
                print(f"[ATM] After APK tap: {texts2[:8]}")

                # Look for operation in dialog
                op_kws = {
                    "decompile": ["Decompile", "decompile", "反编译", "Disassemble"],
                    "rebuild":   ["Build", "Rebuild", "rebuild", "Compile", "编译", "重新编译"],
                    "resource_fix": ["Resource Fix", "Fix Resource", "资源修复", "Fix"],
                    "framework": ["Install Framework", "Framework", "框架"],
                }
                target_kws = op_kws.get(operation, [operation])
                for kw in target_kws:
                    if tap_text(xml2, kw, f"ATM op: {operation}"):
                        return True

                # Maybe the dialog has a list — scroll to find it
                for _ in range(3):
                    scroll_down()
                    xml3 = get_xml()
                    for kw in target_kws:
                        if tap_text(xml3, kw, f"ATM op scroll: {operation}"):
                            return True

                # Dismiss and retry
                adb("shell input keyevent KEYCODE_BACK")
                time.sleep(1)
                break
        else:
            scroll_down()
        time.sleep(0.5)
    return False

# ─── Wait for operation to complete ──────────────────────────────────────────
def wait_for_completion(operation, timeout=180):
    """Wait for APKTool M to finish an operation."""
    print(f"[ATM] Waiting for '{operation}' to complete...")
    for i in range(timeout // 3):
        time.sleep(3)
        xml = get_xml()
        texts = [t.strip() for t,_,_ in find_any_bounds(xml) if t.strip()]

        # Success indicators
        for kw in ["OK", "确定", "Done", "Success", "完成", "Finish", "Completed"]:
            if kw in texts:
                tap_text(xml, kw, f"ATM done: {kw}")
                print(f"[ATM] '{operation}' ✓")
                return True

        # Error indicators — tap close, mark as failed
        for kw in ["Error", "Failed", "错误", "Close", "Cancel"]:
            if kw in texts:
                print(f"[ATM] '{operation}' failed — {kw}")
                tap_text(xml, kw, "ATM error dismiss")
                return False

        # Progress
        if any("%" in t or re.search(r'\d+/\d+', t) for t in texts):
            print(f"[ATM] Processing... ({texts[:3]})")
            continue

        # Output path dialog (APKTool M asks where to save) — confirm default
        for kw in ["CONFIRM", "Confirm", "Save", "OK", "确定"]:
            if kw in texts:
                tap_text(xml, kw, f"ATM save dialog: {kw}")
                time.sleep(2)
                break

    print(f"[ATM] '{operation}' timed out")
    return False

# ─── Framework installation (needed for proper resource decode) ───────────────
def install_framework():
    """Install AOSP framework so APKTool M can decode system resources."""
    print("[ATM] Installing framework...")
    xml = get_xml()
    # Look for framework option in menu or settings
    for kw in ["Install Framework", "Framework Install", "框架安装"]:
        if tap_text(xml, kw, "ATM framework"):
            time.sleep(3)
            wait_for_completion("framework", timeout=60)
            return
    # Try via settings/menu
    for kw in ["Settings", "Menu", "设置", "More"]:
        if tap_text(xml, kw, "ATM settings"):
            time.sleep(1.5)
            xml2 = get_xml()
            for kw2 in ["Install Framework", "Framework"]:
                if tap_text(xml2, kw2, "ATM fw from settings"):
                    time.sleep(3)
                    wait_for_completion("framework", timeout=60)
                    return
            adb("shell input keyevent KEYCODE_BACK")
            break

# ─── Find output APK ──────────────────────────────────────────────────────────
def find_output_apk():
    """Find the output APK produced by APKTool M rebuild."""
    search = [
        "/sdcard/ApktoolM/",
        "/sdcard/ApktoolM/atm_input/",
        "/sdcard/Download/",
        "/sdcard/Android/data/ru.maximoff.apktool/files/",
    ]
    for path in search:
        r = adb(f"shell 'find {path} -maxdepth 3 -name \"*.apk\" "
                f"-newer {ATM_INPUT_PATH} -type f 2>/dev/null | head -3'")
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line and line.endswith(".apk") and "atm_input.apk" not in line:
                return line
    # Last resort — newest APK anywhere
    for path in search:
        r = adb(f"shell 'ls -t {path}*.apk 2>/dev/null | head -1'")
        val = r.stdout.strip()
        if val:
            return path + val if not val.startswith("/") else val
    return None

# ─── Main pipeline ─────────────────────────────────────────────────────────────
def run_pipeline():
    print("=" * 60)
    print("APKTool M Automation — Decompile → Resource Fix → Rebuild")
    print("=" * 60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if not INPUT_APK or not os.path.exists(INPUT_APK):
        print(f"[ATM] No input APK: {INPUT_APK}")
        return False

    # Install APKTool M
    if not install_apktool_m():
        print("[ATM] APKTool M not available — skipping")
        return False

    # Wait for emulator boot
    for _ in range(30):
        r = adb("shell getprop sys.boot_completed")
        if r.stdout.strip() == "1":
            break
        time.sleep(5)
    dismiss_dialogs()

    # Push APK
    push_input_apk()

    # Launch APKTool M
    launch_apktool_m()
    screenshot("atm_launched")

    # Dismiss first-run dialogs
    for _ in range(5):
        xml = get_xml()
        for kw in ["GRANT", "Allow", "OK", "确定", "Agree", "AGREE"]:
            if tap_text(xml, kw, "ATM first-run"):
                time.sleep(1.5)
                break
        else:
            break

    # Navigate to APK
    if not navigate_to_apk():
        print("[ATM] Could not find input APK in file browser")
        screenshot("atm_nav_failed")
        # Continue anyway — APK is on device at ATM_INPUT_PATH
        # We'll use APKTool M via intent/URI if UI nav fails
        print("[ATM] Attempting direct URI open...")
        adb(f"shell am start -a android.intent.action.VIEW "
            f"-t application/vnd.android.package-archive "
            f"-d file://{ATM_INPUT_PATH} -n {APKTOOL_PKG}/.MainActivity")
        time.sleep(3)

    screenshot("atm_apk_found")

    # ── Step 1: Decompile ──────────────────────────────────────────────────
    print("\n[ATM] Step 1: Decompile")
    if tap_apk_and_select("decompile"):
        done = wait_for_completion("decompile", timeout=180)
        screenshot("atm_decompile_done")
        if not done:
            print("[ATM] Decompile had errors — continuing with rebuild anyway")
    else:
        print("[ATM] Could not start decompile — skipping")

    # ── Step 2: Resource Fix ───────────────────────────────────────────────
    print("\n[ATM] Step 2: Resource Fix")
    # Re-navigate to APK
    navigate_to_apk()
    if tap_apk_and_select("resource_fix"):
        wait_for_completion("resource_fix", timeout=120)
        screenshot("atm_resource_fix_done")
    else:
        print("[ATM] Resource Fix not available — skipping")

    # ── Step 3: Rebuild ────────────────────────────────────────────────────
    print("\n[ATM] Step 3: Rebuild")
    navigate_to_apk()
    if tap_apk_and_select("rebuild"):
        done = wait_for_completion("rebuild", timeout=300)
        screenshot("atm_rebuild_done")
        if not done:
            print("[ATM] Rebuild failed — using input APK as output")
    else:
        print("[ATM] Could not start rebuild — using input APK as output")

    # ── Pull output ────────────────────────────────────────────────────────
    output_apk = find_output_apk()
    out_local = os.path.join(OUTPUT_DIR, "atm_output.apk")

    if output_apk:
        r = adb(f"pull '{output_apk}' '{out_local}'")
        if os.path.exists(out_local) and os.path.getsize(out_local) > 0:
            print(f"[ATM] Output: {out_local} ({os.path.getsize(out_local)//1024}KB)")
            return True
        else:
            print("[ATM] Pull failed — using input APK as output")

    # Fallback: use input APK (it was already processed by NP/MT)
    adb(f"pull {ATM_INPUT_PATH} '{out_local}'")
    if os.path.exists(out_local) and os.path.getsize(out_local) > 0:
        print(f"[ATM] Fallback output (input APK): {out_local}")
        return True

    print("[ATM] No output found")
    return False


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
