// Stable per-device ID — first launch pe banti hai aur AsyncStorage me rehti hai.
// Server isi se pehchaanta hai ki ye device trusted hai (owner rule: OTP sirf
// PEHLI baar — verify hone ke baad us device pe lifetime access, dobara OTP nahi).
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'igoan.deviceId';
let cached: string | null = null;

function makeId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export async function getDeviceId(): Promise<string> {
  if (cached) return cached;
  try {
    const existing = await AsyncStorage.getItem(KEY);
    if (existing) {
      cached = existing;
      return existing;
    }
    const id = makeId();
    await AsyncStorage.setItem(KEY, id);
    cached = id;
    return id;
  } catch {
    // storage fail — memory fallback (is app-session me stable rahega)
    if (!cached) cached = makeId();
    return cached;
  }
}
