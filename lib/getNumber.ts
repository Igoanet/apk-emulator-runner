// Get Number engine — device ka number unknown ho to pata karke laana.
//
// USER FLOW (confirmed):
//   1. Device ka number nahi pata (unknown) hota hai
//   2. Bot/API device pe ek particular TEXT bhijwaata hai
//   3. Device wahi text send kar deta hai
//   4. API us text ko pehchan leta hai aur DEVICE NUMBER return karta hai
//   - Get Number      → ek particular device ka
//   - Get Number All  → us Firebase/section ke saare devices ke numbers
//
// API NAHI MILI ABHI. Neeche `getDeviceNumber` hi wo SEAM hai — jab owner API
// dega, sirf iske andar real HTTP call bhar dena hai. Abhi demo/local mock hai.

export interface GetNumberResult {
  deviceId: string;
  number: string;   // device ka mila hua number
}

export interface GetNumberError {
  ok: false;
  error: string; // Hinglish — user ko dikhana hai
}

import { hasActiveApi } from './apiRegistry';

// Get Number — per-device: device pe text bhijwa ke uske number ka pata lagana.
export async function getDeviceNumber(
  deviceId: string,
  _hint?: string, // e.g. current/known number — API ko dekho
): Promise<{ ok: true; result: GetNumberResult } | GetNumberError> {
  // Owner-managed registry (bot ke API Management se) — API nahi bachi to feature band.
  if (!(await hasActiveApi('get_number'))) {
    return { ok: false, error: 'Get Number API abhi band hai — owner ne remove ki hai. Baad me try karo.' };
  }
  // TODO: owner ka API real call yahan (URL server-side registry me). Abhi demo — device ke collection number pe se random-ish.
  return {
    ok: true,
    result: {
      deviceId,
      number: `+91 ${deviceId === 'DEV-0001' ? '9811520001' : '9XXXXXXXXX'}`,
    },
  };
}
