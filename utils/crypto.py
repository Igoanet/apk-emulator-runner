"""
AES-256-CBC crypto helper for server-side file encryption.
Dropper and server share the same 32-byte key.
"""
import os
import struct
import hashlib

def _derive_key(seed: str) -> bytes:
    """Derive a 32-byte AES key from a seed string."""
    return hashlib.sha256(seed.encode()).digest()

def encrypt_file(input_path: str, output_path: str, key_seed: str = "dropper-key-2026") -> str:
    """
    Encrypt a file with AES-256-CBC.
    Output format: [16-byte IV][encrypted data]
    """
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        raise RuntimeError("pycryptodome required: pip install pycryptodome")

    key = _derive_key(key_seed)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv

    with open(input_path, 'rb') as f:
        plaintext = f.read()

    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

    with open(output_path, 'wb') as f:
        f.write(iv + ciphertext)

    return output_path

def decrypt_bytes(data: bytes, key_seed: str = "dropper-key-2026") -> bytes:
    """Decrypt AES-256-CBC bytes."""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError:
        raise RuntimeError("pycryptodome required: pip install pycryptodome")

    if len(data) < 16:
        raise ValueError("Data too short for IV")

    key = _derive_key(key_seed)
    iv = data[:16]
    ciphertext = data[16:]

    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)


def encrypt_apk(apk_path: str, output_dir: str, key_seed: str = "dropper-key-2026") -> str:
    """Encrypt an APK and return the output path."""
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.basename(apk_path).replace('.apk', '')
    out_path = os.path.join(output_dir, f"{base}.enc")
    encrypt_file(apk_path, out_path, key_seed)
    return out_path
