#!/usr/bin/env python3
"""gmail_login.py — emulator pe Google (Gmail) account sign-in.

Flow (API 33, google_apis image — AOSP image me ye kaam nahi karega):
  1. Settings → Add account → Google
  2. Email field → email type → Next
  3. Password field → password type → Next
  4. Terms / Google services screens → I agree / Accept / Skip
  5. `dumpsys account` se confirm ki com.google account add hua

Google "Couldn't sign in" / CAPTCHA / "Verify it's you" dikhaye to screenshot
bana ke fail report karta hai — automated sign-in ko Google kabhi kabhi
challenge karta hai, wo manual intervention maangta hai.

Style np_manager_v3.py jaisa: stdlib only, adb -s <serial>, uiautomator dump.
Env: GMAIL_EMAIL, GMAIL_PASS, optional SCREENSHOT_DIR, EMULATOR_SERIAL.
"""

import os
import re
import subprocess
import sys
import time

SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/fud-work/screenshots"))
EMAIL = os.environ.get("GMAIL_EMAIL", "").strip()
PASSWORD = os.environ.get("GMAIL_PASS", "")
SERIAL = os.environ.get("EMULATOR_SERIAL", "emulator-5554")


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return type("obj", (object,), {"stdout": "", "stderr": str(e), "returncode": 1})()


def adb(cmd, timeout=30):
    return run(f"adb -s {SERIAL} {cmd}", timeout)


def screenshot(name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"gmail_{name}.png")
    adb(f"shell screencap -p /sdcard/gmail_{name}.png")
    adb(f"pull /sdcard/gmail_{name}.png {path}")
    print(f"[SCREEN] gmail_{name}")


def get_xml(save_as=None):
    adb("shell uiautomator dump /sdcard/window_dump.xml")
    xml = adb("shell cat /sdcard/window_dump.xml").stdout
    if save_as:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        with open(os.path.join(SCREENSHOT_DIR, f"gmail_{save_as}.xml"), "w") as f:
            f.write(xml)
        print(f"[XML:gmail_{save_as}] {xml[:2000]}")
    return xml


def find_text(xml, text):
    pat = re.compile(
        r'<node[^>]*text="' + re.escape(text) + r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    )
    m = pat.search(xml)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None


def tap(x, y, desc=""):
    adb(f"shell input tap {x} {y}")
    print(f"[*] Tap {desc} @ ({x},{y})")
    time.sleep(1)


def tap_text(xml, text, desc=""):
    c = find_text(xml, text)
    if c:
        tap(c[0], c[1], desc or text)
        return True
    return False


def tap_first_edittext(xml, desc="field"):
    pat = re.compile(
        r'<node[^>]*class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    )
    m = pat.search(xml)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        tap((x1 + x2) // 2, (y1 + y2) // 2, desc)
        return True
    return False


def input_text(text):
    # `input text`: space -> %s; single-quote shell-safe
    safe = text.replace(" ", "%s")
    adb("shell input text '" + safe.replace("'", "'\\''") + "'", timeout=15)
    time.sleep(1)


def detect_block(xml):
    low = xml.lower()
    for marker in (
        "couldn't sign in", "couldn\u2019t sign in", "verify it", "verify it's you",
        "captcha", "try again", "too many", "unusual traffic", "phone number",
        "wrong password", "incorrect",
    ):
        if marker in low:
            return marker
    return None


def dump_texts(xml, tag):
    # Screen ke saare visible text/content-desc log karo — debugging ke liye
    texts = re.findall(r'text="([^"]+)"', xml) + re.findall(r'content-desc="([^"]+)"', xml)
    texts = [t for t in texts if t.strip()][:40]
    print(f"[TEXTS:{tag}] " + " | ".join(texts))


def wait_for_edittext(tag, tries=6):
    for _ in range(tries):
        xml = get_xml(tag)
        block = detect_block(xml)
        if block:
            print(f"[!] Google sign-in challenge/block: '{block}' — automation yahan nahi chal sakta")
            dump_texts(xml, f"blocked_{tag}")
            screenshot(f"blocked_{tag}")
            return None, block
        if tap_first_edittext(xml, f"{tag} field"):
            return xml, None
        time.sleep(3)
    print(f"[!] {tag}: field nahi mila")
    screenshot(f"no_{tag}")
    return None, "field_not_found"


def main():
    if not EMAIL or not PASSWORD:
        print("[!] GMAIL_EMAIL/GMAIL_PASS set nahi — Gmail sign-in skip")
        return 0

    print(f"[*] Gmail sign-in shuru — {EMAIL}")
    # Boot ke turant baad settings slow hoti hai — settle time
    time.sleep(5)

    # 1. Add-account screen → Google
    adb("shell am start -a android.settings.ADD_ACCOUNT_SETTINGS")
    time.sleep(5)
    xml = get_xml("add_account")
    screenshot("add_account")
    if not tap_text(xml, "Google", "Google account type"):
        print("[!] 'Google' option nahi mila — image google_apis hai na? AOSP me ye kaam nahi karta.")
        screenshot("no_google_option")
        return 1
    time.sleep(8)  # sign-in activity load hone me time lagta hai

    # 2. Email
    xml, err = wait_for_edittext("email_screen")
    if err:
        return 1
    input_text(EMAIL)
    xml = get_xml()
    if not (tap_text(xml, "Next", "email Next") or tap_text(xml, "NEXT", "email NEXT")):
        adb("shell input keyevent 66")  # ENTER fallback
    time.sleep(8)
    screenshot("after_email")

    # 3. Password
    xml, err = wait_for_edittext("password_screen")
    if err:
        return 1
    input_text(PASSWORD)
    xml = get_xml()
    if not (tap_text(xml, "Next", "password Next") or tap_text(xml, "NEXT", "password NEXT")):
        adb("shell input keyevent 66")

    # 4. Password ke baad — 2FA / verify / terms screens handle karo.
    # User GitHub Actions ke LIVE logs dekh raha hota hai: number challenge ya
    # "check your phone" aaya to log me BADA banner print hota hai; user apne
    # phone pe approve karta hai, hum poll karke flow ko aage badha dete hain.
    print("[*] Password submit ho gaya — ab 2FA/verify/terms screens handle hongi")
    print("[*] Agar phone pe Google prompt aaye to use approve kar do — main wait kar raha hoon")
    deadline = time.time() + 600  # user approval ka max 10 min wait
    announced_number = announced_phone = False
    logged_in = False
    while time.time() < deadline:
        xml = get_xml()
        low = xml.lower()

        # Hard fail signals — inpe turant rukna hai
        for bad in ("couldn't sign in", "couldn\u2019t sign in", "wrong password", "too many"):
            if bad in low:
                print(f"[!] Sign-in fail: '{bad}'")
                dump_texts(xml, "hard_block")
                screenshot("hard_block")
                return 1

        # Number challenge — emulator pe 2-digit number dikhta hai, phone pe match karna hota hai
        if not announced_number:
            nums = [t.strip() for t in re.findall(r'text="([^"]+)"', xml) if re.fullmatch(r"\d{2}", t.strip())]
            if nums:
                print("=" * 64)
                print(f"### 2FA NUMBER EMULATOR PE DIKHA: {nums[0]} ###")
                print("### Apne PHONE pe isi number wala option tap karo! ###")
                print("=" * 64)
                announced_number = True

        # "Check your phone" type screens — user ko phone pe action lena hai
        if not announced_phone and (
            "check your phone" in low or "check your other device" in low
            or "tap yes" in low or "trying to sign" in low
        ):
            print("=" * 64)
            print("### GOOGLE ka prompt aapke PHONE pe gaya hai ###")
            print("### Phone pe 'Yes, it's me' tap karke approve karo! ###")
            print("=" * 64)
            announced_phone = True

        # 2FA approve hote hi account background me add ho jata hai
        r = adb("shell dumpsys account", timeout=15)
        if EMAIL.lower() in r.stdout.lower():
            print(f"[+] Account add ho gaya (dumpsys me mila) — {EMAIL}")
            logged_in = True
            break

        # Emulator pe jo known button aaye (terms/agree/next/yes) tap karo
        tapped = False
        for label in (
            "Yes, it's me", "Yes, it\u2019s me", "I agree", "I AGREE",
            "Accept", "ACCEPT", "Next", "NEXT", "Skip", "SKIP",
            "No thanks", "NO THANKS", "Done", "DONE",
        ):
            if tap_text(xml, label, f"post: {label}"):
                time.sleep(4)
                tapped = True
                break
        if not tapped:
            time.sleep(4)

    if not logged_in:
        print("[!] 5 min me 2FA/approval complete nahi hua — live log me banner aaya tha?")
        dump_texts(get_xml(), "timeout_screen")
        screenshot("timeout_screen")
        return 1

    screenshot("after_password")
    dump_texts(get_xml(), "after_password")

    # 5. Confirm — com.google account add hua? Registration me lag lagta hai — poll karo
    time.sleep(3)
    confirmed = False
    for i in range(6):
        r = adb("shell dumpsys account", timeout=15)
        if EMAIL.lower() in r.stdout.lower():
            confirmed = True
            break
        print(f"[*] dumpsys account me abhi nahi mila (try {i+1}/6) — 10s wait")
        time.sleep(10)

    if not confirmed:
        # Fallback: Settings → Accounts screen pe UI me dekho
        adb("shell am start -a android.settings.SYNC_SETTINGS")
        time.sleep(5)
        xml = get_xml("accounts_screen")
        dump_texts(xml, "accounts_screen")
        screenshot("accounts_screen")
        if EMAIL.lower() in xml.lower():
            confirmed = True

    screenshot("final")
    if confirmed:
        print(f"[+] Gmail login confirmed — {EMAIL} emulator pe add ho gaya")
        return 0
    print("[!] Account list me email nahi mila — login shayad poora nahi hua, screenshots dekh lo")
    return 1


if __name__ == "__main__":
    sys.exit(main())
