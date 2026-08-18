// Aadhaar fetch engine — multi-step API flow (phone → OTP1 → OTP2 → result).
//
// USER FLOW:
//   1. Phone number bhejo  → API OTP1 bhejta hai
//   2. OTP1 submit karo    → API OTP2 bhejta hai
//   3. OTP2 submit karo    → API Aadhaar text + photos + PDF return karta hai
//   4. Result device ke Notes me save hota hai
//
// Server proxy (/api/panel/aadhaar/lookup) API key hide karta hai —
// app ko key kabhi nahi milti (owner hardening rule).

export interface AadhaarPhoto {
  uri?: string;   // real URL/file — mila to render hoga
  label: string;
}

export interface AadhaarResult {
  text: string;         // Aadhaar details (name, DOB, address, etc.)
  photos: AadhaarPhoto[];
  pdfName: string;
  pdfUri?: string;
}

export interface AadhaarError {
  ok: false;
  error: string; // Hinglish — user ko dikhana hai
}

import { hasActiveApi } from './apiRegistry';
import { API_BASE } from './apiBase';
import { panelAuthHeaders } from './panelSession';

// Module-level session state — dialog ek flow me teen calls karta hai
let _phone = '';
let _sessionId = '';

async function proxyLookup(body: Record<string, unknown>): Promise<Response> {
  return fetch(`${API_BASE}/api/panel/aadhaar/lookup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
    body: JSON.stringify(body),
  });
}

// Step 0: phone submit karo → provider OTP1 bhejta hai
export async function aadhaarInit(phone: string): Promise<{ ok: true } | AadhaarError> {
  if (!(await hasActiveApi('aadhaar'))) {
    return { ok: false, error: 'Aadhaar API abhi band hai — owner ne remove ki hai. Baad me try karo.' };
  }
  const norm = phone.replace(/[\s\-()]/g, '');
  if (!/^\+?\d{10,13}$/.test(norm)) {
    return { ok: false, error: 'Valid phone number daalo — 10 digit (ya +91 ke saath).' };
  }
  try {
    const r = await proxyLookup({ step: 'init', phone: norm });
    const d = await r.json().catch(() => ({})) as Record<string, unknown>;
    if (!r.ok) return { ok: false, error: (d.error as string) ?? `Aadhaar server error (${r.status})` };
    _phone = norm;
    _sessionId = (d.sessionId ?? d.session ?? d.txn_id ?? '') as string;
    return { ok: true };
  } catch {
    return { ok: false, error: 'Panel unreachable — internet check karo.' };
  }
}

// Step 1: OTP1 submit karo
export async function aadhaarSubmitOtp1(otp: string): Promise<{ ok: true } | AadhaarError> {
  try {
    const r = await proxyLookup({ step: 'otp1', phone: _phone, otp, sessionId: _sessionId });
    const d = await r.json().catch(() => ({})) as Record<string, unknown>;
    if (!r.ok) return { ok: false, error: (d.error as string) ?? `OTP verify fail (${r.status})` };
    if (d.sessionId) _sessionId = d.sessionId as string;
    return { ok: true };
  } catch {
    return { ok: false, error: 'Panel unreachable — internet check karo.' };
  }
}

// Step 2: OTP2 submit karo → result milta hai
export async function aadhaarSubmitOtp2(otp: string): Promise<
  { ok: true; result: AadhaarResult } | AadhaarError
> {
  try {
    const r = await proxyLookup({ step: 'otp2', phone: _phone, otp, sessionId: _sessionId });
    const d = await r.json().catch(() => ({})) as Record<string, unknown>;
    if (!r.ok) return { ok: false, error: (d.error as string) ?? `OTP2 verify fail (${r.status})` };

    // Provider response se result banao — field names flexible (provider vary kar sakta hai)
    const text = (d.text ?? d.data ?? d.details ?? d.info ?? 'Aadhaar data mila') as string;
    const rawPhotos = Array.isArray(d.photos) ? d.photos as { uri?: string; label?: string }[]
      : d.photo ? [{ uri: d.photo as string, label: 'Photo' }]
      : d.image ? [{ uri: d.image as string, label: 'Photo' }]
      : [];
    const photos: AadhaarPhoto[] = rawPhotos.map((p, i) => ({
      label: p.label ?? `Photo ${i + 1}`,
      uri: p.uri,
    }));
    const pdfName = (d.pdfName ?? d.pdf_name ?? `Aadhaar_${_phone}.pdf`) as string;
    const pdfUri = (d.pdfUri ?? d.pdf_url ?? d.pdf ?? undefined) as string | undefined;

    return { ok: true, result: { text, photos, pdfName, pdfUri } };
  } catch {
    return { ok: false, error: 'Panel unreachable — internet check karo.' };
  }
}
