"""File utilities."""
import os, shutil, hashlib
from pathlib import Path

WORK_DIR = Path("/home/runner/workspace")

def get_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def cleanup_temp():
    td = WORK_DIR / "temp"
    if td.exists():
        for f in td.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f)
            except:
                pass
