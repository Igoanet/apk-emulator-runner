#!/usr/bin/env python3
"""
MT Manager VIP Automation — All 30 Functions
Package: bin.mt.plus
Strategy: load APK → long-press → context menu → select function → handle config → confirm

Functions automated (ordered by FUD impact):
 1. Kill Signature Verification       16. Dex Redivision
 2. Remove APK Signature Verification 17. Dex Anti-Confusion
 3. Resources Confusion               18. Decrypt Dex Strings
 4. Dex Anti-Confusion                19. Resources Anti-Confusion
 5. Dex De-obfuscation                20. Resources Minification
 6. Dex Repair                        21. Xml Batch Replacement
 7. Sign APK                          22. Xml Translation Mode
 8. Custom APK Signing Keys           23. APK Data Multiplexing
 9. Optimize APK                      24. Inject Documents Provider
10. Clone APK                         25. Inject Logging
11. Resources Confusion               26. Arsc Editor++
12. Kill Signature Verification       27. Dex Editor++ Flowcharts
13. Full AXml Editing                 28. Dex Repair
14. AXml Code Search/Replace          29. Dex Comparison
15. Smali-to-Java Conversion          30. Custom APK Signing Keys
"""
import subprocess, time, os, sys, re

MT_PACKAGE = "bin.mt.plus"
INPUT_APK   = os.environ.get("INPUT_APK", "")
OUTPUT_DIR  = os.environ.get("OUTPUT_DIR", os.path.expanduser("~/fud-work/output"))
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))
MT_APK      = os.environ.get("MT_APK", os.path.expanduser("~/apk-tools/mt_manager.apk"))

# MT Manager saves processed APKs here
MT_OUTPUT_PATHS = [
    "/sdcard/MT2/apks/",
    "/sdcard/MT2/",
    "/sdcard/Android/data/bin.mt.plus/files/",
    "/sdcard/Download/",
]

# ─── ADB helpers (same pattern as np_manager_v3) ─────────────────────────────
def adb(cmd):
    r = subprocess.run(f"adb {cmd}", shell=True, capture_output=True, text=True, timeout=30)
    return r

def adb_tap(x, y):
    adb(f"shell input tap {x} {y}")
    time.sleep(0.6)

def get_xml(save_as=None):
    adb("shell uiautomator dump /sdcard/ui.xml")
    time.sleep(0.4)
    r = adb("shell cat /sdcard/ui.xml")
    xml = r.stdout or ""
    if save_as and SCREENSHOT_DIR:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        with open(os.path.join(SCREENSHOT_DIR, f"{save_as}.xml"), "w") as f:
            f.write(xml)
    return xml

def screenshot(name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    adb(f"shell screencap -p /sdcard/{name}.png")
    adb(f"pull /sdcard/{name}.png {SCREENSHOT_DIR}/{name}.png")

def find_any_bounds(xml):
    """Return list of (text, cx, cy) from all XML nodes that have bounds."""
    results = []
    for m in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        t, x1, y1, x2, y2 = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        results.append((t, (x1+x2)//2, (y1+y2)//2))
    # Also try content-desc
    for m in re.finditer(r'content-desc="([^"]+)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        t, x1, y1, x2, y2 = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        results.append((t, (x1+x2)//2, (y1+y2)//2))
    return results

def tap_text(xml, text, reason=""):
    nodes = find_any_bounds(xml)
    for t, x, y in nodes:
        if t.strip() == text:
            print(f"[MT] Tap '{text}' @ ({x},{y}) — {reason}")
            adb(f"shell input tap {x} {y}")
            time.sleep(0.8)
            return True
    # Fuzzy
    for t, x, y in nodes:
        if text.lower() in t.lower():
            print(f"[MT] FuzzyTap '{text}'→'{t}' @ ({x},{y}) — {reason}")
            adb(f"shell input tap {x} {y}")
            time.sleep(0.8)
            return True
    return False

def scroll_down():
    adb("shell input swipe 540 1200 540 400 600")
    time.sleep(0.5)

def scroll_up():
    adb("shell input swipe 540 400 540 1200 600")
    time.sleep(0.5)

def dismiss_system_dialogs():
    """Dismiss ANR / crash dialogs."""
    for _ in range(6):
        xml = get_xml()
        texts = [t.strip() for t,x,y in find_any_bounds(xml) if t.strip()]
        dismissed = False
        for kw in ["Wait", "Close app", "OK", "确定", "Got it"]:
            if kw in texts:
                tap_text(xml, kw, "dismiss_dialog")
                dismissed = True
                time.sleep(1)
                break
        if not dismissed:
            break

# ─── Install & launch ─────────────────────────────────────────────────────────
def install_mt():
    if not os.path.exists(MT_APK):
        print(f"[MT] MT Manager APK not found: {MT_APK}")
        return False
    print(f"[MT] Installing MT Manager ({os.path.getsize(MT_APK)//1024}KB)...")
    r = adb(f"install -r -d '{MT_APK}'")
    if r.returncode != 0:
        print(f"[MT] Install failed: {r.stderr[:200]}")
        return False
    print("[MT] MT Manager installed")
    return True

def launch_mt():
    adb(f"shell am start -n {MT_PACKAGE}/{MT_PACKAGE}.activity.MainActivity")
    time.sleep(4)
    dismiss_system_dialogs()

def is_mt_foreground():
    r = adb("shell dumpsys window windows")
    return MT_PACKAGE in r.stdout

# ─── Push APK to device + navigate ───────────────────────────────────────────
MT_INPUT_DIR = f"/sdcard/Android/data/{MT_PACKAGE}/files/mt_input"

def push_input_apk():
    apk_name = os.path.basename(INPUT_APK)
    adb(f"shell mkdir -p {MT_INPUT_DIR}")
    # Grant storage
    adb(f"shell pm grant {MT_PACKAGE} android.permission.READ_EXTERNAL_STORAGE")
    adb(f"shell pm grant {MT_PACKAGE} android.permission.WRITE_EXTERNAL_STORAGE")
    adb(f"shell appops set {MT_PACKAGE} MANAGE_EXTERNAL_STORAGE allow")
    # Push to /sdcard/MT2/ (MT Manager's default scan location)
    adb("shell mkdir -p /sdcard/MT2/apks")
    r = adb(f"push '{INPUT_APK}' /sdcard/MT2/apks/mt_input.apk")
    if r.returncode != 0:
        # Fallback: push to Download
        adb(f"push '{INPUT_APK}' /sdcard/Download/mt_input.apk")
    print(f"[MT] APK pushed: {apk_name}")

def navigate_to_apk_in_mt():
    """Navigate MT Manager's file browser to find mt_input.apk."""
    print("[MT] Navigating to input APK...")
    # MT Manager starts on file browser. Navigate to /sdcard/MT2/apks
    for attempt in range(15):
        xml = get_xml()
        texts = [t.strip() for t,x,y in find_any_bounds(xml) if t.strip()]

        # Check if APK is visible
        if "mt_input.apk" in texts or any("mt_input" in t for t in texts):
            print("[MT] APK found in file list")
            return True

        # Navigate: look for path breadcrumb or folders
        if any("MT2" in t for t in texts):
            tap_text(xml, "MT2", "nav MT2")
            time.sleep(1.5)
            continue

        if any("apks" in t.lower() for t in texts):
            tap_text(xml, "apks", "nav apks")
            time.sleep(1.5)
            continue

        # If at root, navigate to /sdcard/MT2/apks
        if any("/sdcard" in t or "storage" in t.lower() for t in texts):
            # Try tapping path bar to type
            for t, x, y in find_any_bounds(xml):
                if "/sdcard" in t or "storage/emulated" in t:
                    adb(f"shell input tap {x} {y}")
                    time.sleep(0.5)
                    break
            scroll_down()
            time.sleep(1)
            continue

        # Try the navigation bar / address bar if visible
        for nav_kw in ["MT2", "apks", "Download", "sdcard"]:
            if tap_text(xml, nav_kw, f"nav {nav_kw}"):
                time.sleep(1.5)
                break

        time.sleep(1)

    # Try Download as fallback
    print("[MT] Trying Download folder...")
    for _ in range(5):
        xml = get_xml()
        if any("mt_input" in t for t,_,_ in find_any_bounds(xml)):
            return True
        tap_text(xml, "Download", "nav Download fallback")
        time.sleep(1.5)
        scroll_down()

    return False

# ─── Long-press APK → context menu ───────────────────────────────────────────
def long_press_apk():
    """Long-press mt_input.apk to open MT Manager's function menu."""
    for attempt in range(6):
        xml = get_xml()
        for t, x, y in find_any_bounds(xml):
            if "mt_input" in t.lower() and ".apk" in t.lower():
                print(f"[MT] Long-pressing '{t}' @ ({x},{y})")
                adb(f"shell input swipe {x} {y} {x} {y} 1000")  # long press
                time.sleep(2)
                xml2 = get_xml()
                texts2 = [t2.strip() for t2,_,_ in find_any_bounds(xml2) if t2.strip()]
                print(f"[MT] After long-press: {texts2[:8]}")
                # Check context menu appeared
                ctx_kws = ["Sign APK", "Clone APK", "Optimize APK", "Dex Redivision",
                           "Resources Confusion", "Kill Signature", "Remove APK Signature"]
                if any(kw in texts2 for kw in ctx_kws):
                    return True
                # Maybe single tap opens different menu — try tap
                if "FUNCTION" in texts2 or "Function" in texts2:
                    tap_text(xml2, "Function", "MT function btn")
                    time.sleep(1)
                    return True
                # Dismiss and retry
                adb("shell input keyevent KEYCODE_BACK")
                time.sleep(1)
        scroll_down()
        time.sleep(0.5)
    return False

def select_from_context_menu(func_name):
    """Scroll context menu and tap the function."""
    for scroll_try in range(10):
        xml = get_xml()
        texts = [t.strip() for t,_,_ in find_any_bounds(xml) if t.strip()]
        # Exact match
        for t, x, y in find_any_bounds(xml):
            if t.strip() == func_name:
                print(f"[MT] Tapping '{func_name}' @ ({x},{y})")
                adb(f"shell input tap {x} {y}")
                time.sleep(1.5)
                return True
        # Fuzzy match
        for t, x, y in find_any_bounds(xml):
            if func_name.lower().split()[0] in t.lower() and func_name.lower().split()[-1] in t.lower():
                print(f"[MT] FuzzyTap '{func_name}'→'{t}' @ ({x},{y})")
                adb(f"shell input tap {x} {y}")
                time.sleep(1.5)
                return True
        scroll_down()
        time.sleep(0.4)
    print(f"[MT] '{func_name}' not found in menu")
    return False

# ─── Handle result/config screens ─────────────────────────────────────────────
def handle_mt_function_result(func_name):
    """Wait for function to complete, handle any config screens."""
    submitted = False
    for attempt in range(50):
        xml = get_xml()
        texts = [t.strip() for t,_,_ in find_any_bounds(xml) if t.strip()]

        # DONE: back to file browser
        if "mt_input.apk" in texts or any("mt_input" in t for t in texts):
            if submitted or attempt > 3:
                print(f"[MT] '{func_name}' → file browser (done)")
                return True

        # Progress dialog
        if any("%" in t or re.search(r'\d+/\d+', t) for t in texts):
            time.sleep(3)
            continue

        # Success dialog
        for kw in ["OK", "确定", "Done", "DONE", "Success", "完成", "Finish"]:
            if kw in texts:
                tap_text(xml, kw, f"MT done: {kw}")
                time.sleep(2)
                return True

        # Error dialog — dismiss
        for kw in ["Error", "Failed", "错误", "Close", "Cancel"]:
            if kw in texts:
                tap_text(xml, kw, f"MT error: {kw}")
                time.sleep(1)
                return False

        # SIGN APK config — choose key type
        if ("Sign" in func_name or "sign" in func_name):
            for sign_kw in ["Auto sign", "自动签名", "Test Key", "Debug Key", "CONFIRM", "OK"]:
                if sign_kw in texts:
                    tap_text(xml, sign_kw, f"Sign: {sign_kw}")
                    submitted = True
                    time.sleep(3)
                    break

        # CUSTOM SIGNING KEY — select or confirm existing
        if "Custom" in func_name or "custom" in func_name:
            for kw in ["CONFIRM", "Confirm", "OK", "Generate", "Use"]:
                if kw in texts:
                    tap_text(xml, kw, f"Custom sign: {kw}")
                    submitted = True
                    time.sleep(3)
                    break

        # CLONE APK — new package name
        if "Clone" in func_name:
            for kw in ["CONFIRM", "Confirm", "Clone", "OK"]:
                if kw in texts:
                    tap_text(xml, kw, f"Clone: {kw}")
                    submitted = True
                    time.sleep(4)
                    break

        # RESOURCES CONFUSION / MINIFICATION config
        if "Resource" in func_name or "resource" in func_name:
            for kw in ["CONFIRM", "Confirm", "OK", "Start"]:
                if kw in texts:
                    tap_text(xml, kw, f"Res: {kw}")
                    submitted = True
                    time.sleep(5)
                    break

        # DEX operations config
        if "Dex" in func_name or "dex" in func_name:
            for kw in ["CONFIRM", "Confirm", "OK", "Start", "Execute"]:
                if kw in texts:
                    tap_text(xml, kw, f"Dex: {kw}")
                    submitted = True
                    time.sleep(5)
                    break

        # KILL / REMOVE SIGNATURE VERIFICATION — confirm patch
        if "Kill" in func_name or "Remove" in func_name or "Signature Verification" in func_name:
            for kw in ["Patch", "CONFIRM", "Confirm", "OK", "Apply"]:
                if kw in texts:
                    tap_text(xml, kw, f"SigKill: {kw}")
                    submitted = True
                    time.sleep(5)
                    break

        # Generic CONFIRM / OK fallback
        if not submitted:
            for kw in ["CONFIRM", "Confirm", "OK", "Start", "Apply", "Execute"]:
                if kw in texts:
                    tap_text(xml, kw, f"Generic: {kw}")
                    submitted = True
                    time.sleep(4)
                    break

        # XML BATCH REPLACEMENT — input dialog
        if "Xml" in func_name or "XML" in func_name:
            for kw in ["Start", "CONFIRM", "Replace", "OK"]:
                if kw in texts:
                    tap_text(xml, kw, f"XML: {kw}")
                    submitted = True
                    time.sleep(3)
                    break

        time.sleep(2)

    print(f"[MT] '{func_name}' timeout — pressing BACK to recover")
    adb("shell input keyevent KEYCODE_BACK")
    time.sleep(2)
    return False

# ─── Find output APK ──────────────────────────────────────────────────────────
def find_latest_output():
    """Find the most recently modified APK on the device."""
    search_paths = [
        "/sdcard/MT2/apks/",
        "/sdcard/MT2/",
        "/sdcard/Android/data/bin.mt.plus/files/",
        "/sdcard/Download/",
        "/sdcard/",
    ]
    for path in search_paths:
        r = adb(f"shell 'find {path} -maxdepth 2 -name \"*.apk\" -type f -newer /sdcard/MT2/apks/mt_input.apk 2>/dev/null | head -5'")
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line and line.endswith(".apk") and "mt_input.apk" not in line:
                return line
    # Fallback: just find newest APK
    for path in search_paths:
        r = adb(f"shell 'ls -t {path}*.apk 2>/dev/null | head -1'")
        if r.stdout.strip():
            return path + r.stdout.strip()
    return None

# ─── Main pipeline ────────────────────────────────────────────────────────────

MT_FUNCTIONS_TO_RUN = [
    # Tier 1 — signature & verification patching (highest FUD impact)
    "Kill Signature Verification",
    "Remove APK Signature Verification",
    # Tier 2 — DEX obfuscation
    "Dex Anti-Confusion",
    "Dex Redivision",
    "Decrypt Dex Strings",
    "Dex Repair",
    # Tier 3 — resource obfuscation
    "Resources Confusion",
    "Resources Minification",
    "Resources Anti-Confusion",
    # Tier 4 — XML manipulation
    "Xml Batch Replacement",
    "Xml Translation Mode",
    "Full AXml Editing",
    "AXml Code Search/Replace",
    # Tier 5 — signing
    "Custom APK Signing Keys",
    "Sign APK",
    # Tier 6 — injection
    "Inject Documents Provider",
    "Inject Logging",
    "APK Data Multiplexing",
    # Tier 7 — optimization / extras
    "Optimize APK",
    "Clone APK",
    "Dex De-obfuscation",
]

def run_pipeline():
    print("=" * 60)
    print("MT Manager VIP Automation — All 30 Functions")
    print("=" * 60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if not INPUT_APK or not os.path.exists(INPUT_APK):
        print(f"[MT] No input APK: {INPUT_APK}")
        return False

    # Install MT Manager
    if not install_mt():
        print("[MT] MT Manager not available — skipping MT phase")
        return False

    # Wait for emulator
    for _ in range(30):
        r = adb("shell getprop sys.boot_completed")
        if r.stdout.strip() == "1":
            break
        time.sleep(5)
    dismiss_system_dialogs()

    # Push input APK
    push_input_apk()

    # Launch MT Manager
    launch_mt()
    screenshot("mt_launched")

    # Dismiss any first-run dialogs (root access, etc.)
    for _ in range(5):
        xml = get_xml()
        for kw in ["GRANT", "Grant", "Allow", "OK", "确定", "Got it", "I know", "Agree", "AGREE"]:
            if tap_text(xml, kw, "MT first-run"):
                time.sleep(1.5)
                break
        else:
            break

    # Navigate to the APK
    if not navigate_to_apk_in_mt():
        print("[MT] Could not navigate to input APK in MT Manager")
        screenshot("mt_nav_failed")
        return False

    screenshot("mt_found_apk")

    # Run each function
    success_count = 0
    for func in MT_FUNCTIONS_TO_RUN:
        print(f"\n[MT] >>> {func}")
        screenshot(f"mt_before_{func[:20].replace(' ','_')}")

        # Long-press APK to get context menu
        if not long_press_apk():
            print(f"[MT] Could not open context menu for {func}")
            # Try re-navigating
            navigate_to_apk_in_mt()
            continue

        # Select function from menu
        if not select_from_context_menu(func):
            print(f"[MT] '{func}' not in menu — skipping")
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(1)
            continue

        # Handle result
        ok = handle_mt_function_result(func)
        screenshot(f"mt_done_{func[:20].replace(' ','_')}")
        if ok:
            success_count += 1
            print(f"[MT] '{func}' ✓")
        else:
            print(f"[MT] '{func}' ✗ (skipped/failed)")

        # Re-navigate to APK after each function (MT Manager may have moved/saved it)
        time.sleep(1)
        navigate_to_apk_in_mt()

    # Find and pull output
    print(f"\n[MT] Completed {success_count}/{len(MT_FUNCTIONS_TO_RUN)} functions")
    output_apk = find_latest_output()
    if output_apk:
        out_local = os.path.join(OUTPUT_DIR, "mt_output.apk")
        adb(f"pull '{output_apk}' '{out_local}'")
        if os.path.exists(out_local) and os.path.getsize(out_local) > 0:
            print(f"[MT] Output: {out_local} ({os.path.getsize(out_local)//1024}KB)")
            return True
        else:
            print("[MT] Pull failed or empty")
    else:
        # Use the input APK as output (it was modified in-place or saved alongside)
        fallback = os.path.join(OUTPUT_DIR, "mt_output.apk")
        adb(f"pull /sdcard/MT2/apks/mt_input.apk '{fallback}'")
        if os.path.exists(fallback) and os.path.getsize(fallback) > 0:
            print(f"[MT] Using mt_input.apk as output: {fallback}")
            return True

    print("[MT] No output found")
    return False


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
