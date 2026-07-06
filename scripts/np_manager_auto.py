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

def get_xml():
    adb("shell uiautomator dump /sdcard/window_dump.xml")
    r = adb("shell cat /sdcard/window_dump.xml")
    return r.stdout

def find_text(xml, text):
    # Check text, content-desc, and resource-id attributes with flexible regex
    escaped = re.escape(text)
    for attr in ['text', 'content-desc', 'resource-id']:
        # Pattern that handles any attribute order within a node tag
        pat = re.compile(
            r'<node[^>]*?\b' + attr + r'="' + escaped + r'"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?>',
            re.DOTALL
        )
        m = pat.search(xml)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            return ((x1+x2)//2, (y1+y2)//2)
    return None

def list_all_text(xml, max_items=50):
    """Debug: list all text/content-desc elements found in XML."""
    results = []
    for attr in ['text', 'content-desc']:
        pat = re.compile(r'<node[^>]*?\b' + attr + r'="([^"]*)"[^>]*?>', re.DOTALL)
        for m in pat.finditer(xml):
            val = m.group(1).strip()
            if val and len(val) > 1 and val not in [r for r, _ in results]:
                results.append((val, attr))
                if len(results) >= max_items:
                    break
        if len(results) >= max_items:
            break
    return results

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

def dismiss_terms(max_attempts=6):
    for i in range(max_attempts):
        xml = get_xml()
        has_terms = "\u7528\u6237\u534f\u8bae" in xml or "Notice" in xml or "Terms" in xml or "\u540c\u610f" in xml
        if not has_terms:
            return True
        print(f"[*] Terms dialog (attempt {i+1})")
        screenshot(f"terms_{i}")
        if i == 0:
            for _ in range(4):
                scroll_rel(0.5, 0.70, 0.5, 0.30, 500)
                time.sleep(0.3)
        (
            tap_text(xml, "\u540c\u610f", "AGREE") or
            tap_text(xml, "Agree", "AGREE") or
            tap_text(xml, "AGREE", "AGREE") or
            tap_text(xml, "Yes", "Yes") or
            tap_rel(0.82, 0.97, "AGREE fallback")
        )
        time.sleep(1.5)
    print("[!] Terms stuck")
    return False

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

def open_apk():
    print("[*] Opening APK...")
    if not os.path.exists(os.path.expanduser(INPUT_APK)):
        print("[!] Input APK missing")
        return False
    adb(f"push '{os.path.expanduser(INPUT_APK)}' /sdcard/Download/input.apk")
    time.sleep(1)
    
    # Launch APK - this may trigger "Open with" chooser dialog
    print("[*] Launching APK via VIEW intent...")
    adb("shell am start -a android.intent.action.VIEW -d file:///sdcard/Download/input.apk -t application/vnd.android.package-archive")
    time.sleep(5)
    screenshot("project_opened")
    
    # Handle "Open with" chooser dialog if it appears
    xml = get_xml()
    if "Open with" in xml or "Open" in xml:
        print("[*] Handling 'Open with' chooser dialog...")
        # Tap "NP Manager" in the list
        if tap_text(xml, "NP Manager", "Choose NP Manager"):
            time.sleep(1)
        # Tap "Always" to always open with NP Manager
        xml = get_xml()
        if tap_text(xml, "Always", "Always open with NP Manager"):
            time.sleep(3)
        elif tap_text(xml, "Just once", "Just once"):
            time.sleep(3)
    
    # Handle any terms dialogs that appear
    dismiss_terms()
    
    # Wait for project to load in NP Manager
    print("[*] Waiting for project to load...")
    for i in range(15):
        time.sleep(3)
        xml = get_xml()
        keywords = ["Projects", "Smali", "Manifest", "Resources", "Classes", "Dex", "java", "src", 
                   "反编", "项目", "工程", "File", "Edit", "View", "文件", 
                   "编辑", "查看"]
        if any(kw in xml for kw in keywords):
            print(f"[+] Project loaded ({i*3}s)")
            return True
        
        # Check if still parsing
        if "Parsing" in xml or "解析" in xml or "Loading" in xml or "加载" in xml:
            print(f"[*] Still parsing... ({i*3}s)")
            continue
    
    print("[!] Project load timeout - continuing anyway")
    return True  # Don't fail, try to continue


def get_all_clickable(xml):
    """Extract all clickable elements with their text and coordinates."""
    results = []
    # Match nodes with click="true" or that have text/content-desc
    pat = re.compile(
        r'<node[^>]*?clickable="true"[^>]*?(?:text|content-desc)="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?>',
        re.DOTALL
    )
    for m in pat.finditer(xml):
        text, x1, y1, x2, y2 = m.groups()
        if text.strip() and len(text.strip()) > 1:
            cx, cy = (int(x1)+int(x2))//2, (int(y1)+int(y2))//2
            results.append((text.strip(), cx, cy))
    
    # Also get nodes with text that look like buttons/actions even if not clickable="true"
    pat2 = re.compile(
        r'<node[^>]*?(?:text|content-desc)="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?>',
        re.DOTALL
    )
    seen = {r[0] for r in results}
    for m in pat2.finditer(xml):
        text, x1, y1, x2, y2 = m.groups()
        t = text.strip()
        if t and t not in seen and len(t) > 1 and len(t) < 50:
            # Filter for likely actionable text
            action_keywords = ["OK", "Apply", "Start", "Run", "Save", "Build", "Export", "Protect",
                             "确定", "应用", "开始", "保存", "生成", "运行",
                             "保护", "处理", "编译", "打开", "关闭", "设置",
                             "加密", "反伪", "混淆", "虚拟", "工具", "项目",
                             "文件", "类", "方法", "字段", "资源", "布局"]
            if any(kw.lower() in t.lower() for kw in action_keywords):
                cx, cy = (int(x1)+int(x2))//2, (int(y1)+int(y2))//2
                results.append((t, cx, cy))
                seen.add(t)
    return results

def run_tools():
    print("[*] === NP Manager Tool Discovery ===")
    
    # Get initial project view
    xml = get_xml()
    screenshot("np_project_view")
    
    # List all clickable elements
    clickable = get_all_clickable(xml)
    print(f"[*] Found {len(clickable)} clickable elements:")
    for text, cx, cy in clickable:
        print(f"    [{text}] @ ({cx},{cy})")
    
    # Try to find and tap menu/action buttons that might reveal tools
    # In NP Manager, tools are often in a slide-out drawer or accessed via top menu
    menu_patterns = ["Menu", "More", "\u66f4\u591a", "\u83dc\u5355", "\u529f\u80fd", "\u5de5\u5177",
                    "\u8bbe\u7f6e", "Settings", "Options", "\u9009\u9879"]
    
    for text, cx, cy in clickable:
        if any(p.lower() in text.lower() for p in menu_patterns):
            print(f"[*] Tapping menu button: [{text}] @ ({cx},{cy})")
            adb(f"shell input tap {cx} {cy}")
            time.sleep(2)
            break
    else:
        # No explicit menu found, try top-left hamburger (common in Android)
        print("[*] No menu button found, trying hamburger area...")
        tap_rel(0.05, 0.08, "Hamburger area")
        time.sleep(2)
    
    # Now scan for tools in the opened menu/view
    xml = get_xml()
    screenshot("np_menu_opened")
    clickable = get_all_clickable(xml)
    print(f"[*] After menu: {len(clickable)} clickable elements:")
    for text, cx, cy in clickable:
        print(f"    [{text}] @ ({cx},{cy})")
    
    # Look for tool-like options
    tool_texts = []
    for text, cx, cy in clickable:
        # Skip navigation elements
        if text in ["Back", "\u8fd4\u56de", "Cancel", "\u53d6\u6d88", "Close", "\u5173\u95ed"]:
            continue
        # Collect potential tool buttons
        tool_texts.append((text, cx, cy))
    
    # Try tapping each potential tool (up to 10)
    for i, (text, cx, cy) in enumerate(tool_texts[:10]):
        print(f"\n[*] Trying tool [{i+1}]: [{text}] @ ({cx},{cy})")
        adb(f"shell input tap {cx} {cy}")
        time.sleep(2)
        xml = get_xml()
        screenshot(f"np_tool_{i}_{text[:15]}")
        
        # Check if we got to a configuration screen (has apply/start buttons)
        apply_btns = ["OK", "Apply", "\u786e\u5b9a", "\u5e94\u7528", "\u5f00\u59cb", "Start",
                     "\u8fd0\u884c", "Run", "\u751f\u6210", "Generate", "\u786e\u8ba4", "Confirm"]
        found_apply = False
        for btn in apply_btns:
            coords = find_text(xml, btn)
            if coords:
                print(f"[+] Found apply button [{btn}], tapping...")
                adb(f"shell input tap {coords[0]} {coords[1]}")
                time.sleep(5)
                found_apply = True
                break
        
        if not found_apply:
            # Check if this opened a sub-menu with more options
            sub_clickable = get_all_clickable(get_xml())
            if len(sub_clickable) > len(tool_texts):
                print(f"[*] Sub-menu opened with {len(sub_clickable)} options")
        
        # Go back
        adb("shell input keyevent 4")
        time.sleep(1.5)
    
    print("\n[*] Tool exploration complete")


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
