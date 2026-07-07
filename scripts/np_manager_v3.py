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
    """Dismiss any dialog/popup blocking the main UI: terms, update notice, announcement, ANR, etc."""
    for i in range(max_attempts):
        xml = get_xml()
        dismissed = False

        # System ANR dialogs: "isn't responding"
        # For Pixel Launcher: tap "Close app" (we don't need it, and "Wait" keeps ANR alive forever)
        # For NP Manager: tap "Wait" to keep it alive
        if "isn't responding" in xml or "not responding" in xml.lower():
            print(f"[*] ANR dialog detected (attempt {i+1})")
            anr_title = next((t for t,x,y in find_any_bounds(xml) if "isn't responding" in t or "not responding" in t.lower()), "")
            print(f"[ANR_TITLE] {anr_title[:60]}")
            if "pixel launcher" in anr_title.lower() or ("launcher" in anr_title.lower() and "np" not in anr_title.lower()):
                print("[ANR] Pixel Launcher — closing it")
                if tap_text(xml, "Close app", "ANR: Close Pixel Launcher"):
                    time.sleep(2)
                    dismissed = True
                else:
                    adb("shell input keyevent 4")
                    time.sleep(1)
                    dismissed = True
            else:
                if tap_text(xml, "Wait", "ANR: Wait"):
                    time.sleep(2)
                    dismissed = True
                elif tap_text(xml, "Close app", "ANR: Close app"):
                    time.sleep(2)
                    dismissed = True
                else:
                    adb("shell input keyevent 4")
                    time.sleep(1)
                    dismissed = True

        if not dismissed:
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

# Keywords that ONLY appear in the project editor (not the file browser or dialogs)
PROJECT_KEYWORDS = [
    "Smali", "smali",           # Smali editor tab
    "AndroidManifest",          # Manifest editor
    "classes.dex",              # Dex file
    "META-INF",                 # Project tree
    "res/",                     # Project tree
]

# Keywords from the NP Manager FUNCTION tools menu — this is also a "loaded" state
NP_TOOLS_KEYWORDS = [
    "SUPER OBFUSCATION",
    "CONTROL FLOW OBFUSCATION",
    "APK VM PROTECTION",
    "RES CONFUSION",
    "DEX STRING DECRYPTION",
    "AGAINST DEX CONFUSION",
    "CHANGE PACKAGE NAME OR CLASS NAME",
    "ONE-CLICK RANDOMLY SIGN APK",
    "OBFUSCATE APK",
    "DEX OBFUSCATION DICTIONARY EXTRACTION",
]

def is_project_loaded(xml):
    # Check classic project editor signals
    matches = [kw for kw in PROJECT_KEYWORDS if kw in xml]
    if len(matches) >= 2:
        return True
    # Also accept: NP Manager FUNCTION tools menu (we're in with the APK loaded)
    tools_matches = [kw for kw in NP_TOOLS_KEYWORDS if kw in xml]
    if len(tools_matches) >= 2:
        return True
    return False

def find_any_bounds(xml):
    """Return all (text, cx, cy) tuples from clickable nodes."""
    results = []
    for m in re.finditer(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        txt = m.group(1)
        cx = (int(m.group(2)) + int(m.group(4))) // 2
        cy = (int(m.group(3)) + int(m.group(5))) // 2
        results.append((txt, cx, cy))
    return results

def clear_text_field_and_type(field_x, field_y, new_text):
    """Clear an Android text field and type new text.
    
    Strategy: tap to focus, select all (CTRL+A), delete, then type.
    Also sends many DEL keycodes as a belt-and-suspenders approach.
    """
    # Focus the field
    adb(f"shell input tap {field_x} {field_y}")
    time.sleep(0.5)
    # Select all text in the field
    adb("shell input keyevent KEYCODE_CTRL_A")
    time.sleep(0.2)
    # Delete selected text
    adb("shell input keyevent KEYCODE_DEL")
    time.sleep(0.2)
    # Also move to end and send many DEL as fallback (in case CTRL+A didn't work)
    adb("shell input keyevent KEYCODE_MOVE_END")
    time.sleep(0.2)
    del_events = " ".join(["KEYCODE_DEL"] * 80)
    adb(f"shell input keyevent {del_events}")
    time.sleep(0.3)
    # Now type new text
    adb(f"shell input text '{new_text}'")
    time.sleep(0.5)
    print(f"[FIELD] Cleared and typed: {new_text}")


def nav_to_path_in_browser(target_path):
    """Use NP Manager's 'Jump to Path' dialog to navigate directly to a folder.
    
    Workflow:
    1. Tap path bar (shows /storage/emulated/0) -> opens 'Jump to Path' dialog
    2. Dialog has: title, text field with current path, CANCEL, CONFIRM buttons
    3. Clear the text field completely, type new path, tap CONFIRM at pre-captured coords
    """
    xml = get_xml()
    nodes = find_any_bounds(xml)
    # Find path bar node — shows /storage/emulated/0
    path_node = next(((cx, cy) for txt, cx, cy in nodes if "/storage" in txt or ("/sdcard" in txt and "Android" not in txt)), None)
    if not path_node:
        print(f"[NAV] No path bar. Nodes: {[t for t,x,y in nodes if t.strip()][:10]}")
        return False

    adb(f"shell input tap {path_node[0]} {path_node[1]}")
    time.sleep(1.5)

    # Read the dialog that just opened
    xml2 = get_xml()
    nodes2 = find_any_bounds(xml2)
    print(f"[NAV_DIALOG] {[n for n in nodes2 if n[0].strip()]}")

    if "Jump to Path" not in xml2:
        print("[NAV] 'Jump to Path' dialog not found")
        return False

    # Capture CONFIRM button position BEFORE typing (keyboard may shift it)
    confirm_pos = next(((cx, cy) for txt, cx, cy in nodes2 if txt == "CONFIRM"), None)
    print(f"[NAV_CONFIRM_POS] {confirm_pos}")

    # Find the text field in the dialog
    path_field_pos = next(((cx, cy) for txt, cx, cy in nodes2 if "/storage" in txt or "/sdcard" in txt), None)
    if not path_field_pos:
        print("[NAV] No path field found in dialog")
        return False

    # Clear field and type target path
    clear_text_field_and_type(path_field_pos[0], path_field_pos[1], target_path)

    # Read the field content after typing to verify
    xml_check = get_xml()
    nodes_check = find_any_bounds(xml_check)
    field_now = next((t for t,x,y in nodes_check if "/sdcard" in t or "/storage" in t or "Android" in t), "?")
    print(f"[NAV_FIELD_AFTER_TYPE] '{field_now}'")

    # CRITICAL: Dismiss the soft keyboard BEFORE tapping CONFIRM
    # The keyboard appears after typing and covers the dialog buttons at y=1360.
    # Press Back to hide keyboard without closing the dialog.
    adb("shell input keyevent KEYCODE_BACK")
    time.sleep(0.8)

    # Re-read XML to get CONFIRM coords after keyboard dismissal
    xml_nodialog = get_xml()
    nodes_nodialog = find_any_bounds(xml_nodialog)
    print(f"[NAV_AFTER_KB_DISMISS] {[n for n in nodes_nodialog if n[0].strip()][:8]}")
    confirm_pos2 = next(((cx, cy) for txt, cx, cy in nodes_nodialog if txt == "CONFIRM"), confirm_pos)
    print(f"[NAV_CONFIRM_POS2] {confirm_pos2}")

    # Tap CONFIRM
    if confirm_pos2:
        adb(f"shell input tap {confirm_pos2[0]} {confirm_pos2[1]}")
        print(f"[NAV] Tapped CONFIRM @ {confirm_pos2}")
        time.sleep(2)
    else:
        adb("shell input keyevent 66")
        print("[NAV] Pressed Enter (no CONFIRM found)")
        time.sleep(2)

    # Check where we ended up
    xml3 = get_xml()
    nodes3 = find_any_bounds(xml3)
    curr = next((t for t,x,y in nodes3 if "/storage" in t or "/sdcard" in t), "unknown")
    print(f"[NAV_RESULT] Now at: {curr}")
    return "files" in curr or target_path in curr


def open_apk():
    print("[*] Opening APK via NP Manager...")
    if not os.path.exists(os.path.expanduser(INPUT_APK)):
        print("[!] Input APK missing")
        return False

    # Push APK to a location NP Manager can access via Intent
    DL_DIR = "/sdcard/Download"
    NP_FILES_DIR = f"/sdcard/Android/data/{NP_PACKAGE}/files"
    adb(f"shell mkdir -p {NP_FILES_DIR}")

    # Push to NP's own app-private dir (it can always read its own files dir)
    r_push = adb(f"push '{INPUT_APK}' {NP_FILES_DIR}/input.apk")
    print(f"[PUSH_NP] {r_push.stdout.strip()[:150]} {r_push.stderr.strip()[:150]}")

    # Also push to Download
    r_push_dl = adb(f"push '{INPUT_APK}' {DL_DIR}/input.apk")
    print(f"[PUSH_DL] {r_push_dl.stdout.strip()[:150]} {r_push_dl.stderr.strip()[:150]}")

    time.sleep(1)
    r_ls = adb(f"shell ls -la {NP_FILES_DIR}/ {DL_DIR}/ 2>&1")
    print(f"[LS_BOTH] {r_ls.stdout.strip()[:600]}")

    # Grant MANAGE_EXTERNAL_STORAGE so NP Manager's file browser can see all files
    r_grant = adb(f"shell appops set {NP_PACKAGE} MANAGE_EXTERNAL_STORAGE allow")
    print(f"[GRANT_STORAGE] rc={r_grant.returncode} {r_grant.stderr.strip()[:100]}")

    # STRATEGY: Send a VIEW Intent directly to NP Manager with the APK file URI.
    # This bypasses the file browser entirely and directly opens the APK as a project.
    # NP Manager handles android.intent.action.VIEW with application/vnd.android.package-archive.
    APK_ON_DEVICE = f"{NP_FILES_DIR}/input.apk"
    print(f"[*] Sending VIEW Intent for {APK_ON_DEVICE}...")

    # Method 1: am start with file:// URI (NP Manager's own files dir)
    r_intent = adb(
        f"shell am start -n {NP_PACKAGE}/.activity.NPMainActivity"
        f" -a android.intent.action.VIEW"
        f" -t application/vnd.android.package-archive"
        f" -d file://{APK_ON_DEVICE}"
        f" --grant-read-uri-permission"
    )
    print(f"[INTENT_RESULT] {r_intent.stdout.strip()[:200]} {r_intent.stderr.strip()[:100]}")
    time.sleep(5)

    screenshot("after_intent")
    xml = get_xml(save_as="01_after_intent")
    nodes_intent = find_any_bounds(xml)
    print(f"[NODES_INTENT] {[n for n in nodes_intent if n[0].strip()][:15]}")

    if is_project_loaded(xml):
        print("[+] Project loaded via Intent!")
        return True

    # Method 2: Try ApkInstallerActivity which NP Manager uses for its file picker
    r_intent2 = adb(
        f"shell am start -n {NP_PACKAGE}/.activity.ApkInstallerActivity"
        f" -a android.intent.action.VIEW"
        f" -t application/vnd.android.package-archive"
        f" -d file://{APK_ON_DEVICE}"
        f" --grant-read-uri-permission"
    )
    print(f"[INTENT2_RESULT] {r_intent2.stdout.strip()[:200]}")
    time.sleep(5)

    screenshot("after_intent2")
    xml = get_xml(save_as="01b_after_intent2")
    nodes2 = find_any_bounds(xml)
    print(f"[NODES_INTENT2] {[n for n in nodes2 if n[0].strip()][:15]}")

    if is_project_loaded(xml):
        print("[+] Project loaded via Intent2!")
        return True

    # Method 3: Dismiss dialogs and use the file browser to navigate
    # Re-launch NP Manager fresh
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(2)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(8)

    # Aggressively clear ALL ANR/dialogs — System UI / Pixel Launcher ANR can persist
    # For Pixel Launcher ANR: tap "Close app" (kills it cleanly; we don't need it).
    # For NP Manager ANR: tap "Wait" to keep it alive.
    for _ in range(15):
        xml_anr = get_xml()
        if "isn't responding" in xml_anr or "not responding" in xml_anr.lower():
            nodes_anr = find_any_bounds(xml_anr)
            # Determine which app is ANR-ing
            anr_title = next((t for t,x,y in nodes_anr if "isn't responding" in t or "not responding" in t.lower()), "")
            if "pixel launcher" in anr_title.lower() or "launcher" in anr_title.lower():
                # Kill Pixel Launcher — we don't need it
                tap_text(xml_anr, "Close app", "Pixel Launcher ANR close")
                print(f"[ANR] Closed Pixel Launcher")
            else:
                tap_text(xml_anr, "Wait", "ANR aggressive dismiss")
            time.sleep(2)
        else:
            break

    # Dismiss ALL dialogs
    dismiss_all_dialogs(max_attempts=15)
    time.sleep(2)

    screenshot("np_main_screen")
    xml = get_xml(save_as="02_main_screen")
    nodes_main = find_any_bounds(xml)
    print(f"[NODES_MAIN] {[n for n in nodes_main if n[0].strip()][:15]}")

    # Navigate to NP files dir — retry up to 3 times in case ANR blocks dialog
    nav_ok = False
    for nav_attempt in range(3):
        # Clear any lingering ANRs before each attempt
        # For Pixel Launcher ANR: close it; for NP Manager ANR: wait
        for _ in range(8):
            xml_chk = get_xml()
            if "isn't responding" in xml_chk or "not responding" in xml_chk.lower():
                nodes_chk = find_any_bounds(xml_chk)
                anr_title_chk = next((t for t,x,y in nodes_chk if "isn't responding" in t or "not responding" in t.lower()), "")
                if "pixel launcher" in anr_title_chk.lower() or "launcher" in anr_title_chk.lower():
                    tap_text(xml_chk, "Close app", f"Pixel Launcher ANR pre-nav {nav_attempt}")
                    print(f"[ANR] Closed Pixel Launcher pre-nav")
                else:
                    tap_text(xml_chk, "Wait", f"ANR pre-nav attempt {nav_attempt}")
                time.sleep(2)
            else:
                break
        print(f"[*] Navigating to NP files dir (attempt {nav_attempt+1})...")
        nav_ok = nav_to_path_in_browser(NP_FILES_DIR)
        time.sleep(3)
        # Verify we actually navigated
        xml_nav = get_xml()
        nodes_nav = find_any_bounds(xml_nav)
        curr = next((t for t,x,y in nodes_nav if NP_FILES_DIR in t or "com.wn.app.np" in t), None)
        if curr:
            print(f"[NAV_SUCCESS] At {curr} on attempt {nav_attempt+1}")
            break
        print(f"[NAV_RETRY] Still not at NP files dir after attempt {nav_attempt+1}, retrying...")
        time.sleep(3)

    screenshot("inside_np_files")
    xml = get_xml(save_as="03_np_files_contents")
    nodes_f = find_any_bounds(xml)
    visible = [n for n in nodes_f if n[0].strip()]
    print(f"[NODES_NP_FILES] {visible}")

    if is_project_loaded(xml):
        print("[+] Project editor already showing!")
        return True

    # Check where we ended up after navigation
    curr_path = next((t for t,x,y in visible if "/storage" in t or "/sdcard" in t), "unknown")
    print(f"[CURR_PATH] {curr_path}")

    # Tap input.apk if visible
    apk_tapped = False
    for txt, cx, cy in nodes_f:
        if "input" in txt.lower() and ".apk" in txt.lower():
            adb(f"shell input tap {cx} {cy}")
            print(f"[*] Tapped APK '{txt}' @ ({cx},{cy})")
            apk_tapped = True
            time.sleep(3)
            break

    if not apk_tapped:
        # Also accept bare "input" filename
        for txt, cx, cy in nodes_f:
            if txt.strip().lower() == "input.apk" or (txt.strip().lower().startswith("input") and ".apk" in txt.lower()):
                adb(f"shell input tap {cx} {cy}")
                print(f"[*] Tapped APK fallback '{txt}' @ ({cx},{cy})")
                apk_tapped = True
                time.sleep(3)
                break

    if not apk_tapped:
        print(f"[!] input.apk not visible in NP files dir.")
        r_ls2 = adb(f"shell ls -la {NP_FILES_DIR}/ /sdcard/Download/ 2>&1")
        print(f"[LS_CHECK] {r_ls2.stdout.strip()[:400]}")
    else:
        # After tapping input.apk, NP Manager may show a context/action dialog.
        # Print ALL nodes so we know exactly what to tap.
        xml3 = get_xml(save_as="04_after_apk_tap")
        nodes3 = find_any_bounds(xml3)
        print(f"[NODES_AFTER_TAP] {[n for n in nodes3 if n[0].strip()]}")
        if is_project_loaded(xml3):
            print("[+] Project editor opened immediately!")
            return True
        # NP Manager shows an APK info screen with FUNCTION / VIEW / INSTALL buttons.
        # FUNCTION = opens the project editor / tools menu — tap it first.
        tapped_dialog = False
        for kw in ["FUNCTION", "功能", "Decompile", "decompile", "反编译", "Open project",
                   "Project", "Editor", "OK", "确定", "Open", "Start", "开始", "Import", "导入"]:
            if tap_text(xml3, kw, f"APK info: {kw}"):
                tapped_dialog = True
                time.sleep(5)
                break
        if not tapped_dialog:
            print(f"[!] No known dialog option found after tap. Will wait for editor...")

    # Step 3: Wait for project editor/decompile UI to load (up to 120s)
    # NP Manager decompiles the APK which takes 20-60s on the emulator.
    # IMPORTANT: Tapping FUNCTION may kick back to the login screen (session re-check).
    # Detect this and re-login, then we'll end up in the FUNCTION/tools view.
    print("[*] Waiting for project editor...")
    relogin_done = False
    for i in range(60):
        time.sleep(2)
        xml = get_xml()
        # Dismiss any ANR that reappears
        if "isn't responding" in xml or "not responding" in xml.lower():
            nodes_anr_w = find_any_bounds(xml)
            anr_title_w = next((t for t,x,y in nodes_anr_w if "isn't responding" in t or "not responding" in t.lower()), "")
            if "pixel launcher" in anr_title_w.lower() or "launcher" in anr_title_w.lower():
                tap_text(xml, "Close app", "Pixel Launcher ANR wait loop")
                print("[ANR] Closed Pixel Launcher in wait loop")
            else:
                tap_text(xml, "Wait", "ANR Wait loop")
            time.sleep(1)
            continue
        if is_project_loaded(xml):
            print(f"[+] Project loaded! ({i*2}s)")
            return True
        nodes_w = find_any_bounds(xml)
        visible = [n for n in nodes_w if n[0].strip()]
        texts = [t for t,x,y in visible]
        if i % 5 == 0:
            print(f"[WAIT_{i*2}s] {visible[:12]}")

        # Detect the "Delete a signed-in device" / "DOUBLE-ENDED LOGIN" dialog
        # shown after re-login when the account has too many devices logged in.
        # Tap DELETE on the FIRST listed device to free up a slot.
        # After DELETE, NP Manager returns to the login screen with credentials pre-filled —
        # just tap LOGIN again (no need to re-enter credentials).
        if any("double-ended login" in t.lower() or "delete a signed-in device" in t.lower() for t,x,y in visible):
            print("[*] DOUBLE-ENDED LOGIN dialog — deleting oldest device slot...")
            # Tap the first DELETE button (oldest device = first in list)
            for t, x, y in visible:
                if t.strip().upper() == "DELETE":
                    adb(f"shell input tap {x} {y}")
                    print(f"[*] Tapped DELETE @ ({x},{y})")
                    time.sleep(4)
                    break
            # After DELETE, dismiss any confirmation dialog ("OK", "确定", etc.)
            xml_dd = get_xml()
            nodes_dd = find_any_bounds(xml_dd)
            print(f"[AFTER_DELETE] {[n for n in nodes_dd if n[0].strip()][:8]}")
            for kw in ["OK", "确定", "CONFIRM", "Yes"]:
                if tap_text(xml_dd, kw, f"Delete confirm: {kw}"):
                    time.sleep(2)
                    xml_dd = get_xml()
                    nodes_dd = find_any_bounds(xml_dd)
                    break
            screenshot("after_delete_device")
            # NP Manager returns to login screen with credentials already filled.
            # Detect this and tap LOGIN immediately.
            texts_dd = [t for t,x,y in nodes_dd if t.strip()]
            if "LOGIN" in texts_dd and any("@" in t or "••" in t for t,x,y in nodes_dd):
                print("[*] Back on login screen after DELETE — tapping LOGIN (creds pre-filled)...")
                for t2, x2, y2 in nodes_dd:
                    if t2.strip() == "LOGIN":
                        adb(f"shell input tap {x2} {y2}")
                        print(f"[RELOGIN2_LOGIN] tapped @ ({x2},{y2})")
                        time.sleep(8)
                        break
                else:
                    # Fallback: tap at known LOGIN position
                    adb("shell input tap 540 1302")
                    print("[RELOGIN2_LOGIN] fallback tap @ (540,1302)")
                    time.sleep(8)
                relogin_done = True
            continue

        # Detect login screen shown by FUNCTION's session check and re-login
        if not relogin_done and ("LOGIN" in texts or "login" in texts) and "Please enter" in " ".join(texts):
            print("[*] FUNCTION triggered login re-check — re-logging in...")
            # The re-login screen may show placeholder hints OR pre-filled content.
            # Strategy: find email field by placeholder OR by "@" in text, then
            # use clear_text_field_and_type (which does CTRL+A + 80xDEL) to wipe it.
            all_nodes = find_any_bounds(xml)
            # Identify email field: placeholder text or a node containing "@"
            email_node = None
            for t, x, y in all_nodes:
                if "account number" in t.lower() or "email address" in t.lower() or "@" in t:
                    email_node = (x, y)
                    print(f"[RELOGIN_EMAIL_FIELD] found at ({x},{y}): {t[:40]}")
                    break
            # Identify password field: placeholder "Please enter a password" (not "Forgot password")
            pass_node = None
            for t, x, y in all_nodes:
                if "please enter a password" in t.lower():
                    pass_node = (x, y)
                    print(f"[RELOGIN_PASS_FIELD] found at ({x},{y}): {t[:40]}")
                    break
            if not pass_node:
                # Fallback: any "password" node that's not "Forgot"
                for t, x, y in all_nodes:
                    if "password" in t.lower() and "forgot" not in t.lower() and x > 400:
                        pass_node = (x, y)
                        print(f"[RELOGIN_PASS_FIELD] fallback at ({x},{y}): {t[:40]}")
                        break
            # Identify LOGIN button — must be exactly "LOGIN" (uppercase, not title "login")
            login_node = None
            for t, x, y in all_nodes:
                if t.strip() == "LOGIN":  # exact uppercase match — not the title "login"
                    login_node = (x, y)
                    break
            if not login_node:
                # fallback: any node whose text is all caps LOGIN
                for t, x, y in all_nodes:
                    if t.strip().upper() == "LOGIN" and t.strip() != "login":
                        login_node = (x, y)
                        break
            print(f"[RELOGIN_LOGIN_NODE] {login_node}")
            # Clear and fill email
            ex, ey = email_node if email_node else (540, 936)
            clear_text_field_and_type(ex, ey, EMAIL)
            time.sleep(1.5)
            # Dismiss keyboard before tapping password field
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(0.5)
            # Verify email field and show intermediate state
            xml_mid = get_xml()
            nodes_mid = find_any_bounds(xml_mid)
            print(f"[RELOGIN_MID] {[n for n in nodes_mid if n[0].strip()][:8]}")
            # Re-find password field in fresh XML (positions may shift)
            for t2, x2, y2 in nodes_mid:
                if "please enter a password" in t2.lower():
                    pass_node = (x2, y2)
                    print(f"[RELOGIN_PASS_REFOUND] ({x2},{y2}): {t2[:30]}")
                    break
            # Clear and fill password
            px, py = pass_node if pass_node else (540, 1096)
            clear_text_field_and_type(px, py, PASSWORD)
            time.sleep(1.5)
            # Dismiss keyboard
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(0.5)
            # Re-read XML to find LOGIN button in final state
            xml_final = get_xml()
            nodes_final2 = find_any_bounds(xml_final)
            print(f"[RELOGIN_BEFORE_LOGIN] {[n for n in nodes_final2 if n[0].strip()][:10]}")
            # Tap LOGIN
            lx, ly = login_node if login_node else (540, 1302)
            print(f"[RELOGIN_LOGIN_BTN] tapping LOGIN @ ({lx},{ly})")
            adb(f"shell input tap {lx} {ly}")
            time.sleep(8)
            relogin_done = True
            screenshot("after_relogin")
            xml = get_xml(save_as="relogin_state")
            nodes_rl = find_any_bounds(xml)
            print(f"[RELOGIN_STATE] {[n for n in nodes_rl if n[0].strip()][:12]}")
            continue

        # Tap any decompile/open action dialog that appears mid-wait
        for kw in ["Decompile", "decompile", "反编译", "OK", "确定", "Open", "Continue", "开始", "Start"]:
            if any(t.strip() == kw for t, x, y in visible):
                tap_text(xml, kw, f"Dialog mid-wait: {kw}")
                time.sleep(3)
                break

        # Detect that we're still on the root file browser (nav failed due to ANR earlier).
        # ANR may have cleared by now — retry nav + APK tap from here.
        curr_paths = [t for t,x,y in visible if "/storage/emulated/0" == t or t == "/storage/emulated/0"]
        apk_visible = any("input" in t.lower() and ".apk" in t.lower() for t,x,y in visible)
        func_visible = any(t.strip() == "FUNCTION" for t,x,y in visible)
        if curr_paths and not apk_visible and not func_visible and i > 0 and i % 10 == 0:
            print(f"[WAIT_RENAVIGATING] Still at root browser, retry nav at {i*2}s...")
            nav_to_path_in_browser(NP_FILES_DIR)
            time.sleep(3)
            xml2 = get_xml()
            nodes2 = find_any_bounds(xml2)
            for txt2, cx2, cy2 in nodes2:
                if "input" in txt2.lower() and ".apk" in txt2.lower():
                    adb(f"shell input tap {cx2} {cy2}")
                    print(f"[WAIT_TAPPED_APK] '{txt2}' @ ({cx2},{cy2})")
                    time.sleep(4)
                    xml3 = get_xml()
                    for kw in ["FUNCTION", "Decompile", "OK"]:
                        if tap_text(xml3, kw, f"Post-renav: {kw}"):
                            time.sleep(4)
                            break
                    break

    print("[!] Project load timeout")
    screenshot("load_timeout")
    xml = get_xml(save_as="07_timeout")
    nodes_final = find_any_bounds(xml)
    print(f"[TIMEOUT_NODES] {[n for n in nodes_final if n[0].strip()][:30]}")
    return False

def find_tool_on_screen(tool_name, xml):
    """Find a tool by exact text match in the XML. Returns (x, y) or None."""
    nodes = find_any_bounds(xml)
    for t, x, y in nodes:
        if t.strip() == tool_name:
            return (x, y)
    return None

def scroll_tool_list_and_tap(tool_name):
    """Scroll the tools list to find and tap a tool. Returns True if tapped."""
    # Try visible screen first
    xml = get_xml()
    pos = find_tool_on_screen(tool_name, xml)
    if pos:
        adb(f"shell input tap {pos[0]} {pos[1]}")
        print(f"[TOOL_TAP] '{tool_name}' @ {pos}")
        return True
    # Scroll down and retry (tool list can be long)
    for _ in range(4):
        scroll_rel(0.5, 0.8, 0.5, 0.3, 600)
        time.sleep(1)
        xml = get_xml()
        pos = find_tool_on_screen(tool_name, xml)
        if pos:
            adb(f"shell input tap {pos[0]} {pos[1]}")
            print(f"[TOOL_TAP_SCROLL] '{tool_name}' @ {pos}")
            return True
    # Scroll back to top and retry
    for _ in range(5):
        scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
        time.sleep(0.5)
    return False

def wait_for_apk_info_and_enter_function():
    """Wait for NP Manager APK info screen (FUNCTION/VIEW/INSTALL), then tap FUNCTION.
    Handles login re-check. Returns True if we reach the tools list."""
    print("[REENTER] Waiting for APK info screen...")
    for wait_try in range(12):  # up to 24s
        time.sleep(2)
        xml = get_xml()
        texts_w = [t.strip() for t,x,y in find_any_bounds(xml) if t.strip()]
        # Already on tools list
        if any(kw in xml for kw in NP_TOOLS_KEYWORDS):
            print("[REENTER] Already on tools list")
            return True
        # APK info screen — tap FUNCTION
        if "FUNCTION" in texts_w:
            print(f"[REENTER] APK info screen found (try {wait_try+1}), tapping FUNCTION...")
            tap_text(xml, "FUNCTION", "REENTER FUNCTION")
            time.sleep(5)
            # Handle login re-check
            xml2 = get_xml()
            if any(t in xml2 for t in ["Please enter", "LOGIN", "login", "Password"]):
                print("[REENTER] Login re-check — re-logging in...")
                relogin()
                time.sleep(3)
                xml2 = get_xml()
            if any(kw in xml2 for kw in NP_TOOLS_KEYWORDS):
                print("[REENTER] Back on tools list")
                return True
            # FUNCTION might have gone to a different state — keep waiting
            continue
        # Login screen appeared
        if any(t in xml for t in ["Please enter", "LOGIN", "login"]):
            print("[REENTER] Login screen — re-logging in...")
            relogin()
            time.sleep(3)
            continue
        print(f"[REENTER] Still waiting... ({texts_w[:3]})")
    print("[REENTER] Gave up waiting for APK info screen")
    return False

def recover_from_file_browser():
    """Called when file browser is detected after a tool completes.
    Press BACK repeatedly to exit all file browser levels back to APK info screen."""
    print("[FILE_BROWSER] Tool done — pressing BACK x10 to exit file browser levels...")
    # The file browser nests: files/ → com.wn.app.np/ → Android/data/ → Android/ → sdcard/ → / → APK info
    # Press BACK up to 10 times, stopping when we detect APK info screen or tools list
    for back_n in range(10):
        adb("shell input keyevent KEYCODE_BACK")
        time.sleep(2)
        xml_b = get_xml()
        texts_b = [t.strip() for t,x,y in find_any_bounds(xml_b) if t.strip()]
        print(f"[FILE_BROWSER] BACK {back_n+1}: {texts_b[:3]}")
        # Reached tools list
        if any(kw in xml_b for kw in NP_TOOLS_KEYWORDS):
            print("[FILE_BROWSER] Reached tools list")
            return True
        # Reached APK info screen (FUNCTION button visible)
        if "FUNCTION" in texts_b and ("VIEW" in texts_b or "INSTALL" in texts_b):
            print(f"[FILE_BROWSER] Reached APK info screen after {back_n+1} BACKs")
            return wait_for_apk_info_and_enter_function()
        # Reached home screen — re-launch NP Manager
        HOME_IND = ["Gmail", "Chrome", "YouTube", "Phone", "Messages"]
        if sum(1 for h in HOME_IND if h in xml_b) >= 2:
            print("[FILE_BROWSER] Reached home screen — launching NP Manager APK info...")
            adb("shell am start -n com.wn.app.np/.activity.ApkInstallerActivity"
                " -a android.intent.action.VIEW"
                " -d file:///sdcard/Android/data/com.wn.app.np/files/input.apk"
                " -t application/vnd.android.package-archive")
            time.sleep(7)
            return wait_for_apk_info_and_enter_function()
        # Still in file browser — press BACK again (loop continues)
    print("[FILE_BROWSER] Gave up — pressing HOME and re-launching")
    adb("shell input keyevent KEYCODE_HOME")
    time.sleep(2)
    adb("shell am start -n com.wn.app.np/.activity.ApkInstallerActivity"
        " -a android.intent.action.VIEW"
        " -d file:///sdcard/Android/data/com.wn.app.np/files/input.apk"
        " -t application/vnd.android.package-archive")
    time.sleep(7)
    return wait_for_apk_info_and_enter_function()

def handle_tool_result():
    """After tapping a tool, wait for completion and dismiss any result dialog.
    Returns True when done (tools list is accessible again)."""
    time.sleep(3)
    submitted = False  # track if we already tapped CONFIRM/START

    for attempt in range(40):  # up to ~80s total (mix of 2s and 4s sleeps)
        xml = get_xml()
        nodes = find_any_bounds(xml)
        texts = [t.strip() for t,x,y in nodes if t.strip()]
        print(f"[TOOL_RESULT] {texts[:8]}")

        # === COMPLETION STATES ===

        # 1. Tools list is visible — tool finished and returned automatically
        if any(kw in xml for kw in NP_TOOLS_KEYWORDS):
            print("[TOOL_RESULT] Back on tools list — done")
            return True

        # 2. File browser appeared — tool saved output, escape and re-enter
        if ("Folder：" in xml or "File：" in xml) and ("/sdcard" in xml or "com.wn.app.np" in xml):
            print("[TOOL_RESULT] File browser — escaping via am start to APK info...")
            if recover_from_file_browser():
                return True
            # If still not recovered, keep looping — might need another attempt
            continue

        # 3. Home screen (Gmail, Photos, Chrome etc) — NP Manager was closed, re-launch
        HOME_INDICATORS = ["Gmail", "Chrome", "YouTube", "Phone"]
        if sum(1 for h in HOME_INDICATORS if h in xml) >= 2:
            print("[TOOL_RESULT] Home screen — re-launching NP Manager...")
            if recover_from_file_browser():
                return True
            continue

        # 4. APK info screen (FUNCTION/VIEW/INSTALL) — tap FUNCTION directly
        if "FUNCTION" in texts and ("VIEW" in texts or "INSTALL" in texts):
            print("[TOOL_RESULT] APK info screen — tapping FUNCTION...")
            if wait_for_apk_info_and_enter_function():
                return True
            continue

        # === CONFIG / SETUP SCREENS ===

        # 4. "General obfuscation configuration" choice → tap it
        if any("general obfuscation" in t.lower() for t in texts):
            tap_text(xml, "General obfuscation configuration", "Tool config: General")
            print("[TOOL_CONFIG] Chose General obfuscation configuration")
            time.sleep(3)
            submitted = False  # reset — now on config form
            continue

        # 5. CONFIRM / START on a config form → submit (only once per submission cycle)
        submit_kws = ["CONFIRM", "Confirm", "START", "Start", "开始", "Run", "RUN",
                      "Execute", "EXECUTE"]
        tapped_submit = False
        for kw in submit_kws:
            if kw in texts:
                if not submitted:
                    tap_text(xml, kw, f"Tool submit: {kw}")
                    submitted = True
                    tapped_submit = True
                    time.sleep(6)
                else:
                    # Still seeing CONFIRM after submission — re-tap to push through
                    tap_text(xml, kw, f"Tool re-submit: {kw}")
                    tapped_submit = True
                    time.sleep(6)
                break
        if tapped_submit:
            continue

        # 6. Progress indicator (编译中 = "compiling", percentage, X/Y numeric counters)
        # Only match actual numeric progress like "7396/7397" or "45%" — not file paths
        import re as _re
        if any("编译中" in t or (_re.search(r'\d+%', t) and len(t) < 10)
               or _re.search(r'\d+/\d+', t) for t in texts):
            print(f"[TOOL_RESULT] Processing... ({texts[:3]})")
            time.sleep(4)
            continue

        # 7. Final OK/Done/Success dialogs
        for kw in ["OK", "确定", "Done", "DONE", "Success", "完成", "Close", "CLOSE"]:
            if kw in texts:
                tap_text(xml, kw, f"Tool done: {kw}")
                time.sleep(3)
                return True

        # Still waiting...
        time.sleep(2)

    print("[TOOL_RESULT] Timeout — trying to recover to tools list")
    # Press BACK to escape any sub-screen
    adb("shell input keyevent KEYCODE_BACK")
    time.sleep(2)
    xml_chk = get_xml()
    if "FUNCTION" in xml_chk:
        reenter_function_tools()
    elif not any(kw in xml_chk for kw in NP_TOOLS_KEYWORDS):
        adb("shell input keyevent KEYCODE_BACK")
        time.sleep(2)
    return False

def run_tools():
    """Tap 7 anti-detection tools from the NP Manager FUNCTION tools list."""
    # Actual tool names as they appear in the tools list (from live run 27 observation).
    # Ordered from most impactful to least, to maximize FUD even if some fail.
    TOOLS_TO_RUN = [
        "SUPER OBFUSCATION",
        "CONTROL FLOW OBFUSCATION",
        "RES CONFUSION 3.0",
        "APK VM PROTECTION",
        "DEX STRING DECRYPTION",
        "CHANGE PACKAGE NAME OR CLASS NAME",
        "ONE-CLICK RANDOMLY SIGN APK",
    ]

    print("\n[*] === Starting NP Manager tools ===")
    # Scroll to top of tools list first
    for _ in range(5):
        scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
        time.sleep(0.3)
    time.sleep(1)

    for tool_name in TOOLS_TO_RUN:
        print(f"\n[TOOL] >>> {tool_name}")
        # Ensure we're on the tools list — press BACK up to 3 times if needed
        for back_try in range(3):
            xml_chk = get_xml()
            if any(kw in xml_chk for kw in NP_TOOLS_KEYWORDS):
                break
            print(f"[TOOL] Not on tools list (try {back_try+1}) — pressing BACK...")
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(3)
        # Scroll to top of tools list
        for _ in range(6):
            scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
            time.sleep(0.3)
        time.sleep(1.5)
        screenshot(f"before_{tool_name[:20].replace(' ','_')}")
        tapped = scroll_tool_list_and_tap(tool_name)
        if not tapped:
            print(f"[TOOL] Not found: {tool_name} — skipping")
            continue
        time.sleep(3)
        screenshot(f"after_tap_{tool_name[:20].replace(' ','_')}")
        handle_tool_result()
        screenshot(f"done_{tool_name[:20].replace(' ','_')}")

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
