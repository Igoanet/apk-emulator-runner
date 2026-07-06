#!/usr/bin/env python3
"""
Test script to verify Android emulator + NP Manager automation works
Run this to check the setup before full pipeline
"""
import subprocess
import sys
import time
import os

ADB = "adb"

def _run(cmd, timeout=30):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode == 0, result.stdout, result.stderr

def test_device_connection():
    print("[TEST 1] Device connection...")
    ok, out, err = _run([ADB, "devices"])
    if ok and "emulator" in out:
        print("  ✅ Device found:", out.strip().split("\n")[1])
        return True
    print("  ❌ No emulator found")
    print("  Error:", err)
    return False

def test_screen_size():
    print("[TEST 2] Screen size...")
    ok, out, _ = _run([ADB, "shell", "wm", "size"])
    if ok:
        print(f"  ✅ Screen: {out.strip()}")
        return True
    return False

def test_install_app(apk_path):
    print(f"[TEST 3] Install {os.path.basename(apk_path)}...")
    ok, out, err = _run([ADB, "install", "-r", apk_path], timeout=60)
    if ok:
        print("  ✅ Installed successfully")
        return True
    print(f"  ❌ Install failed: {err[:200]}")
    return False

def test_app_installed(package_name):
    print(f"[TEST 4] Check {package_name}...")
    ok, out, _ = _run([ADB, "shell", "pm", "list", "packages", package_name])
    if ok and package_name in out:
        print(f"  ✅ {package_name} installed")
        return True
    print(f"  ❌ {package_name} not found")
    return False

def test_launch_app(package_name):
    print(f"[TEST 5] Launch {package_name}...")
    _run([ADB, "shell", "am", "force-stop", package_name])
    time.sleep(1)
    _run([ADB, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(5)
    
    ok, out, _ = _run([ADB, "shell", "dumpsys", "window", "windows", "|", "grep", "-i", package_name])
    print(f"  Window check: {ok}")
    return ok

def test_ui_dump():
    print("[TEST 6] UI hierarchy dump...")
    _run([ADB, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    ok, out, _ = _run([ADB, "shell", "cat", "/sdcard/window_dump.xml"])
    if ok and len(out) > 100:
        print(f"  ✅ UI dump: {len(out)} chars")
        return True
    print("  ❌ UI dump failed")
    return False

def main():
    print("=" * 60)
    print("Android Emulator + NP Manager Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(test_device_connection())
    results.append(test_screen_size())
    
    # Check for APK files
    np_apk = None
    for f in ["attached_assets/NP_Manager_1783303024552.apk", "attached_assets/NP_Manager_1783273430848.apk"]:
        if os.path.exists(f):
            np_apk = f
            break
    
    if np_apk:
        results.append(test_install_app(np_apk))
        results.append(test_app_installed("com.wn.app.np"))
        results.append(test_launch_app("com.wn.app.np"))
    else:
        print("[TEST 3-5] SKIP - NP Manager APK not found")
        results.extend([False, False, False])
    
    results.append(test_ui_dump())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Emulator + NP Manager working!")
        return 0
    else:
        print("❌ Some tests failed - check setup")
        return 1

if __name__ == "__main__":
    sys.exit(main())
