// Auto Verify API client — panel app ↔ api-server /api/auto-verify/*.
// KEY hi auth hai (bot se mili hui); har call usi key ke scope me hota hai.

import EventSource from 'react-native-sse';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { API_BASE } from './apiBase';
import { panelAuthHeaders } from './panelSession';
const KEY_STORAGE = 'av_key_v1';

export interface AvKeyStatus {
  exists: boolean;
  isAdmin: boolean;
  channelTitle?: string;
  memberCount?: number;
  error?: string;
}

export interface AvEvent {
  id: string;
  userChatId: number;
  channelChatId: number;
  channelTitle: string;
  text: string;
  sender?: string;
  ts: number;
}

export interface AvJob {
  id: number;
  state: 'queued' | 'sending' | 'delivered';
  number: string;
  body: string;
}

export async function loadSavedKey(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(KEY_STORAGE)) ?? '';
  } catch {
    return '';
  }
}

export async function saveKey(key: string): Promise<void> {
  try {
    if (key) await AsyncStorage.setItem(KEY_STORAGE, key);
    else await AsyncStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage fail — session ke liye in-memory kaafi */
  }
}

// null = server/bot unreachable (caller "CHECKING…" rakh ke retry kare)
export async function checkKeyStatus(key: string): Promise<AvKeyStatus | null> {
  try {
    const r = await fetch(`${API_BASE}/api/auto-verify/key-status?key=${encodeURIComponent(key)}`);
    if (!r.ok) return null;
    return (await r.json()) as AvKeyStatus;
  } catch {
    return null;
  }
}

// Channel status (active/inactive) — session-authed, connect se pehle/refresh pe.
// null = server unreachable.
export async function channelStatus(chatId: string): Promise<AvKeyStatus | null> {
  try {
    const r = await fetch(
      `${API_BASE}/api/auto-verify/channel-status?chatId=${encodeURIComponent(chatId)}`,
      { headers: { ...panelAuthHeaders() } },
    );
    if (!r.ok) return null;
    return (await r.json()) as AvKeyStatus;
  } catch {
    return null;
  }
}

export interface AvConnectResult {
  ok: boolean;
  active?: boolean;
  key?: string;
  channelTitle?: string;
  memberCount?: number;
  error?: string;
}

// Direct connect (owner flow): chat ID paste → server verify (bot admin?) →
// ACTIVE hote hi key AUTO-issue. Telegram bot pe Generate Key ki zaroorat nahi.
export async function connectChannel(chatId: string): Promise<AvConnectResult> {
  try {
    const r = await fetch(`${API_BASE}/api/auto-verify/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
      body: JSON.stringify({ chatId }),
    });
    const data = (await r.json().catch(() => ({}))) as AvConnectResult;
    if (!r.ok) return { ok: false, error: data.error ?? `http_${r.status}`, channelTitle: data.channelTitle };
    return data;
  } catch {
    return { ok: false, error: 'network' };
  }
}

export async function fetchRecent(key: string): Promise<AvEvent[]> {
  try {
    const r = await fetch(`${API_BASE}/api/auto-verify/recent?key=${encodeURIComponent(key)}`);
    if (!r.ok) return [];
    const data = (await r.json()) as { events?: AvEvent[] };
    return data.events ?? [];
  } catch {
    return [];
  }
}

// SSE stream — naya channel post aate hi onSms fire hota hai (~1s).
// Returns close() — screen unmount / key change pe call karo.
// onReady fires with server timestamp when connection is established —
// use this as serverListenSince to drop stale replayed events.
export function openStream(
  key: string,
  onSms: (ev: AvEvent) => void,
  onStateChange?: (live: boolean) => void,
  onReady?: (serverTs: number) => void,
): () => void {
  // 'sms' + 'ready' custom events
  const es = new EventSource<'sms' | 'ready'>(`${API_BASE}/api/auto-verify/stream?key=${encodeURIComponent(key)}`);
  es.addEventListener('open', () => onStateChange?.(true));
  es.addEventListener('ready', (e: any) => {
    try {
      if (e?.data) {
        const payload = JSON.parse(e.data) as { ts?: number };
        if (typeof payload.ts === 'number') onReady?.(payload.ts);
      }
    } catch { /* ignore */ }
  });
  es.addEventListener('sms', (e: any) => {
    try {
      if (e?.data) onSms(JSON.parse(e.data) as AvEvent);
    } catch {
      /* bad event skip */
    }
  });
  es.addEventListener('error', () => onStateChange?.(false));
  es.addEventListener('close', () => onStateChange?.(false));
  return () => {
    try {
      es.close();
    } catch {
      /* ignore */
    }
  };
}

export async function avSend(
  key: string,
  number: string,
  text: string,
  simSlot?: 1 | 2,
): Promise<{ ok: true; job: AvJob } | { ok: false; error: string }> {
  try {
    const r = await fetch(`${API_BASE}/api/auto-verify/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, number, text, simSlot }),
    });
    const data = (await r.json().catch(() => ({}))) as { job?: AvJob; error?: string };
    if (!r.ok || !data.job) return { ok: false, error: data.error ?? `http_${r.status}` };
    return { ok: true, job: data.job };
  } catch {
    return { ok: false, error: 'network' };
  }
}

export async function fetchAvJob(key: string, id: number): Promise<AvJob | null> {
  try {
    const r = await fetch(
      `${API_BASE}/api/auto-verify/job?key=${encodeURIComponent(key)}&id=${id}`,
    );
    if (!r.ok) return null;
    return ((await r.json()) as { job: AvJob }).job;
  } catch {
    return null;
  }
}

// Delivery result → owner ke Telegram DM. confirmDelivery=true pe response me
// Telegram confirmation aati hai (max ~10s wait).
export async function ackEvent(
  key: string,
  id: string,
  result: { ok: boolean; to: string; message?: string; error?: string },
): Promise<{ acked: boolean; delivered?: boolean }> {
  try {
    const r = await fetch(`${API_BASE}/api/auto-verify/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, id, ...result, confirmDelivery: true }),
    });
    const data = (await r.json().catch(() => ({}))) as {
      acked?: boolean;
      delivery?: { delivered?: boolean };
    };
    return { acked: data.acked === true, delivered: data.delivery?.delivered };
  } catch {
    return { acked: false };
  }
}
