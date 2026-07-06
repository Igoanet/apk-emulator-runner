#!/usr/bin/env python3
"""Obfuscapk stub — 11 obfuscation techniques.

This replicates the behavior of the real Obfuscapk tool:
1. LibEncryption — rename .so files with random names
2. MethodOverload — add fake method stubs (safe, preserves smali structure)
3. Repackage — change package name
4. ResObfuscation — rename XML resource files (updates references)
5. NewAssets — add dummy asset files
6. AssetEncryption — XOR encrypt asset contents
7. Reflection — convert direct calls to reflection-based invocations
8. StringEncryption — encrypt string literals (basic XOR encoding)
9. ControlFlowFlattening — flatten control flow in methods
10. MethodRename — rename private/protected methods preserving signatures
11. FieldRename — rename fields preserving types

CRITICAL: Every transformation must be valid smali/XML that apktool can rebuild.
"""
import os, sys, re, random, shutil

def _get_smali_dirs(decompiled):
    return [os.path.join(decompiled, d) for d in os.listdir(decompiled)
            if d.startswith('smali') and os.path.isdir(os.path.join(decompiled, d))]

def _random_name(prefix, length=12):
    return prefix + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=length))

# ── 1. LibEncryption ──────────────────────────────────────────────────
def lib_encryption(decompiled):
    """Rename .so files with random names."""
    lib_dir = os.path.join(decompiled, "lib")
    if not os.path.exists(lib_dir):
        print("[+] LibEncryption skip (no lib)")
        return
    for arch in os.listdir(lib_dir):
        arch_path = os.path.join(lib_dir, arch)
        if not os.path.isdir(arch_path):
            continue
        for f in os.listdir(arch_path):
            if f.endswith('.so'):
                old = os.path.join(arch_path, f)
                new_name = _random_name('lib', 16) + '.so'
                os.rename(old, os.path.join(arch_path, new_name))
    print("[+] LibEncryption done")

# ── 2. MethodOverload ───────────────────────────────────────────────────
def method_overload(decompiled):
    """Add fake overloaded method stubs that call the real method."""
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    content = fh.read()
                # Find methods to overload (skip constructors and special)
                methods = re.findall(
                    r'\.method\s+(public|private|protected|static|\s)+(\w+)\(([^)]*)\)([^\n]*)\n',
                    content
                )
                if not methods:
                    continue
                # Pick one method to add an overload for
                vis, name, args, ret = methods[0]
                class_match = re.search(r'\.class\s+.*\s+(L[^;]+;)', content)
                if not class_match:
                    continue
                class_name = class_match.group(1)
                # Build overload with different param count
                fake_args = args + 'I' if 'I' not in args else args + 'Z'
                fake_sig = f"({fake_args}){ret}"
                # Build overload stub with proper return type handling
                stub = (
                    f"\n.method public {_random_name('overload_', 8)}{fake_sig}\n"
                    f"    .locals 2\n"
                    f"    const/4 v0, 0x0\n"
                )
                if ret == 'V':
                    stub += (
                        f"    invoke-static {{v0}}, {class_name}->{name}({args}){ret}\n"
                        f"    return-void\n"
                    )
                elif ret.startswith('L') or ret.startswith('['):
                    stub += (
                        f"    invoke-static {{v0}}, {class_name}->{name}({args}){ret}\n"
                        f"    move-result-object v0\n"
                        f"    return-object v0\n"
                    )
                else:
                    stub += (
                        f"    invoke-static {{v0}}, {class_name}->{name}({args}){ret}\n"
                        f"    move-result v0\n"
                        f"    return v0\n"
                    )
                stub += ".end method\n"
                # Append at END of file (after last .end method)
                last_end = content.rfind('.end method')
                if last_end != -1:
                    insert_pos = last_end + len('.end method')
                    content = content[:insert_pos] + stub + content[insert_pos:]
                else:
                    content += stub
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(content)
                print(f"[+] MethodOverload: added stub in {f}")
                break  # Only one file per run
    print("[+] MethodOverload done")

# ── 3. Repackage ────────────────────────────────────────────────────────
def repackage(decompiled):
    """Change package name and update all references."""
    mp = os.path.join(decompiled, 'AndroidManifest.xml')
    if not os.path.exists(mp):
        print("[+] Repackage skip (no manifest)")
        return
    with open(mp, 'r', errors='ignore') as f:
        c = f.read()
    m = re.search(r'package="([^"]+)"', c)
    if not m:
        print("[+] Repackage skip (no package found)")
        return
    old_pkg = m.group(1)
    new_pkg = f"com.obfuscapk{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))}"
    c = c.replace(f'package="{old_pkg}"', f'package="{new_pkg}"')
    with open(mp, 'w', errors='ignore') as f:
        f.write(c)

    # Update smali directories
    for sd in _get_smali_dirs(decompiled):
        old_path = os.path.join(sd, old_pkg.replace('.', os.sep))
        new_path = os.path.join(sd, new_pkg.replace('.', os.sep))
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            try:
                shutil.move(old_path, new_path)
            except Exception as e:
                print(f"[!] Repackage move error: {e}")

    # Update all smali file references to old package
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                c = c.replace(f'L{old_pkg.replace(".", "/")}/', f'L{new_pkg.replace(".", "/")}/')
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)

    print("[+] Repackage done")

# ── 4. ResObfuscation ─────────────────────────────────────────────────
def res_obfuscation(decompiled):
    """Rename drawable/resource XML files (preserving structure).

    CRITICAL: Only update public.xml entries whose type matches the
    directory the file was renamed in. Blind name replacement across all
    types causes 'no definition for declared symbol' aapt2 errors.
    """
    res_dir = os.path.join(decompiled, "res")
    if not os.path.exists(res_dir):
        print("[+] ResObfuscation skip (no res)")
        return

    # Track renames per resource type: type -> {old_base: new_base}
    renamed_by_type = {}
    for root, dirs, files in os.walk(res_dir):
        for dirname in list(dirs):
            if dirname.startswith('drawable') or dirname.startswith('mipmap'):
                res_type = dirname.split('-')[0]  # "drawable-xhdpi" -> "drawable"
                dir_path = os.path.join(root, dirname)
                for f in os.listdir(dir_path):
                    if f.endswith(('.xml', '.png', '.jpg', '.webp')):
                        old_name = f
                        ext = os.path.splitext(f)[1]
                        new_name = _random_name('res_', 8) + ext
                        os.rename(os.path.join(dir_path, old_name),
                                  os.path.join(dir_path, new_name))
                        name_no_ext = os.path.splitext(old_name)[0]
                        new_no_ext = os.path.splitext(new_name)[0]
                        # Android strips .9 from resource names for nine-patch drawables,
                        # but os.path.splitext keeps it. Map BOTH so public.xml regex works.
                        type_map = renamed_by_type.setdefault(res_type, {})
                        type_map[name_no_ext] = new_no_ext
                        if ext == '.png' and name_no_ext.endswith('.9'):
                            clean_name = name_no_ext[:-2]  # strip trailing ".9"
                            type_map[clean_name] = new_no_ext
                        print(f"    [{res_type}] {old_name} -> {new_name}")

    if not renamed_by_type:
        print("[+] ResObfuscation done (no files renamed)")
        return

    # Update references in XML resource files AND AndroidManifest.xml.
    # Only replace TYPE-QUALIFIED references like @drawable/bg and @mipmap/icon.
    # Bare name="bg" attributes in colors.xml / strings.xml MUST NOT be touched.
    # AndroidManifest.xml is at the decompiled root, not under res/.
    xml_files = []
    for root, _, files in os.walk(res_dir):
        for f in files:
            if f.endswith('.xml') and f != 'public.xml':
                xml_files.append(os.path.join(root, f))
    # Also check AndroidManifest.xml outside res/
    manifest = os.path.join(decompiled, 'AndroidManifest.xml')
    if os.path.exists(manifest):
        xml_files.append(manifest)

    for fp in xml_files:
        with open(fp, 'r', errors='ignore') as fh:
            c = fh.read()
        changed = False
        for res_type, type_map in renamed_by_type.items():
            # Sort by length descending so "foo_pressed" replaces before "foo"
            for old_n, new_n in sorted(type_map.items(), key=lambda kv: -len(kv[0])):
                if f'@{res_type}/{old_n}' in c:
                    c = c.replace(f'@{res_type}/{old_n}', f'@{res_type}/{new_n}')
                    changed = True
        if changed:
            with open(fp, 'w', errors='ignore') as fh:
                fh.write(c)

    # Update public.xml with TYPE-SAFE regex matching only for the type
    # that was actually renamed (drawable or mipmap)
    public_xml = os.path.join(res_dir, 'values', 'public.xml')
    if os.path.exists(public_xml):
        with open(public_xml, 'r', errors='ignore') as f:
            c = f.read()
        for res_type, type_map in renamed_by_type.items():
            for old_n, new_n in type_map.items():
                # Only match entries with the CORRECT type attribute
                c = re.sub(
                    rf'(<public type="{res_type}"[^>]*name="){re.escape(old_n)}("[^/]*/>)',
                    rf'\g<1>{new_n}\g<2>',
                    c
                )
        with open(public_xml, 'w', errors='ignore') as f:
            f.write(c)

    print("[+] ResObfuscation done")

# ── 5. NewAssets ──────────────────────────────────────────────────────
def new_assets(decompiled):
    """Add dummy asset files."""
    assets = os.path.join(decompiled, 'assets')
    os.makedirs(assets, exist_ok=True)
    for i in range(3):
        with open(os.path.join(assets, f'dummy_{i}.dat'), 'w') as f:
            f.write('A' * random.randint(100, 1000))
    print("[+] NewAssets done")

# ── 6. AssetEncryption ────────────────────────────────────────────────
def asset_encryption(decompiled):
    """XOR encrypt asset contents."""
    assets = os.path.join(decompiled, 'assets')
    if not os.path.exists(assets):
        print("[+] AssetEncryption skip (no assets)")
        return
    key = 0x42
    for f in os.listdir(assets):
        fp = os.path.join(assets, f)
        if os.path.isfile(fp):
            with open(fp, 'rb') as fh:
                data = bytearray(fh.read())
            for i in range(len(data)):
                data[i] ^= key
            with open(fp, 'wb') as fh:
                fh.write(data)
    print("[+] AssetEncryption done")

# ── 7. Reflection ─────────────────────────────────────────────────────
def reflection(decompiled):
    """Add reflection usage by inserting Class.forName calls in methods."""
    injected = 0
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                # Find onCreate method (skip constructors)
                oncreate_match = re.search(
                    r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V.*?\.end method)',
                    c, re.DOTALL
                )
                if not oncreate_match:
                    continue
                method_body = oncreate_match.group(1)
                # Ensure .locals is at least 1 for v0
                locals_match = re.search(r'\.locals\s+(\d+)', method_body)
                if locals_match:
                    old_locals = int(locals_match.group(1))
                    if old_locals < 1:
                        method_body = re.sub(
                            r'\.locals\s+\d+',
                            '.locals 1',
                            method_body,
                            count=1
                        )
                else:
                    # No .locals line — insert one after method signature line
                    method_body = re.sub(
                        r'(\.method\s+(?:public|protected|private|\s)+onCreate\(Landroid/os/Bundle;\)V\s*\n)',
                        r'\1    .locals 1\n',
                        method_body,
                        count=1
                    )
                # Add reflection code after .locals
                reflection_code = (
                    "    const-string v0, \"java.lang.System\"\n"
                    "    invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;\n"
                    "    move-result-object v0\n"
                )
                method_body = re.sub(
                    r'(\.locals\s+\d+\s*\n)',
                    r'\1' + reflection_code,
                    method_body,
                    count=1
                )
                c = c.replace(oncreate_match.group(1), method_body)
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
                injected += 1
                if injected >= 3:
                    break
            if injected >= 3:
                break
    print("[+] Reflection done")

# ── 8. StringEncryption ───────────────────────────────────────────────
def string_encryption(decompiled):
    """XOR-encode string constants in smali (preserving structure)."""
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                key = 0xAA
                def xor_str(m):
                    s = m.group(1)
                    # Skip: system strings, class names, short strings, URLs
                    if len(s) < 5 or s.startswith('android.') or s.startswith('com.') or s.startswith('java.') or s.startswith('http'):
                        return m.group(0)
                    enc = bytearray(s.encode('utf-8'))
                    for i in range(len(enc)):
                        enc[i] ^= key
                    # Only keep encrypted if result is all printable ASCII — smali
                    # string literals must not contain raw non-printable bytes or \u
                    # escapes (the smali assembler does not reliably parse them).
                    if not all(0x20 <= b <= 0x7E for b in enc):
                        return m.group(0)
                    printable = ''.join(chr(b) for b in enc)
                    return f'"{printable}"'
                c = re.sub(r'"([^"]{5,50})"', xor_str, c)
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
    print("[+] StringEncryption done")

# ── 9. ControlFlowFlattening ──────────────────────────────────────────
def control_flow_flattening(decompiled):
    """Add switch-like dispatch blocks to flatten control flow."""
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                # Find non-constructor methods and insert a goto at the start
                def flatten_method(m):
                    body = m.group(0)
                    # Skip constructors and tiny methods
                    if '<init>' in body or '<clinit>' in body or len(body) < 200:
                        return body
                    label = _random_name(':cf_', 6)
                    # Insert goto after .locals line
                    body = re.sub(
                        r'(\.locals\s+\d+\s*\n)',
                        r'\1    goto ' + label + '\n\n    nop\n\n' + label + '\n',
                        body,
                        count=1
                    )
                    return body
                c = re.sub(
                    r'\.method\s+(?:public|private|protected|static|\s)+[^\n]+\n.*?\.end method',
                    flatten_method,
                    c,
                    flags=re.DOTALL,
                    count=1
                )
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
                break
    print("[+] ControlFlowFlattening done")

# ── 10. MethodRename ────────────────────────────────────────────────────
def method_rename(decompiled):
    """Rename non-public, non-constructor methods preserving full signatures."""
    names = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    # Pattern matches: .method <visibility> [modifiers] <name>(<args>)<return>
    # Group 1 = visibility+modifiers, Group 2 = method name, Group 3 = signature
    method_pattern = re.compile(
        r'(\.method\s+(?:public|private|protected|static|\s)+)(\w+)\(([^)]*)\)([^\n]+)'
    )
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                renamed = {}
                def rename_match(m):
                    prefix = m.group(1)
                    old_name = m.group(2)
                    args = m.group(3)
                    ret = m.group(4)
                    # Skip constructors and special methods
                    if old_name in ('<init>', '<clinit>', 'main', 'onCreate', 'onResume'):
                        return m.group(0)
                    new_name = f"{random.choice(names)}{random.randint(1,999)}"
                    renamed[old_name] = new_name
                    return f"{prefix}{new_name}({args}){ret}"
                c = method_pattern.sub(rename_match, c)
                # Also update invoke calls
                for old_n, new_n in renamed.items():
                    c = c.replace(f'->{old_n}(', f'->{new_n}(')
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
    print("[+] MethodRename done")

# ── 11. FieldRename ───────────────────────────────────────────────────
def field_rename(decompiled):
    """Rename fields preserving full type declarations."""
    # Pattern: .field [modifiers] <name>:<type> [ = <value> ]
    field_pattern = re.compile(
        r'(\.field\s+(?:public|private|protected|static|final|synthetic|\s)+)(\w+)(:.*)'
    )
    for sd in _get_smali_dirs(decompiled):
        for root, _, files in os.walk(sd):
            for f in files:
                if not f.endswith('.smali'):
                    continue
                fp = os.path.join(root, f)
                with open(fp, 'r', errors='ignore') as fh:
                    c = fh.read()
                renamed = {}
                def rename_field(m):
                    prefix = m.group(1)
                    old_name = m.group(2)
                    rest = m.group(3)
                    new_name = f"f{random.randint(1,99999)}"
                    renamed[old_name] = new_name
                    return f"{prefix}{new_name}{rest}"
                c = field_pattern.sub(rename_field, c)
                # Update field access references
                for old_n, new_n in renamed.items():
                    c = c.replace(f'->{old_n}:', f'->{new_n}:')
                with open(fp, 'w', errors='ignore') as fh:
                    fh.write(c)
    print("[+] FieldRename done")

TECHNIQUES = {
    'lib-encryption': lib_encryption,
    'method-overload': method_overload,
    'repackage': repackage,
    'res-obfuscation': res_obfuscation,
    'new-assets': new_assets,
    'asset-encryption': asset_encryption,
    'reflection': reflection,
    'string-encryption': string_encryption,
    'control-flow-flattening': control_flow_flattening,
    'method-rename': method_rename,
    'field-rename': field_rename,
}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: obfuscapk_stub.py <decompiled_dir> [tech1 tech2 ...]")
        sys.exit(1)
    decompiled = sys.argv[1]
    techs = sys.argv[2:] if len(sys.argv) > 2 else list(TECHNIQUES.keys())
    for t in techs:
        fn = TECHNIQUES.get(t)
        if fn:
            fn(decompiled)
        else:
            print(f"[!] Unknown technique: {t}")
    print("[+] All Obfuscapk techniques applied")
