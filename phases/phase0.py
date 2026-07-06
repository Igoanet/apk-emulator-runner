"""Phase 0: Preparation — APKiD + JADX + Decompile + Suspicious Strings + VirusTotal."""
import os, subprocess, re, json, time, shutil
from pathlib import Path
from utils.logger import setup_logger
from utils.file_utils import get_size_mb, sha256_file
from config import INPUT_DIR, TEMP_DIR, LOGS_DIR, VT_API_KEY, APKTOOL, JADX, APKID

logger = setup_logger()

def _apkid_scan(apk_path):
    """Function 1: APKiD — scan for packers/obfuscators."""
    logger.info("[*] F1: APKiD scan")
    try:
        r = subprocess.run([APKID, "-v", "-j", apk_path],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            logger.info(f"[+] APKiD: {len(data)} detections")
            return data
    except Exception as e:
        logger.warning(f"[!] APKiD skip: {e}")
    return {}

def _jadx_decompile(apk_path, out_dir):
    """Function 2: APKLab — JADX decompile."""
    logger.info("[*] F2: APKLab JADX decompile")
    try:
        r = subprocess.run([JADX, "-d", out_dir, "--show-bad-code", apk_path],
                          capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            logger.info("[+] JADX done")
            return True
    except Exception as e:
        logger.warning(f"[!] JADX skip: {e}")
    return False

def _apktool_decompile(apk_path, out_dir):
    """Function 3: APKTool M — decompile APK."""
    logger.info("[*] F3: APKTool M decompile")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", out_dir, apk_path],
                      capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        logger.info("[+] APKTool decompile done")
        # Remove synthetic res/ dir to prevent build errors with "false" layout values
        res_dir = os.path.join(out_dir, "res")
        if os.path.exists(res_dir):
            shutil.rmtree(res_dir)
        return True
    raise Exception(f"apktool d failed: {r.stderr[:500]}")

def _extract_suspicious(decompiled_dir):
    """Function 4: Extract suspicious strings."""
    logger.info("[*] F4: Suspicious string extraction")
    patterns = re.compile(r"(https?://[^\s\"'<>]+|exec|Runtime|getDeviceId|READ_SMS|WRITE_SMS|SEND_SMS|BOOT_COMPLETED|meterpreter|payload|c2|cnc|metasploit|stage|bypass|inject|shell|backdoor|trojan|rat|spy)", re.I)
    susp = set()
    dp = Path(decompiled_dir)
    for f in dp.rglob("*"):
        if f.is_file() and f.stat().st_size < 5*1024*1024:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        for m in patterns.finditer(line):
                            susp.add(m.group(0))
            except:
                pass
    logger.info(f"[+] Found {len(susp)} suspicious strings")
    return sorted(susp)[:50]

def _virustotal_scan(apk_path):
    """Function 5: VirusTotal API scan."""
    import requests
    logger.info("[*] F5: VirusTotal scan")
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
            return {"error": "No analysis ID"}
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
        return {"error": str(e)}

def run(apk_path):
    logger.info("="*60)
    logger.info("[*] PHASE 0: Preparation (5 functions)")
    logger.info("="*60)

    results = {
        "apk_path": str(apk_path),
        "size_mb": round(get_size_mb(apk_path), 2),
        "sha256": sha256_file(apk_path),
        "apkid": None,
        "jadx": None,
        "decompiled_dir": None,
        "suspicious_strings": [],
        "virustotal": None,
        "error": None
    }

    try:
        results["apkid"] = _apkid_scan(apk_path)
        jadx_dir = str(TEMP_DIR / "jadx_output")
        results["jadx"] = _jadx_decompile(apk_path, jadx_dir)

        decompiled = str(TEMP_DIR / f"decompiled_{os.path.basename(apk_path)}")
        results["decompiled_dir"] = decompiled
        _apktool_decompile(apk_path, decompiled)

        results["suspicious_strings"] = _extract_suspicious(decompiled)
        results["virustotal"] = _virustotal_scan(apk_path)

    except Exception as e:
        logger.error(f"[!] Phase 0 error: {e}")
        results["error"] = str(e)

    with open(TEMP_DIR / "phase0_results.json", "w") as f:
        json.dump(results, f, indent=2)

    logger.info("[+] Phase 0 Complete")
    return results
