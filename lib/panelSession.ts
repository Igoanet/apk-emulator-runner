// Panel session token — AsyncStorage pe persist hota hai taaki app restart pe bhi
// session bacha rahe (owner rule: first login OTP, phir us device pe lifetime
// access). Scoped API calls (slots/devices/ping) isi token se apni identity prove
// karti hain — bina token ke server sirf 401 deta hai, kisi aur user ka data kabhi nahi.

import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'igoan.panelSession';

export const panelSession: { token: string | null } = { token: null };

export function setPanelToken(token: string | null): void {
  panelSession.token = token;
  // fire-and-forget persist — storage fail pe bhi in-memory session kaam karta hai
  if (token) AsyncStorage.setItem(STORAGE_KEY, token).catch(() => {});
  else AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
}

// App launch pe saved token wapas laao. null = login screen dikhani hai.
export async function loadPanelToken(): Promise<string | null> {
  try {
    const t = await AsyncStorage.getItem(STORAGE_KEY);
    panelSession.token = t;
    return t;
  } catch {
    return null;
  }
}

export function panelAuthHeaders(): Record<string, string> {
  return panelSession.token ? { Authorization: `Bearer ${panelSession.token}` } : {};
}

// DEV PREVIEW (owner request 2026-08-14): bypass mode me app bina login ke andar
// jaati hai — token missing ho to dev-login se session le aao taaki upload/slots
// jaise scoped APIs 401 na dein. Server pe ye route SIRF PANEL_DEV_BYPASS=1 hone
// pe exist karta hai (production me 404 → false → normal unauthorized flow).
export async function ensureDevSession(apiBase: string): Promise<boolean> {
  if (panelSession.token) return true;
  try {
    const r = await fetch(`${apiBase}/api/panel/app/dev-login`, { method: 'POST' });
    const data = await r.json().catch(() => ({}));
    if (r.ok && data.session?.token) {
      setPanelToken(data.session.token);
      return true;
    }
  } catch { /* server unreachable — caller apna normal error dikhayega */ }
  return false;
}
