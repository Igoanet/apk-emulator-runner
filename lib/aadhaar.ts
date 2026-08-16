// Aadhaar fetch engine — multi-step API flow (number → OTP1 → OTP2 → result).
//
// USER FLOW (confirmed):
//   1. API phone number maangta hai  → hum linked phone bhejte hain
//   2. API pehla OTP maangta hai     → hum OTP1 bhejte hain
//   3. API doosra OTP maangta hai    → hum OTP2 bhejte hain
//   4. API { text, photos[], pdf } return karta hai
//   5. Text + PDF Saved section (device Notes) me rakhte hain
//
// API NAHI MILI ABHI. Neeche teen functions hi wo *SEAM* hain — jab owner API
// dega, sirf inke andar real HTTP call bhar dena hai. Abhi demo/local mock hai.

export interface AadhaarPhoto {
  uri?: string;       // real API se aane wala photo url/file — mila to render hoga
  label: string;      // e.g. "Photo 1"
}

export interface AadhaarResult {
  text: string;       // Aadhaar details text (name, DOB, address, etc.)
  photos: AadhaarPhoto[];
  pdfName: string;    // PDF file ka naam — Notes me record hota hai
  pdfUri?: string;    // real PDF url/file — mila to save ho sakta hai
}

export interface AadhaarError {
  ok: false;
  error: string; // Hinglish, user ko dikhana hai
}

import { hasActiveApi } from './apiRegistry';

// ---- THE SEAM — ye teen functions API ke endpoints banenge ----

// Step 0: phone submit → demo me hamesha ok. Real me: POST /aadhaar/init {phone}
export async function aadhaarInit(phone: string): Promise<{ ok: true } | AadhaarError> {
  // Owner-managed registry — Aadhaar API remove hui to poora flow yahin band.
  if (!(await hasActiveApi('aadhaar'))) {
    return { ok: false, error: 'Aadhaar API abhi band hai — owner ne remove ki hai. Baad me try karo.' };
  }
  // TODO: owner ka API yahan (URL server-side registry me). Abhi demo.
  if (!/^\+?\d{10,13}$/.test(phone.replace(/[\s-]/g, ''))) {
    return { ok: false, error: 'Valid phone number daalo — 10 digit ya koi format.' };
  }
  return { ok: true };
}

// Step 1: OTP1 submit → demo me hamesha ok. Real me: POST /aadhaar/otp1 {phone, otp}
export async function aadhaarSubmitOtp1(_otp: string): Promise<{ ok: true } | AadhaarError> {
  // TODO: owner ka API. Abhi demo — koi bhi 6-digit chalega.
  return { ok: true };
}

// Step 2: OTP2 submit → demo me result return. Real me: POST /aadhaar/otp2 {phone, otp}
export async function aadhaarSubmitOtp2(_otp: string): Promise<
  { ok: true; result: AadhaarResult } | AadhaarError
> {
  // TODO: owner ka API — result uske response se aayega. Abhi demo.
  return {
    ok: true,
    result: {
      text:
        'Name: Ramesh Kumar Sharma\n' +
        'DOB: 15/08/1988\n' +
        'Gender: Male\n' +
        'Aadhaar (masked): 9876 •••• 1234\n' +
        'Address: 45, MG Road, Andheri East, Mumbai 400069',
      photos: [
        { label: 'Photo 1 — front' },
        { label: 'Photo 2 — signature' },
      ],
      pdfName: 'Aadhaar_RameshKumarSharma.pdf',
    },
  };
}
