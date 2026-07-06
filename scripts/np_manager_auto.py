#!/usr/bin/env python3
"""
NP Manager Premium Automation v18
Runs inside android-emulator-runner script block.
Handles: login, Terms dialog (scroll + agree), 7 anti-detection tools.
"""
import subprocess, time, os, sys, base64, shutil, re, glob

# ── Config ────────────────────────────────────────────────────────────────────
NP_APK = os.environ.get("NP_APK", "")
INPUT_APK = os.environ.get("INPUT_APK", "")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "")
APK_URL = os.environ.get("APK_URL", "")
EMAIL = os.environ.get("NP_MANAGER_EMAIL", "")
PASSWORD = os.environ.get("NP_MANAGER_PASS", "")
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))

def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return type('obj', (object,), {'stdout': '', 'stderr': str(e), 'returncode': 1})()

def adb(cmd, timeout=30):
    return run(f"adb -s emulator-5554 {cmd}", timeout)

def screenshot(name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    adb(f"shell screencap -p /sdcard/screen_{name}.png")
    adb(f"pull /sdcard/screen_{name}.png {path}")
    print(f"[SCREEN] {name}")

def get_screen_info():
    """Get actual device resolution and density for debugging."""
    size = adb("shell wm size").stdout.strip()
    density = adb("shell wm density").stdout.strip()
    print(f"[*] Screen: {size} | Density: {density}")
    # Extract resolution
    m = re.search(r'(\d+)x(\d+)', size)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 320, 640

def get_element_coords(element_text):
    """Get element center coordinates from UIAutomator dump."""
    adb("shell uiautomator dump /sdcard/window_dump.xml")
    r = adb("shell cat /sdcard/window_dump.xml")
    xml = r.stdout
    pattern = re.compile(
        r'<node[^>]*text="' + re.escape(element_text) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    )
    m = pattern.search(xml)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        print(f"[*] Found '{element_text}' @ ({cx},{cy}) bounds=[{x1},{y1}][{x2},{y2}]")
        return (cx, cy)
    return None

def tap_key(key):
    coords = {
        "agree_terms": (0.82, 0.97),  # AGREE bottom-right (proportional)
        "refuse_terms": (0.50, 0.97), # REFUSE bottom-center
        "privacy_policy": (0.18, 0.97), # PRIVACY bottom-left
        "scroll_area": (0.50, 0.60),  # Center of dialog content for scrolling
    }
    rel = coords.get(key)
    if rel:
        w, h = get_screen_info()
        x = int(rel[0] * w)
        y = int(rel[1] * h)
        print(f"[*] Tap '{key}' @ ({x},{y}) on {w}x{h}")
        adb(f"shell input tap {x} {y}")
        return True
    return False

def scroll_terms_dialog():
    """Scroll the terms dialog content to enable AGREE button."""
    w, h = get_screen_info()
    # Scroll from center-bottom to center-top within dialog
    x = w // 2
    y_from = int(h * 0.70)
    y_to = int(h * 0.30)
    print(f"[*] Scrolling terms dialog: ({x},{y_from}) -> ({x},{y_to})")
    adb(f"shell input swipe {x} {y_from} {x} {y_to} 500")
    time.sleep(0.5)

def dismiss_dialog(attempts=8):
    """Aggressive multi-method dialog dismissal."""
    for i in range(attempts):
        screenshot(f"dialog_{i}")
        time.sleep(0.5)

        xml = adb("shell uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml").stdout

        # 1. Check for Terms of Use dialog
        if "用户协议" in xml or "Notice to users" in xml or "同意" in xml:
            print(f"[*] Found Terms dialog, trying multi-method dismiss (attempt {i+1})")

            # Method A: Scroll down first (AGREE might be disabled until scrolled)
            if i == 0:
                for _ in range(5):
                    scroll_terms_dialog()

            # Method B: Tap AGREE using proportional coordinates
            tap_key("agree_terms")
            time.sleep(1.0)

            # Method C: Try uiautomator text-based click
            adb("shell uiautomator runtest /sdcard/uiauto.jar -c com.test.Clicker 2>/dev/null || true")

            # Method D: Key events
            adb("shell input keyevent 66")   # ENTER
            time.sleep(0.3)
            adb("shell input keyevent 23")   # DPAD_CENTER
            time.sleep(0.3)

            # Check if dismissed
            time.sleep(1.0)
            xml2 = adb("shell uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml").stdout
            if "用户协议" not in xml2 and "Notice to users" not in xml2:
                print(f"[+] Terms dialog dismissed!")
                return True
            continue

        # 2. Check for login screen
        if "Email" in xml or "邮箱" in xml or "登录" in xml:
            print("[*] Login screen detected")
            return True

        # 3. Check if NP Manager main screen is visible
        if "NP" in xml or "Tools" in xml or "工具" in xml or "Settings" in xml:
            print("[*] Main screen visible")
            return True

        # 4. Check for "Wait/Close app" system dialog
        if "isn\'t responding" in xml or "Close app" in xml or "Wait" in xml:
            print("[*] Found ANR dialog, tapping Wait")
            w, h = get_screen_info()
            adb(f"shell input tap {int(w*0.75)} {int(h*0.85)}")  # Wait button
            time.sleep(2)
            continue

        # 5. Generic OK/dismiss
        for ok_text in ["OK", "确定", "知道了", "同意", "是", "Yes", "Continue", "继续", "Dismiss", "Close"]:
            coords = get_element_coords(ok_text)
            if coords:
                print(f"[*] Tapping generic OK text: '{ok_text}'")
                adb(f"shell input tap {coords[0]} {coords[1]}")
                time.sleep(1)
                break
        else:
            # No known dialog element found
            print(f"[*] No dialog detected (attempt {i+1})")
            return True

    print("[!] Dialog still present after all attempts")
    return False

def wait_for_device():
    print("[*] Waiting for device...")
    for i in range(60):
        r = run("adb -s emulator-5554 shell getprop sys.boot_completed", timeout=5)
        if "1" in r.stdout:
            print("[+] Device ready")
            return True
        time.sleep(2)
    print("[!] Device not ready")
    return False

def install_npmanager():
    print(f"[*] Installing NP Manager from {NP_APK}...")
    if not os.path.exists(NP_APK):
        print(f"[!] NP Manager APK not found at {NP_APK}")
        return False
    r = adb(f"install -r -d '{NP_APK}'", timeout=60)
    print(r.stdout, r.stderr)
    if "Success" in r.stdout:
        print("[+] NP Manager installed")
        return True
    print("[!] Install failed")
    return False

def launch_npmanager():
    print("[*] Launching NP Manager...")
    adb("shell monkey -p com.juney.fudfud -c android.intent.category.LAUNCHER 1")
    time.sleep(4)
    screenshot("post_launch")
    dismiss_dialog()

def handle_login():
    print("[*] Checking login state...")
    screenshot("login_check")
    xml = adb("shell uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml").stdout

    if EMAIL and PASSWORD and ("邮箱" in xml or "Email" in xml or "登录" in xml):
        print("[*] Login screen detected, entering credentials...")
        # Try to find email field
        email_coords = get_element_coords("邮箱") or get_element_coords("Email")
        if not email_coords:
            # Fallback: tap in upper portion of screen
            w, h = get_screen_info()
            email_coords = (w // 2, int(h * 0.35))
        adb(f"shell input tap {email_coords[0]} {email_coords[1]}")
        time.sleep(0.5)
        adb(f'shell input text "{EMAIL}"')
        time.sleep(0.5)

        # Tap password field (below email)
        pass_coords = (email_coords[0], email_coords[1] + 80)
        adb(f"shell input tap {pass_coords[0]} {pass_coords[1]}")
        time.sleep(0.5)
        adb(f'shell input text "{PASSWORD}"')
        time.sleep(0.5)

        # Find login button
        login_coords = get_element_coords("登录") or get_element_coords("Login") or get_element_coords("确定")
        if not login_coords:
            w, h = get_screen_info()
            login_coords = (w // 2, int(h * 0.60))
        adb(f"shell input tap {login_coords[0]} {login_coords[1]}")
        time.sleep(5)
        screenshot("after_login")
        dismiss_dialog()
        print("[+] Login completed")
    else:
        print("[*] No login screen or no credentials")

def open_apk():
    print(f"[*] Pushing input APK: {INPUT_APK}")
    if not os.path.exists(INPUT_APK):
        print("[!] Input APK missing")
        return False
    adb(f"push '{INPUT_APK}' /sdcard/Download/input.apk")
    time.sleep(1)
    screenshot("01_apk_pushed")

    print("[*] Opening APK in NP Manager...")
    adb('shell am start -a android.intent.action.VIEW -d file:///sdcard/Download/input.apk -t application/vnd.android.package-archive')
    time.sleep(5)
    screenshot("03_apk_opened")
    dismiss_dialog()

    # Wait for project to load
    print("[*] Waiting for project load...")
    time.sleep(8)
    return True

def run_tool(tool_name, xml_label, fallback_coords=None):
    print(f"[*] === {tool_name} ===")
    screenshot(f"before_{tool_name.replace(' ', '_')[:25]}")

    # Try XML-based navigation
    xml = adb("shell uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml").stdout

    tools_coords = get_element_coords("Tools") or get_element_coords("工具")
    if tools_coords:
        adb(f"shell input tap {tools_coords[0]} {tools_coords[1]}")
    else:
        print("[!] XML miss 'Tools', fallback coord")
        w, h = get_screen_info()
        adb(f"shell input tap {w//2} {int(h*0.06)}")  # Top nav area
    time.sleep(1)

    tool_coords = get_element_coords(xml_label)
    if tool_coords:
        adb(f"shell input tap {tool_coords[0]} {tool_coords[1]}")
    else:
        print(f"[!] XML miss '{xml_label}', fallback coord")
        if fallback_coords:
            adb(f"shell input tap {fallback_coords[0]} {fallback_coords[1]}")
        else:
            w, h = get_screen_info()
            adb(f"shell input tap {w//2} {int(h*0.25)}")

    # Wait for tool to process
    time.sleep(15)
    screenshot("after_tool_tap")

    # Dismiss any dialogs
    dismiss_dialog()

    # Try to save
    save_coords = get_element_coords("Save") or get_element_coords("保存") or get_element_coords("确定") or get_element_coords("OK")
    if save_coords:
        adb(f"shell input tap {save_coords[0]} {save_coords[1]}")
        print(f"[*] Tap save @ {save_coords}")
    else:
        w, h = get_screen_info()
        adb(f"shell input tap {w//2} {int(h*0.90)}")
        print(f"[*] Tap save fallback @ ({w//2},{int(h*0.90)})")
    time.sleep(2)

    dismiss_dialog()
    print(f"[+] {tool_name} done")

def find_output_apk():
    print("[*] Searching for output APK...")
    screenshot("10_after_sign")

    # Search common locations
    search_paths = [
        "/sdcard/NPManager/output",
        "/sdcard/Android/data/com.juney.fudfud/files",
        "/sdcard/Download",
        "/sdcard/",
        "/data/data/com.juney.fudfud/files",
    ]

    for path in search_paths:
        r = adb(f"shell 'find {path} -name \"*.apk\" -type f 2>/dev/null | head -5'")
        if r.stdout.strip():
            apk_files = r.stdout.strip().split("\n")
            for apk in apk_files:
                apk = apk.strip()
                if apk:
                    print(f"[+] Found APK: {apk}")
                    local_name = os.path.basename(apk) or "output.apk"
                    adb(f"pull '{apk}' {os.path.join(OUTPUT_DIR, local_name)}")
                    print(f"[+] Pulled to {os.path.join(OUTPUT_DIR, local_name)}")
                    return True

    # Try pulling any recently modified APK
    r = adb("shell 'find /sdcard -name \"*.apk\" -mmin -10 2>/dev/null | head -5'")
    if r.stdout.strip():
        apk = r.stdout.strip().split("\n")[0].strip()
        print(f"[+] Found recent APK: {apk}")
        adb(f"pull '{apk}' {os.path.join(OUTPUT_DIR, 'output.apk')}")
        return True

    print("[!] No output APK found")
    return False

def run_pipeline():
    print("=" * 60)
    print("NP Manager Premium Automation v18")
    print("=" * 60)

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.expanduser("~/fud-work/input"), exist_ok=True)

    screenshot("00_start")

    if not wait_for_device():
        print("[!] Device timeout")
        return False

    if not install_npmanager():
        print("[!] Cannot install NP Manager")
        return False

    launch_npmanager()
    handle_login()

    if not open_apk():
        print("[!] Cannot open APK")
        return False

    # Run all 7 anti-detection tools
    tools = [
        ("Encrypt Resource Files", "Encrypt", None),
        ("Anti-APK Pseudo Encryption", "Anti-APK", None),
        ("RES Anti-VT", "RES", None),
        ("Anti-Pseudo Trace", "Anti-Pseudo", None),
        ("Customize ARSC", "Customize", None),
        ("Sign APK", "Sign", None),
    ]

    for tool_name, xml_label, fallback in tools:
        run_tool(tool_name, xml_label, fallback)

    # Extract output
    success = find_output_apk()

    screenshot("99_final")
    if success:
        print("[+] Pipeline completed successfully")
    else:
        print("[!] Pipeline completed but no output found")

    return success

if __name__ == "__main__":
    run_pipeline()
