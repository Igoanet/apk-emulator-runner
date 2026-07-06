"""Pipeline logging with timestamps."""
import logging
import os
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("/home/runner/workspace/logs/pipeline.log")

def setup_logger(name="pipeline"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger

def get_last_lines(n=50):
    if not LOG_FILE.exists():
        return "No logs yet."
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return "".join(lines[-n:]) if lines else "No logs yet."
