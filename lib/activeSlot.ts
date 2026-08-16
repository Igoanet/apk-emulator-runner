import AsyncStorage from '@react-native-async-storage/async-storage';

// Active Firebase slot — user jis slot me "enter" karta hai wo yahan persist hota hai.
// Main screen isi ke hisaab se devices load/filter karta hai.

export interface ActiveSlot {
  id: string; // slot id, e.g. 'slot1'
  label: string; // display label, e.g. 'Slot 1'
  projectId?: string;
  databaseUrl?: string; // RTDB probe ke liye (connection test) — optional, purane saved entries me nahi hoga
}

const KEY = 'active_slot_v1';

export async function getActiveSlot(): Promise<ActiveSlot | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ActiveSlot;
  } catch {
    return null;
  }
}

export async function setActiveSlot(slot: ActiveSlot | null): Promise<void> {
  try {
    if (slot) await AsyncStorage.setItem(KEY, JSON.stringify(slot));
    else await AsyncStorage.removeItem(KEY);
  } catch {
    // storage fail hone pe silent — app abhi bhi default (all slots) pe chalti hai
  }
}
