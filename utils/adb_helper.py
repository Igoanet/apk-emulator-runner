"""ADB helper for Android device communication."""
import subprocess, os, time
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger()
TOOLS_PATH = "/home/runner/workspace/android-tools-bin"
ADB = f"{TOOLS_PATH}/adb" if os.path.exists(f"{TOOLS_PATH}/adb") else "adb"

def _run(cmd, timeout=60):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "PATH": f"{TOOLS_PATH}:{os.environ.get('PATH','')}"})
    return result.returncode == 0, result.stdout, result.stderr

def adb_connect(ip, port=5555):
    logger.info(f"[*] ADB connecting to {ip}:{port}")
    ok, out, err = _run([ADB, "connect", f"{ip}:{port}"])
    if ok and "connected" in out.lower():
        logger.info("[+] ADB connected")
        return True
    logger.warning(f"[!] ADB connect failed: {err or out}")
    return False

def adb_disconnect(ip, port=5555):
    _run([ADB, "disconnect", f"{ip}:{port}"])

def adb_shell(cmd, timeout=60):
    ok, out, err = _run([ADB, "shell", cmd], timeout=timeout)
    return out if ok else err

def adb_push(local, remote, timeout=120):
    logger.info(f"[*] ADB push: {local} -> {remote}")
    ok, out, err = _run([ADB, "push", local, remote], timeout=timeout)
    if not ok:
        logger.warning(f"[!] Push failed: {err}")
    return ok, out, err

def adb_pull(remote, local, timeout=120):
    logger.info(f"[*] ADB pull: {remote} -> {local}")
    ok, out, err = _run([ADB, "pull", remote, local], timeout=timeout)
    if not ok:
        logger.warning(f"[!] Pull failed: {err}")
    return ok, out, err

def adb_install(apk_path, spoof_store="com.android.vending", timeout=120):
    logger.info(f"[*] ADB install: {apk_path}")
    ok, out, err = _run([ADB, "install", "-i", spoof_store, apk_path], timeout=timeout)
    if not ok:
        logger.warning(f"[!] Install failed: {err}")
    return ok, out, err

def adb_trigger_tasker(task_name):
    logger.info(f"[*] Triggering Tasker: {task_name}")
    ok, out, err = _run([
        ADB, "shell", "am", "broadcast",
        "-a", "net.dinglisch.android.tasker.ACTION_RUN_TASK",
        "--es", "task_name", task_name
    ])
    return ok

def adb_wait_for_file(remote_path, poll_interval=10, max_wait=1800):
    """Poll for file existence on device."""
    logger.info(f"[*] Waiting for {remote_path} on device...")
    waited = 0
    while waited < max_wait:
        out = adb_shell(f'ls "{remote_path}" 2>/dev/null && echo EXISTS || echo MISSING')
        if "EXISTS" in out:
            logger.info("[+] File found on device")
            return True
        time.sleep(poll_interval)
        waited += poll_interval
    logger.warning("[!] Timeout waiting for file")
    return False
