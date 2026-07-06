"""
Full package rename utility for decompiled APKs.
Replaces all occurrences of old_package with new_package in:
- AndroidManifest.xml
- resources.arsc (via binary patch)
- All .smali files
- All .xml files
- Directory structure
"""
import os
import re
import shutil
from pathlib import Path


def rename_package(decompiled_dir: str, old_pkg: str, new_pkg: str):
    """
    Replace ALL occurrences of old_pkg with new_pkg in decompiled APK.
    Uses apktool.yml renameManifestPackage for binary-safe manifest rename.
    """
    work = Path(decompiled_dir)
    old_dots = old_pkg
    new_dots = new_pkg
    old_slashes = old_pkg.replace('.', '/')
    new_slashes = new_pkg.replace('.', '/')

    # 1. AndroidManifest.xml — use apktool.yml renameManifestPackage
    #    instead of corrupting binary XML with naive byte replacement
    apktool_yml = work / 'apktool.yml'
    if apktool_yml.exists():
        content = apktool_yml.read_text()
        # Replace the renameManifestPackage line
        if 'renameManifestPackage:' in content:
            content = re.sub(
                r'renameManifestPackage:\s*\S*',
                f'renameManifestPackage: {new_pkg}',
                content
            )
        else:
            # Add it after the packageInfo block
            content = content.replace(
                'packageInfo:\n',
                f'packageInfo:\n  renameManifestPackage: {new_pkg}\n'
            )
        apktool_yml.write_text(content)
        print(f"  [+] Set apktool.yml renameManifestPackage: {new_pkg}")
    else:
        # Fallback: only if apktool.yml missing
        manifest = work / 'AndroidManifest.xml'
        if manifest.exists():
            from utils.binary_xml import patch_binary_file
            content = manifest.read_bytes()
            content = patch_binary_file(content, {old_dots: new_dots})
            manifest.write_bytes(content)
            print(f"  [+] Patched AndroidManifest.xml (binary-safe)")

    # 2. resources.arsc — only patch if old package actually exists in it
    arsc = work / 'resources.arsc'
    if arsc.exists():
        arsc_data = arsc.read_bytes()
        if old_dots.encode() in arsc_data:
            from utils.binary_xml import patch_binary_file
            arsc_data = patch_binary_file(arsc_data, {old_dots: new_dots})
            arsc.write_bytes(arsc_data)
            print(f"  [+] Patched resources.arsc")
        else:
            print(f"  [+] resources.arsc: old package not present, skipped")

    # 3. All .smali files (also handle kotlin smali)
    smali_dirs = [d for d in work.iterdir() if d.is_dir() and d.name.startswith('smali')]
    patched_count = 0
    for smali_dir in smali_dirs:
        for smali_file in smali_dir.rglob('*.smali'):
            try:
                content = smali_file.read_text(encoding='utf-8')
                if old_dots in content or old_slashes in content:
                    content = content.replace(old_dots, new_dots)
                    content = content.replace(old_slashes, new_slashes)
                    smali_file.write_text(content, encoding='utf-8')
                    patched_count += 1
            except UnicodeDecodeError:
                pass
        print(f"  [+] Patched {patched_count} .smali files in {smali_dir.name}")

    # 4. All .xml files (skip binary XML)
    for xml_file in work.rglob('*.xml'):
        if xml_file.name == 'AndroidManifest.xml':
            continue
        try:
            content = xml_file.read_text(encoding='utf-8')
            content = content.replace(old_dots, new_dots)
            content = content.replace(old_slashes, new_slashes)
            xml_file.write_text(content, encoding='utf-8')
        except UnicodeDecodeError:
            # Binary XML file — skip (already patched via binary bytes in step 1)
            pass

    # 5. Rename directories
    old_parts = old_pkg.split('.')
    new_parts = new_pkg.split('.')

    for smali_dir in smali_dirs:
        old_path = smali_dir
        for part in old_parts:
            old_path = old_path / part

        if old_path.exists() and old_path.is_dir():
            # Build new path
            new_path = smali_dir
            for part in new_parts:
                new_path = new_path / part
            # Create parent dirs
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            print(f"  [+] Renamed directory: {old_path.relative_to(work)} -> {new_path.relative_to(work)}")

    # 6. Verify no old references remain
    remaining = 0
    for smali_dir in smali_dirs:
        for f in smali_dir.rglob('*'):
            if f.is_file() and old_dots.encode() in f.read_bytes():
                remaining += 1
    if remaining == 0:
        print(f"  [+] Verified: zero old package references remain")
    else:
        print(f"  [!] Warning: {remaining} files still contain old package references")
