#!/usr/bin/env python3
"""
NP Manager Premium Automation v21
Complete flow: install -> launch -> dismiss terms -> hamburger menu -> sign in ->
handle pre-connection (remove second device) -> re-login -> open APK -> run tools -> save output
Handles: Terms dialog, hamburger (3 lines), login, pre-connection removal, all 7 anti-detection tools.
Package: com.wn.app.np
"""
import subprocess, time, os, sys, re

EMAIL = os.environ.get("NP_MANAGER_EMAIL", "")
PASSWORD = os.environ.get("NP_MANAGER_PASS", "")
INPUT_APK = os.environ.get("INPUT_APK", "")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.expanduser("~/fud-work/output"))
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))
NP_PACKAGE = "com.wn.app.np"

def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return type('obj', (object,), {'stdout': '', 'stderr': str(e), 'returncode': 1})()

def adb(cmd, timeout=30):
    return run(f"adb -s emulator-5554 {cmd}", timeout)

def screenshot(name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    adb(f"shell screencap -p /sdcard/screen_{name}.png")
    adb(f"pull /sdcard/screen_{name}.png {path}")
    print(f"[SCREEN] {name}")

def get_screen():
    size = adb("shell wm size").stdout.strip()
    m = re.search(r'(\d+)x(\d+)', size)
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)

def get_xml(save_as=None):
    adb("shell uiautomator dump /sdcard/window_dump.xml")
    r = adb("shell cat /sdcard/window_dump.xml")
    xml = r.stdout
    if save_as:
        path = os.path.join(SCREENSHOT_DIR, f"{save_as}.xml")
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(xml)
        # Also print first 2000 chars so it shows in GH Actions logs
        print(f"[XML:{save_as}] {xml[:2000]}")
    return xml

def find_text(xml, text):
    pat = re.compile(r'<node[^>]*text="' + re.escape(text) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    m = pat.search(xml)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1+x2)//2, (y1+y2)//2)
    return None

def tap_text(xml, text, desc=""):
    c = find_text(xml, text)
    if c:
        adb(f"shell input tap {c[0]} {c[1]}")
        print(f"[*] Tap {desc or text} @ {c}")
        return True
    return False

def tap_rel(rx, ry, desc=""):
    w, h = get_screen()
    x, y = int(w*rx), int(h*ry)
    adb(f"shell input tap {x} {y}")
    print(f"[*] Tap {desc} @ ({x},{y})")
    return True

def scroll_rel(x1, y1, x2, y2, dur=500):
    w, h = get_screen()
    adb(f"shell input swipe {int(w*x1)} {int(h*y1)} {int(w*x2)} {int(h*y2)} {dur}")

def back():
    adb("shell input keyevent 4")
    time.sleep(0.5)

def wait_for_boot(max_wait=120):
    print("[*] Waiting for emulator...")
    for i in range(max_wait//2):
        r = adb("shell getprop sys.boot_completed", timeout=5)
        if "1" in r.stdout:
            print("[+] Booted")
            time.sleep(3)
            return True
        time.sleep(2)
    return False

def install_apk(apk_path, pkg):
    if not os.path.exists(os.path.expanduser(apk_path)):
        print(f"[!] APK not found: {apk_path}")
        return False
    print(f"[*] Installing {pkg}...")
    r = adb(f"install -r -d '{os.path.expanduser(apk_path)}'", timeout=60)
    print(f"    {r.stdout[:100]} {r.stderr[:100]}")
    return "Success" in r.stdout or pkg in adb("shell pm list packages").stdout

def dismiss_all_dialogs(max_attempts=10):
    """Dismiss any dialog/popup blocking the main UI: terms, update notice, announcement, etc."""
    for i in range(max_attempts):
        xml = get_xml()
        dismissed = False

        # Update dialog: "WAIT UNTIL LATER" / "UPDATE IMMEDIATELY" / "COPY URL"
        for btn in ["WAIT UNTIL LATER", "Later", "Cancel", "CANCEL", "Skip", "SKIP",
                    "Close", "CLOSE", "No Thanks", "Dismiss"]:
            if tap_text(xml, btn, f"Dialog dismiss: {btn}"):
                time.sleep(1.5)
                dismissed = True
                break

        if not dismissed:
            # Terms / agreement dialogs
            has_terms = any(kw in xml for kw in [
                "\u7528\u6237\u534f\u8bae", "Notice", "Terms", "\u540c\u610f",
                "\u5173\u4e8eAPP", "\u6350\u8d60", "parentPanel"
            ])
            if has_terms:
                print(f"[*] Dialog/terms (attempt {i+1})")
                if i == 0:
                    for _ in range(3):
                        scroll_rel(0.5, 0.70, 0.5, 0.30, 500)
                        time.sleep(0.2)
                (
                    tap_text(xml, "\u540c\u610f", "AGREE") or
                    tap_text(xml, "Agree", "AGREE") or
                    tap_text(xml, "AGREE", "AGREE") or
                    tap_text(xml, "Yes", "Yes") or
                    tap_text(xml, "OK", "OK") or
                    tap_rel(0.82, 0.97, "AGREE fallback")
                )
                time.sleep(1.5)
                dismissed = True

        if not dismissed:
            # No more dialogs
            return True

    print("[!] Dialogs stuck after max attempts")
    return False

def dismiss_terms(max_attempts=6):
    """Legacy alias — calls dismiss_all_dialogs."""
    return dismiss_all_dialogs(max_attempts)

def launch_npm():
    print(f"[*] Launching {NP_PACKAGE}...")
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(0.5)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(4)
    screenshot("launch_np")

def handle_login():
    print("[*] Login flow...")
    dismiss_terms()

    xml = get_xml()
    if "Projects" in xml or "Tools" in xml or "Settings" in xml:
        print("[+] Already logged in")
        return True

    # Tap hamburger menu (3 lines, top-left)
    print("[*] Tapping hamburger (3 lines)...")
    tap_rel(0.08, 0.06, "Hamburger")
    time.sleep(2)
    screenshot("menu_opened")

    xml = get_xml()
    # Look for Sign In / Login / Account
    sign_items = ["Sign In", "Signin", "Login", "Log In", "\u767b\u5f55", "\u767b\u5165", "Account"]
    for item in sign_items:
        if tap_text(xml, item, f"Menu: {item}"):
            break
    else:
        tap_rel(0.25, 0.65, "Menu fallback")

    time.sleep(3)
    screenshot("signin_screen")
    dismiss_terms()

    # Handle pre-connection: remove second device
    xml = get_xml()
    if "pre-connection" in xml.lower() or "connected" in xml.lower() or "Second" in xml or "\u8bbe\u5907" in xml:
        print("[*] Pre-connection detected! Removing second device...")
        remove_items = ["Remove", "Disconnect", "Delete", "\u79fb\u9664", "\u5220\u9664", "\u65ad\u5f00"]
        for item in remove_items:
            if tap_text(xml, item, f"Remove: {item}"):
                time.sleep(2)
                break
        else:
            tap_rel(0.75, 0.45, "Remove device fallback")
            time.sleep(1)
            # Confirm
            confirm_items = ["Yes", "OK", "Confirm", "\u786e\u5b9a", "\u662f"]
            xml2 = get_xml()
            for item in confirm_items:
                if tap_text(xml2, item, f"Confirm: {item}"):
                    break
        time.sleep(3)
        screenshot("after_remove")

        # NOW: re-login with same procedure
        print("[*] Re-logging in after device removal...")
        # Tap hamburger again
        tap_rel(0.08, 0.06, "Hamburger (re-login)")
        time.sleep(2)
        xml = get_xml()
        for item in sign_items:
            if tap_text(xml, item, f"Re-login: {item}"):
                break
        time.sleep(3)
        screenshot("relogin_screen")
        dismiss_terms()

    # Enter email
    print("[*] Entering credentials...")
    xml = get_xml()
    email_field = find_text(xml, "Email") or find_text(xml, "\u90ae\u7bb1") or find_text(xml, "E-mail")
    if not email_field:
        w, h = get_screen()
        email_field = (w//2, int(h*0.38))
    adb(f"shell input tap {email_field[0]} {email_field[1]}")
    time.sleep(0.5)
    adb(f'shell input text "{EMAIL}"')
    print(f"[*] Email: {EMAIL[:5]}...")
    time.sleep(0.5)

    # Enter password (below email)
    pass_field = (email_field[0], email_field[1] + 100)
    adb(f"shell input tap {pass_field[0]} {pass_field[1]}")
    time.sleep(0.5)
    adb(f'shell input text "{PASSWORD}"')
    print("[*] Password entered")
    time.sleep(0.5)

    # Tap login button
    xml = get_xml()
    login_btn = (
        find_text(xml, "Login") or find_text(xml, "Log In") or
        find_text(xml, "Sign In") or find_text(xml, "\u767b\u5f55") or
        find_text(xml, "\u767b\u5165") or find_text(xml, "\u786e\u5b9a")
    )
    if not login_btn:
        w, h = get_screen()
        login_btn = (w//2, int(h*0.58))
    adb(f"shell input tap {login_btn[0]} {login_btn[1]}")
    print(f"[*] Login tapped @ {login_btn}")
    time.sleep(6)
    screenshot("after_login")
    dismiss_terms()

    xml = get_xml()
    if "Email" in xml or "\u90ae\u7bb1" in xml or "Password" in xml:
        print("[!] Still on login screen")
        return False
    print("[+] Login done")
    return True

PROJECT_KEYWORDS = ["Smali", "Manifest", "Resources", "AndroidManifest", "classes.dex",
                    "smali", "manifest", "res/", "META-INF"]

def is_project_loaded(xml):
    return any(kw in xml for kw in PROJECT_KEYWORDS)

def find_any_bounds(xml):
    """Return all (text, cx, cy) tuples from clickable nodes."""
    results = []
    for m in re.finditer(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        txt = m.group(1)
        cx = (int(m.group(2)) + int(m.group(4))) // 2
        cy = (int(m.group(3)) + int(m.group(5))) // 2
        results.append((txt, cx, cy))
    return results

def open_apk():
    print("[*] Opening APK via NP Manager...")
    if not os.path.exists(os.path.expanduser(INPUT_APK)):
        print("[!] Input APK missing")
        return False

    # Push APK to emulator
    adb(f"push '{INPUT_APK}' /sdcard/Download/input.apk")
    time.sleep(1)
    # Also make it discoverable via media scan
    adb("shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
        "-d file:///sdcard/Download/input.apk")
    print("[*] APK pushed to /sdcard/Download/input.apk")

    # Re-launch NP Manager fresh
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(1)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(5)

    # Dismiss ALL dialogs (update notice, announcement, terms, etc.)
    dismiss_all_dialogs(max_attempts=12)
    time.sleep(1)

    screenshot("np_main_screen")
    xml = get_xml(save_as="01_after_login")

    nodes_main = find_any_bounds(xml)
    print(f"[NODES_MAIN] {nodes_main[:30]}")

    # NP Manager opens directly in its file browser at /storage/emulated/0
    # We need to: tap "Download" folder -> tap "input.apk" file -> wait for project load

    # Step 1: Navigate into Download folder
    print("[*] Looking for Download folder in file browser...")
    if not tap_text(xml, "Download", "Download folder"):
        # Fallback: scan all nodes for "Download"
        for txt, cx, cy in nodes_main:
            if "download" in txt.lower():
                adb(f"shell input tap {cx} {cy}")
                print(f"[*] Tapped Download node '{txt}' @ ({cx},{cy})")
                break
        else:
            print("[!] Download folder not found in main screen, trying scroll")
            scroll_rel(0.5, 0.7, 0.5, 0.3, 500)
            time.sleep(1)
            xml = get_xml()
            tap_text(xml, "Download", "Download after scroll")
    time.sleep(2)

    # Step 2: Now inside Download folder — look for input.apk
    screenshot("inside_download")
    xml = get_xml(save_as="02_download_contents")
    nodes_dl = find_any_bounds(xml)
    print(f"[NODES_DL] {nodes_dl}")

    # Check if project already loaded (unlikely but possible via intent)
    if is_project_loaded(xml):
        print("[+] Project loaded!")
        return True

    # Find and tap input.apk
    apk_tapped = False
    for txt, cx, cy in nodes_dl:
        if "input" in txt.lower() or ".apk" in txt.lower():
            adb(f"shell input tap {cx} {cy}")
            print(f"[*] Tapped APK '{txt}' @ ({cx},{cy})")
            apk_tapped = True
            time.sleep(3)
            break

    if not apk_tapped:
        print(f"[!] input.apk not visible in NP file browser (filtered by app). Using ACTION_VIEW intent...")
        # Verify the file exists on device
        r_ls = adb("shell ls -la /sdcard/Download/")
        print(f"[LS] /sdcard/Download/: {r_ls.stdout[:500]}")

        # ACTION_VIEW triggers "Open with" dialog in Android
        # NP Manager shows 3 options: APK Installer, Save As, text editor
        # We want: NP Manager / APK Installer (first NP Manager entry) + "Just once"
        adb(f'shell am start -a android.intent.action.VIEW '
            f'-d file:///sdcard/Download/input.apk '
            f'-t application/vnd.android.package-archive')
        time.sleep(4)
        xml = get_xml(save_as="03_open_with_dialog")
        nodes_ow = find_any_bounds(xml)
        print(f"[NODES_OW] {nodes_ow}")

        # The "Open with" dialog shows NP Manager entries - tap the first one (APK Installer)
        # which opens the APK in NP Manager's project editor
        # Strategy: find all "NP Manager" text nodes, tap the one with lowest Y (first entry)
        nm_nodes = [(txt, cx, cy) for txt, cx, cy in nodes_ow if "NP Manager" in txt]
        print(f"[NM_NODES] {nm_nodes}")

        if nm_nodes:
            # Sort by Y to get the topmost NP Manager entry
            nm_nodes.sort(key=lambda x: x[2])
            _, cx, cy = nm_nodes[0]
            adb(f"shell input tap {cx} {cy}")
            print(f"[*] Tapped NP Manager (first) @ ({cx},{cy})")
            time.sleep(2)
            # Now tap "Just once" to open
            xml2 = get_xml(save_as="04_after_nm_tap")
            nodes2 = find_any_bounds(xml2)
            print(f"[NODES_AFTER_NM] {nodes2}")
            (
                tap_text(xml2, "Just once", "Just once") or
                tap_text(xml2, "JUST ONCE", "JUST ONCE") or
                tap_text(xml2, "Once", "Once")
            )
            time.sleep(3)
        else:
            # "Open with" dialog not visible — check if NP Manager opened directly
            print("[!] No NP Manager in Open With dialog")
            # Try direct launch with NPMainActivity
            adb(f'shell am start -n {NP_PACKAGE}/player.normal.np.activity.NPMainActivity '
                f'--es file /sdcard/Download/input.apk')
            time.sleep(5)
            xml = get_xml(save_as="04_direct_launch")

    # Step 3: Wait for project editor to load (up to 90s)
    print("[*] Waiting for project editor...")
    for i in range(45):
        time.sleep(2)
        xml = get_xml()
        if is_project_loaded(xml):
            print(f"[+] Project loaded! ({i*2}s)")
            return True
        if i % 5 == 0:
            nodes_w = find_any_bounds(xml)
            print(f"[WAIT_{i*2}s] {[n for n in nodes_w if n[0].strip()][:10]}")
            # If "Open with" dialog still showing, tap NP Manager
            if "Open with" in xml or "NP Manager" in xml:
                nm_now = [(t,x,y) for t,x,y in nodes_w if "NP Manager" in t]
                if nm_now:
                    nm_now.sort(key=lambda n: n[2])
                    adb(f"shell input tap {nm_now[0][1]} {nm_now[0][2]}")
                    print(f"[RETRY] Tapped NP Manager @ ({nm_now[0][1]},{nm_now[0][2]})")
                    time.sleep(1)
                    xml2 = get_xml()
                    tap_text(xml2, "Just once", "Just once retry") or tap_text(xml2, "Once", "Once")
                    time.sleep(2)

    print("[!] Project load timeout")
    screenshot("load_timeout")
    xml = get_xml(save_as="07_timeout")
    nodes_final = find_any_bounds(xml)
    print(f"[TIMEOUT_NODES] {[n for n in nodes_final if n[0].strip()][:30]}")
    return False

def run_tools():
    tools = [
        ("Encrypt Resource", ["Encrypt", "Resource", "\u52a0\u5bc6"]),
        ("Anti-APK Pseudo", ["Anti-APK", "Pseudo", "\u53cd\u4f2a"]),
        ("RES Anti-VT", ["RES Anti", "Anti-VT", "RES"]),
        ("Anti-Pseudo Trace", ["Anti-Pseudo", "Pseudo Trace", "\u53cd\u8ffd\u8e2a"]),
        ("Custom ARSC", ["Custom ARSC", "Customize", "\u81ea\u5b9a\u4e49"]),
        ("VM Protection", ["VM", "Virtual Machine", "\u865a\u62df\u673a"]),
        ("Dex2C", ["Dex2C", "Native", "DEX"]),
    ]
    for tool_name, keywords in tools:
        print(f"\n[*] === {tool_name} ===")
        screenshot(f"np_{tool_name.replace(' ','_')[:20]}")
        xml = get_xml()
        tools_tab = find_text(xml, "Tools") or find_text(xml, "\u5de5\u5177")
        if tools_tab:
            adb(f"shell input tap {tools_tab[0]} {tools_tab[1]}")
        else:
            tap_rel(0.7, 0.06, "Tools fallback")
        time.sleep(2)
        xml = get_xml()
        tool_tapped = False
        for kw in keywords:
            if tap_text(xml, kw, f"Tool: {kw}"):
                tool_tapped = True
                break
        if not tool_tapped:
            print(f"[!] {tool_name} not found, skip")
            back()
            continue
        time.sleep(12)
        screenshot(f"after_{tool_name.replace(' ','_')[:20]}")
        dismiss_terms()
        xml = get_xml()
        (
            tap_text(xml, "Save", "Save") or tap_text(xml, "\u4fdd\u5b58", "Save") or
            tap_text(xml, "Apply", "Apply") or tap_text(xml, "OK", "OK") or
            tap_rel(0.5, 0.92, "Save fallback")
        )
        time.sleep(3)
        back()
        time.sleep(1)
    print("\n[+] All NP tools done")
    return True

def save_output():
    print("[*] Saving output...")
    screenshot("np_before_save")
    xml = get_xml()
    (
        tap_text(xml, "Save", "Save") or tap_text(xml, "Export", "Export") or
        tap_text(xml, "Build", "Build") or tap_text(xml, "\u4fdd\u5b58", "Save") or
        tap_rel(0.5, 0.92, "Save fallback")
    )
    time.sleep(5)
    screenshot("np_after_save")
    dismiss_terms()
    paths = [
        "/sdcard/Android/data/com.wn.app.np/files/",
        "/sdcard/NPManager/output/",
        "/sdcard/Download/",
        "/data/data/com.wn.app.np/files/",
    ]
    for p in paths:
        r = adb(f"shell 'find {p} -name \"*.apk\" -type f -mmin -5 2>/dev/null | head -3'")
        if r.stdout.strip():
            for apk in r.stdout.strip().split("\n"):
                apk = apk.strip()
                if apk:
                    out = os.path.join(OUTPUT_DIR, f"np_{os.path.basename(apk)}")
                    adb(f"pull '{apk}' '{out}'")
                    print(f"[+] Pulled: {out}")
                    return out
    print("[!] No NP output found")
    return None

def run_pipeline():
    print("="*60)
    print("NP Manager v21 - Full Login + Tools Pipeline")
    print("="*60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if not wait_for_boot():
        return False

    np_apk = os.environ.get("NP_APK", os.path.expanduser("~/apk-tools/np_manager.apk"))
    if not install_apk(np_apk, NP_PACKAGE):
        print("[!] NP Manager install failed")
        return False

    launch_npm()
    if not dismiss_terms():
        print("[!] Terms stuck")

    if EMAIL and PASSWORD:
        if not handle_login():
            print("[!] Login failed, continuing...")
    else:
        print("[*] No credentials, skip login")

    if not open_apk():
        print("[!] Cannot open APK")
        return False

    run_tools()
    output = save_output()

    if output and os.path.exists(output):
        print(f"\n[+] Pipeline OK: {output}")
        return True
    print("\n[!] No output")
    return False

if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
