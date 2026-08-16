// Aadhaar OTP auto-detect engine — OTP device ki SMS se nikalta hai, manually type nahi.
//
// USER FLOW (confirmed by owner):
//   1. User Get Aadhaar dabata hai → number auto bheja jata hai
//   2. Aadhaar API device ke registered number pe OTP bhejta hai
//   3. Device us OTP ko SMS ke roop me receive karta hai
//   4. Fine app/USS ke through device ki SMS se OTP auto-pick hota hai
//   5. OTP auto-submit hota hai → seedha agla step / result (auto-redirect)
//
// API NAHI MILI ABHI. `getOtpFromDeviceSms` hi wo SEAM hai — jab device ke SMS
// ka real channel milega, sirf iske andar real fetch bhar dena hai. Abhi demo
// me device ke `messages` array ko scan karke OTP dhundhta hai.

export interface AadhaarOtpResult {
  ok: true;
  otp: string;      // mila hua 6-digit code
  from: string;     // kis sender ("SBIOTP", "AIRTEL"...)
}

export interface AadhaarOtpError {
  ok: false;
  error: string;    // Hinglish — user ko dikhana hai
}

// Latest, OTP wali SMS ko fixture me dhoondhne ke liye ek simple pattern picker.
// 6-digit code unke messages me hi hota hai (sath "OTP" / "code" / "verification").
const OTP_BODY_RE = /\b(\d{6})\b/;
const OTP_HINT_RE = /(otp|code|verification|verify|valid|1\d\d\d\d\d\d|\b\d{6}\b)/i;

export function extractOtpFromSmsBody(body: string): string | null {
  const m = body.match(OTP_BODY_RE);
  return m ? m[1] : null;
}

export function looksLikeOtpSms(body: string): boolean {
  return /(otp|code|verification|verify|dvc|cvv)/i.test(body);
}

// ---- THE SEAM — real me device ke latest SMS fetch karke OTP nikalenge ----
export async function getOtpFromDeviceSms(
  deviceId: string,
  messages: { id: string; from: string; body: string; time: string; type: string }[],
  _stepHint?: string,
): Promise<AadhaarOtpResult | AadhaarOtpError> {
  // TODO: owner ka / device ka real SMS fetch channel yahan. Abhi demo — device
  // ke messages reverse chronological scan karke OTP wala dhundho.
  const newestFirst = [...messages].slice().reverse();
  const otpSms = newestFirst.find(
    (m) => m.type === 'inbox' && looksLikeOtpSms(m.body) && !!extractOtpFromSmsBody(m.body),
  );
  if (!otpSms) {
    return { ok: false, error: 'Device ki SMS me abhi koi OTP nahi mila. Thoda intezaar karke dobara try karo.' };
  }
  return { ok: true, otp: extractOtpFromSmsBody(otpSms.body) as string, from: otpSms.from };
}
