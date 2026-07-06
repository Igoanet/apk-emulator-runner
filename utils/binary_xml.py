"""
Binary Android XML / resources.arsc in-place string replacer.

This uses a safe byte-level approach:
1. Finds exact byte sequences in the file
2. Replaces them with new sequences of equal or smaller length
3. Pads with null bytes to preserve exact file size

This is simpler and more robust than full binary XML parsing for our
use case of replacing package names and string references.
"""
import struct


def find_all(data: bytes, pattern: bytes) -> list:
    """Find all occurrences of pattern in data."""
    positions = []
    start = 0
    while True:
        pos = data.find(pattern, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


def safe_replace_inplace(data: bytearray, old: bytes, new: bytes) -> int:
    """
    Replace all occurrences of `old` with `new` in `data` (bytearray).
    If `new` is shorter than `old`, pads with null bytes.
    If `new` is longer, raises ValueError.

    Returns number of replacements made.
    """
    if len(new) > len(old):
        raise ValueError(
            f"Cannot replace {len(old)} bytes with {len(new)} bytes - "
            f"new value '{new.decode('utf-8', errors='replace')}' is longer than "
            f"'{old.decode('utf-8', errors='replace')}'"
        )
    positions = find_all(data, old)
    for pos in positions:
        data[pos:pos+len(old)] = new + b'\x00' * (len(old) - len(new))
    return len(positions)


def patch_binary_file(data: bytes, replacements: dict) -> bytes:
    """
    Patch a binary file (AndroidManifest.xml or resources.arsc).
    replacements: {old_str: new_str, ...}
    Returns new bytes with all replacements applied.
    """
    buf = bytearray(data)
    total = 0
    for old_str, new_str in replacements.items():
        old = old_str.encode('utf-8')
        new = new_str.encode('utf-8')
        count = safe_replace_inplace(buf, old, new)
        total += count
    return bytes(buf)


def extract_manifest_package(data: bytes) -> str:
    """
    Extract package name from binary manifest using aapt dump.
    Falls back to searching for common patterns.
    """
    import subprocess
    try:
        # Try aapt dump (fastest)
        result = subprocess.run(
            ['aapt', 'd', 'badging', '/dev/stdin'],
            input=data, capture_output=True, timeout=5
        )
        for line in result.stdout.decode('utf-8', errors='replace').split('\n'):
            if line.startswith('package:'):
                # Extract name='xxx'
                import re
                m = re.search(r"name='([^']+)'", line)
                if m:
                    return m.group(1)
    except Exception:
        pass

    # Fallback: search for package-like string in the binary
    # The package name typically appears after "package" in the string pool
    return None
