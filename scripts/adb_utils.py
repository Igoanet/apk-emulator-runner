#!/usr/bin/env python3
"""Shared ADB utilities for Android automation"""
import subprocess
import time
import os
import xml.etree.ElementTree as ET

ADB = os.environ.get("ADB", "adb")

def _run(cmd, timeout=30):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode == 0, result.stdout, result.stderr

def wait_for_device(timeout=60):
    ok, _, _ = _run([ADB, "wait-for-device"], timeout=timeout)
    return ok

def get_screen_size():
    ok, out, _ = _run([ADB, "shell", "wm", "size"])
    if ok:
        return out.strip()
    return None

def take_screenshot(path="/sdcard/screen.png"):
    _run([ADB, "shell", "screencap", "-p", path])
    return path

def pull_screenshot(local_path="screenshot.png"):
    remote = "/sdcard/screen.png"
    take_screenshot(remote)
    _run([ADB, "pull", remote, local_path])
    return local_path

def get_ui_hierarchy():
    """Get full UI hierarchy as XML string"""
    _run([ADB, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    ok, out, _ = _run([ADB, "shell", "cat", "/sdcard/window_dump.xml"])
    return out if ok else ""

def find_element_bounds(xml_text, text_search):
    """Find element bounds containing specific text"""
    try:
        root = ET.fromstring(xml_text)
        for node in root.iter():
            node_text = node.get("text", "") + " " + node.get("content-desc", "")
            if text_search.lower() in node_text.lower():
                bounds = node.get("bounds", "")
                # bounds format: [x1,y1][x2,y2]
                if bounds:
                    import re
                    nums = re.findall(r'\[(\d+),(\d+)\]', bounds)
                    if len(nums) == 2:
                        x1, y1 = int(nums[0][0]), int(nums[0][1])
                        x2, y2 = int(nums[1][0]), int(nums[1][1])
                        return ((x1 + x2) // 2, (y1 + y2) // 2)
    except:
        pass
    return None

def tap_text(text, retries=5):
    """Tap element containing text by finding it in UI hierarchy"""
    for i in range(retries):
        xml = get_ui_hierarchy()
        coords = find_element_bounds(xml, text)
        if coords:
            x, y = coords
            _run([ADB, "shell", "input", "tap", str(x), str(y)])
            return True
        time.sleep(1)
    return False

def tap_screen(x, y):
    _run([ADB, "shell", "input", "tap", str(x), str(y)])

def swipe(x1, y1, x2, y2, duration=300):
    _run([ADB, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

def press_key(keycode):
    _run([ADB, "shell", "input", "keyevent", str(keycode)])

def back():
    press_key(4)

def home():
    press_key(3)

def install_apk(apk_path, timeout=60):
    ok, out, err = _run([ADB, "install", "-r", apk_path], timeout=timeout)
    return ok

def launch_app(package_name, activity=None):
    _run([ADB, "shell", "am", "force-stop", package_name])
    time.sleep(1)
    if activity:
        _run([ADB, "shell", "am", "start", "-n", f"{package_name}/{activity}"])
    else:
        _run([ADB, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(3)

def is_app_installed(package_name):
    ok, out, _ = _run([ADB, "shell", "pm", "list", "packages", package_name])
    return package_name in out
