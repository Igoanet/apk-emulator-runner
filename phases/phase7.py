"""Phase 7: Hex Editor (PC) — DEX magic + checksum + SHA-1 modify.

Replicates HxD manual edits:
1. Change DEX magic: dex\n035\x00 → dex\n037\x00
2. Zero out Adler32 checksum at offset 8
3. Randomize SHA-1 signature at offset 12

DEX header format:
  offset 0x00: magic[8]     = "dex\n035\0"
  offset 0x08: checksum[4]  = adler32 (zeroed)
  offset 0x0C: signature[20] = SHA-1 (randomized)
"""
import os, zipfile, random
from config import TEMP_DIR
from utils.logger import setup_logger

logger = setup_logger()

def run(input_apk):
    logger.info("="*60)
    logger.info("[*] PHASE 7: Hex Editor — DEX Magic/Checksum/SHA-1")
    logger.info("="*60)

    out_apk = str(TEMP_DIR / "hex_modified.apk")

    # Proper ZIP rewrite — preserves structure and compression
    with zipfile.ZipFile(input_apk, 'r') as zin:
        with zipfile.ZipFile(out_apk, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.endswith('.dex') and len(data) > 32:
                    dex = bytearray(data)
                    # 1. Change magic dex\n035\x00 → dex\n037\x00
                    if dex[:4] == b'dex\n':
                        dex[4:8] = b'037\x00'
                        logger.info(f"    DEX magic: 035→037 in {info.filename}")
                    # 2. Zero out adler32 at offset 8
                    if len(dex) >= 12:
                        dex[8:12] = b'\xFF\xFF\xFF\xFF'
                        logger.info(f"    Adler32: zeroed in {info.filename}")
                    # 3. Randomize SHA-1 signature at offset 12 (20 bytes)
                    if len(dex) >= 32:
                        dex[12:32] = bytes(random.randint(0, 255) for _ in range(20))
                        logger.info(f"    SHA-1: randomized in {info.filename}")
                    data = bytes(dex)
                zout.writestr(info, data)

    logger.info(f"[+] Phase 7 Complete: {out_apk}")
    return out_apk
