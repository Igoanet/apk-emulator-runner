// Scoped devices — GET /api/panel/devices Bearer session se sirf ISI user ke
// slots/links ke devices deta hai (multi-tenant isolation). main + details
// dono screens yahi source use karti hain — bundled CLIENTS fixture nahi.

import { Client } from '@/constants/panelData';
import { ensureDevSession, panelAuthHeaders } from '@/lib/panelSession';
import { DEV_PREVIEW, FAKE_DEVICES, FAKE_MESSAGES } from '@/lib/devPreview';

import { API_BASE } from './apiBase';

export type ApiDevice = {
  id: string; model: string; label: string; sim: number; simLabel: string;
  number: string; online: boolean; slotId: string; upiPin?: string; favorite?: boolean;
  batteryLevel?: number | null; networkIp?: string; registeredAt?: number;
  lastOnlineAt?: number; appUninstalled?: boolean; sim2Label?: string; sim2Number?: string;
  deviceLabel?: string;   // 🏷️ category tag (4 fixed types) — RTDB deviceLabel
  deviceLabelAt?: number; // tag set hone ka ts
};

// ms timestamp → Gian panel format 'DD-MM-YYYY | hh:mm am'. 0/missing → '—'.
function fmtTs(ms?: number): string {
  if (!ms || ms <= 0) return '—';
  const d = new Date(ms);
  const dd = String(d.getDate()).padStart(2, '0');
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  let h = d.getHours();
  const ampm = h >= 12 ? 'pm' : 'am';
  h = h % 12 || 12;
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${dd}-${mo}-${d.getFullYear()} | ${h}:${mi} ${ampm}`;
}

export function toClient(d: ApiDevice, i: number): Client {
  return {
    index: i + 1,
    id: d.id,
    slot: 'Slot 1',
    slotTag: d.slotId,
    label: d.label ?? '',
    labelTime: '',
    phone: d.number || 'N/A',
    upiPin: d.upiPin || '—', // server se real UPI pin (device node ka upiPin field)
    favorite: d.favorite === true,
    model: d.model,
    battery: typeof d.batteryLevel === 'number' ? d.batteryLevel : -1, // -1 = kabhi report nahi hua → UI 'N/A'
    ip: d.networkIp || 'N/A',
    date: fmtTs(d.registeredAt),  // install/registration date
    last: fmtTs(d.lastOnlineAt),  // last seen
    tag: d.deviceLabel ?? '',          // 🏷️ 4-type category label
    tagTime: fmtTs(d.deviceLabelAt),   // kab set hua
    uninstalled: d.appUninstalled === true,
    status: d.online ? 'Online' : 'Offline',
    online: d.online,
    device: d.model,
    sim1: [d.simLabel, d.number].filter(Boolean).join(' · ') || '—', // 'Jio · +91…' format
    sim2: [d.sim2Label, d.sim2Number].filter(Boolean).join(' · ') || '—',
    sent: 0,
    received: 0,
    notes: [],
    messages: [],
  };
}

// Loading placeholder — details screen ka initial state (fetch ke baad replace).
export function emptyClient(id: string): Client {
  return toClient(
    { id, model: '…', label: '', sim: 1, simLabel: '—', number: 'N/A', online: false, slotId: '' },
    0,
  );
}

// Sirf isi user ke devices (Bearer session scope). Fail pe throw — caller decide kare.
// 401 pe dev-session leke EK baar retry (dev preview me app bina login ke /main pe
// atak jaati thi — poll hi token recover kar le, reload ki zaroorat na pade).
export async function fetchMyDevices(): Promise<Client[]> {
  // DEV PREVIEW: server ke bina fake devices (lib/devPreview.ts) — sirf jab flag on ho.
  if (DEV_PREVIEW) return FAKE_DEVICES.map(toClient);
  let r = await fetch(`${API_BASE}/api/panel/devices`, { headers: panelAuthHeaders() });
  if (r.status === 401 && (await ensureDevSession(API_BASE))) {
    r = await fetch(`${API_BASE}/api/panel/devices`, { headers: panelAuthHeaders() });
  }
  const data = (await r.json().catch(() => ({}))) as { devices?: ApiDevice[] };
  if (!r.ok) throw new Error(`http_${r.status}`);
  return (data.devices ?? []).map(toClient);
}

// ---- Live device data (RTDB via API) — SMS log / send / delete ----

// 🏷️ Category label set/clear — RTDB deviceLabel pe likhta hai (Gian convention,
// isFavorite jaisa). DEV_PREVIEW me fake device mutate hota hai taaki 10s poll
// pe bhi tag bana rahe (session-local preview).
export async function setDeviceTagApi(deviceId: string, tag: string): Promise<boolean> {
  if (DEV_PREVIEW) {
    const d = FAKE_DEVICES.find((x) => x.id === deviceId);
    if (d) { d.deviceLabel = tag; d.deviceLabelAt = tag ? Date.now() : 0; }
    return true;
  }
  try {
    const r = await fetch(`${API_BASE}/api/panel/devices/label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
      body: JSON.stringify({ deviceId, label: tag }),
    });
    // RTDB write fail pe route 200 + {ok:false} deta hai — sirf HTTP 2xx dekh ke
    // success mat maano (code-review): body.ok bhi true hona chahiye.
    const data = (await r.json().catch(() => ({}))) as { ok?: boolean };
    return r.ok && data.ok === true;
  } catch {
    return false;
  }
}

export type ApiMessage = { id: string; from: string; body: string; time: string; type: string };

// Device ka SMS log — live RTDB se (Gian protocol: deviceMessages/<id>).
export async function fetchDeviceMessages(deviceId: string): Promise<ApiMessage[]> {
  // DEV PREVIEW: fake SMS log (online fake devices pe) — baaki khali list.
  if (DEV_PREVIEW) return FAKE_MESSAGES[deviceId] ?? [];
  const r = await fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/messages`, {
    headers: panelAuthHeaders(),
  });
  const data = (await r.json().catch(() => ({}))) as { messages?: ApiMessage[] };
  if (!r.ok) throw new Error(`http_${r.status}`);
  return data.messages ?? [];
}

// Send SMS — device pe actions/sendSms command; acked=true matlab device ne confirm kiya.
export async function sendSmsToDevice(
  deviceId: string,
  to: string,
  message: string,
  sim: number,
): Promise<{ acked: boolean; sendOk: boolean }> {
  // DEV PREVIEW: mutation inert — fake success taaki UI ka sent-flow dikhe, server pe kuch nahi jata.
  if (DEV_PREVIEW) return { acked: true, sendOk: true };
  const r = await fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/sms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
    body: JSON.stringify({ to, message, sim }),
  });
  const data = (await r.json().catch(() => ({}))) as { acked?: boolean; sendOk?: boolean };
  if (!r.ok) throw new Error(`http_${r.status}`);
  return { acked: data.acked === true, sendOk: data.sendOk === true };
}

// Call + SMS forwarding state — reference V7 protocol (actions/callForward +
// actions/forwardSms). GET = dialog prefill, POST = apply. DEV_PREVIEW inert.
export interface ForwardingState {
  callTo: string;
  callFrom: number;
  callOn: boolean;
  smsTo: string;
  smsOn: boolean;
}

export async function fetchForwarding(deviceId: string): Promise<ForwardingState> {
  if (DEV_PREVIEW) return { callTo: '', callFrom: 0, callOn: false, smsTo: '', smsOn: false };
  const r = await fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/forwarding`, {
    headers: panelAuthHeaders(),
  });
  const data = (await r.json().catch(() => ({}))) as { forwarding?: ForwardingState };
  if (!r.ok || !data.forwarding) throw new Error(`http_${r.status}`);
  return data.forwarding;
}

export async function applyForwarding(
  deviceId: string,
  state: { callTo: string; callOn: boolean; smsTo: string; smsOn: boolean },
): Promise<void> {
  if (DEV_PREVIEW) return;
  const r = await fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/forwarding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
    body: JSON.stringify(state),
  });
  if (!r.ok) {
    const data = (await r.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error || `http_${r.status}`);
  }
}

// Ek SMS record delete (deviceMessages/<id>/<key>) — server pe Telegram OTP gate
// hai (owner rule: har SMS/device delete pe OTP). Error code throw hota hai
// (wrong_otp / otp_expired / otp_required) taaki UI dialog me sahi message dikhaye.
export async function deleteDeviceSms(deviceId: string, key: string, otp: string): Promise<void> {
  // DEV PREVIEW: no-op — server pe delete nahi jata (fake IDs + real data collision se bachna).
  if (DEV_PREVIEW) return;
  const r = await fetch(
    `${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/messages/${encodeURIComponent(key)}`,
    { method: 'DELETE', headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() }, body: JSON.stringify({ otp }) },
  );
  if (!r.ok) {
    const data = (await r.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error || `http_${r.status}`);
  }
}

// Destructive actions (SMS/device delete) ka Telegram OTP maango — user ke apne
// Telegram chat pe jata hai. 'cooldown' = 30s ke andar dobara request — pichla
// OTP abhi bhi valid hai, dialog khol sakte ho.
export async function requestActionOtp(): Promise<{ status: 'ok' | 'cooldown' | 'fail'; retryAfterSec?: number }> {
  // DEV PREVIEW: OTP dialog UI dikhe isliye 'ok' — par Telegram pe koi OTP nahi jata.
  if (DEV_PREVIEW) return { status: 'ok' };
  try {
    const r = await fetch(`${API_BASE}/api/panel/app/otp/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
      body: '{}',
    });
    if (r.ok) return { status: 'ok' };
    const data = (await r.json().catch(() => ({}))) as { error?: string; retryAfterSec?: number };
    return {
      status: data.error === 'cooldown' ? 'cooldown' : 'fail',
      retryAfterSec: typeof data.retryAfterSec === 'number' ? data.retryAfterSec : undefined,
    };
  } catch {
    return { status: 'fail' };
  }
}

// ⭐ Star/favorite toggle — server RTDB me isFavorite likhta hai (Gian protocol).
// 401 pe dev-session self-heal + retry (fetchMyDevices jaisa pattern).
export async function setDeviceFavoriteApi(deviceId: string, favorite: boolean): Promise<boolean> {
  // DEV PREVIEW: local success — server write nahi.
  if (DEV_PREVIEW) return true;
  try {
    const call = () =>
      fetch(`${API_BASE}/api/panel/devices/favorite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ deviceId, favorite }),
      });
    let r = await call();
    if (r.status === 401) {
      await ensureDevSession(API_BASE);
      r = await call();
    }
    return r.ok;
  } catch {
    return false;
  }
}
