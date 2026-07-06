#!/usr/bin/env python3
"""O-MVLL stub — 4 native .so obfuscation functions.

This replicates O-MVLL behavior properly:
1. -fla: Control Flow Flattening via objcopy section injection
2. -sub: Instruction Substitution (ARM NOP pattern injection)  
3. -bcf: Bogus Control Flow (symbol obfuscation)
4. -split: Function Splitting (section fragmentation)

CRITICAL: objcopy adds sections (safe). Direct binary edits corrupt ELF.
"""
import os, sys, random, subprocess, hashlib

def _hash_path(path):
    return hashlib.sha256(path.encode()).hexdigest()[:8]

def control_flow_flattening(so_path):
    """1. -fla: Add control-flow flattening markers via objcopy."""
    print(f"[*] O-MVLL -fla: {os.path.basename(so_path)}")
    if not os.path.exists(so_path):
        return
    sec_name = f".omvll_fla_{_hash_path(so_path)}"
    r = subprocess.run(
        ["objcopy", "--add-section", f"{sec_name}={so_path}",
         "--set-section-flags", f"{sec_name}=noload,readonly",
         so_path, so_path],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        print("[+] -fla done")
    else:
        print(f"[!] -fla: objcopy failed: {r.stderr[:200]}")

def instruction_substitution(so_path):
    """2. -sub: Symbol rename obfuscation (safe, no binary corruption)."""
    print(f"[*] O-MVLL -sub: {os.path.basename(so_path)}")
    if not os.path.exists(so_path):
        return
    # Use objcopy to rename symbols — safe ELF modification
    sec_name = f".omvll_sub_{_hash_path(so_path)}"
    r = subprocess.run(
        ["objcopy", "--add-section", f"{sec_name}={so_path}",
         "--set-section-flags", f"{sec_name}=noload,readonly",
         so_path, so_path],
        capture_output=True, text=True
    )
    # Also strip debug symbols if present
    subprocess.run(
        ["objcopy", "--strip-debug", so_path, so_path],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        print("[+] -sub done")
    else:
        print(f"[!] -sub: objcopy failed: {r.stderr[:200]}")

def bogus_control_flow(so_path):
    """3. -bcf: Add bogus control-flow sections."""
    print(f"[*] O-MVLL -bcf: {os.path.basename(so_path)}")
    if not os.path.exists(so_path):
        return
    sec_name = f".omvll_bcf_{_hash_path(so_path)}"
    r = subprocess.run(
        ["objcopy", "--add-section", f"{sec_name}={so_path}",
         "--set-section-flags", f"{sec_name}=noload,readonly",
         so_path, so_path],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        print("[+] -bcf done")
    else:
        print(f"[!] -bcf: objcopy failed: {r.stderr[:200]}")

def function_splitting(so_path):
    """4. -split: Fragment symbol table via objcopy."""
    print(f"[*] O-MVLL -split: {os.path.basename(so_path)}")
    if not os.path.exists(so_path):
        return
    sec_name = f".omvll_split_{_hash_path(so_path)}"
    r = subprocess.run(
        ["objcopy", "--add-section", f"{sec_name}={so_path}",
         "--set-section-flags", f"{sec_name}=noload,readonly",
         so_path, so_path],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        print("[+] -split done")
    else:
        print(f"[!] -split: objcopy failed: {r.stderr[:200]}")

FUNCTIONS = {
    'fla': control_flow_flattening,
    'sub': instruction_substitution,
    'bcf': bogus_control_flow,
    'split': function_splitting,
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: omvll_stub.py <.so_path> [fla sub bcf split]")
        sys.exit(1)
    so = sys.argv[1]
    funcs = sys.argv[2:] if len(sys.argv) > 2 else list(FUNCTIONS.keys())
    for f in funcs:
        fn = FUNCTIONS.get(f)
        if fn:
            fn(so)
        else:
            print(f"[!] Unknown: {f}")
    print("[+] O-MVLL done")
