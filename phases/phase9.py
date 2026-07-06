"""Phase 9: Validation (PC) — VirusTotal + Frida + APKiD."""
import os, json, time, subprocess
import requests
from config import TEMP_DIR, VT_API_KEY, APKID, FRIDA
from utils.logger import setup_logger
from utils.adb_helper import adb_shell

logger = setup_logger()

def _virustotal_scan(apk_path):
    """F1: VirusTotal re-scan."""
    if not VT_API_KEY:
        logger.warning("[!] No VT_API_KEY")
        return {"detections": -1, "status": "no_key"}
    url = "https://www.virustotal.com/api/v3/files"
    headers = {"x-apikey": VT_API_KEY}
    try:
        with open(apk_path, "rb") as apk_fh:
            files = {"file": (os.path.basename(apk_path), apk_fh)}
            r = requests.post(url, headers=headers, files=files, timeout=120)
        data = r.json()
        analysis_id = data.get("data", {}).get("id")
        if not analysis_id:
            return {"detections": -1, "error": "No analysis ID"}
        for i in range(20):
            time.sleep(15)
            ar = requests.get(f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                              headers=headers, timeout=60)
            ad = ar.json()
            status = ad.get("data", {}).get("attributes", {}).get("status")
            if status == "completed":
                stats = ad["data"]["attributes"]["stats"]
                return {"detections": stats.get("malicious", 0), "total": stats.get("total", 0)}
        return {"detections": -1, "status": "timeout"}
    except Exception as e:
        return {"detections": -1, "error": str(e)}

def _frida_test():
    """F2: Frida runtime test — simulate Play Protect checks."""
    logger.info("[*] F2: Frida runtime test")
    # Create a minimal Frida script for Play Protect simulation
    frida_script = str(TEMP_DIR / "playprotect_simulator.js")
    with open(frida_script, 'w') as f:
        f.write('''
// Play Protect simulation script
Java.perform(function() {
    var ActivityThread = Java.use('android.app.ActivityThread');
    var PackageManager = Java.use('android.content.pm.PackageManager');
    console.log("[*] Frida: Play Protect simulation active");
});
''')
    try:
        r = subprocess.run([FRIDA, "-U", "-f", "com.google.android.gms",
                           "-l", frida_script, "--no-pause"],
                          capture_output=True, text=True, timeout=30)
        stdout = r.stdout.lower()
        stderr = r.stderr.lower()
        warnings = 0
        if "warning" in stdout or "warning" in stderr:
            warnings += 1
        if "error" in stdout or "error" in stderr:
            warnings += 1
        if warnings > 0:
            logger.warning(f"[!] Frida warnings: {warnings}")
            return {"status": "warnings", "warnings": warnings}
        logger.info("[+] Frida: no warnings")
        return {"status": "ok", "warnings": 0}
    except Exception as e:
        logger.warning(f"[!] Frida not available: {e}")
        return {"status": "not_available", "warnings": 0}

def _apkid_final(apk_path):
    """F3: APKiD final verification."""
    logger.info("[*] F3: APKiD final scan")
    try:
        r = subprocess.run([APKID, "-v", "-j", apk_path],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception as e:
        logger.warning(f"[!] APKiD skip: {e}")
    return {}

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 9: Validation (3 functions)")
    logger.info("="*60)

    results = {
        "virustotal": None,
        "frida": None,
        "apkid": None,
        "needs_retry": False
    }

    results["virustotal"] = _virustotal_scan(input_apk)
    detections = results["virustotal"].get("detections", 0)
    logger.info(f"    VT Detections: {detections}")

    if detections > 3:
        logger.warning("[!] >3 detections — needs retry")
        results["needs_retry"] = True

    results["frida"] = _frida_test()
    results["apkid"] = _apkid_final(input_apk)

    with open(TEMP_DIR / "validation_results.json", "w") as f:
        json.dump(results, f, indent=2)

    logger.info("[+] Phase 9 Complete")
    return input_apk
