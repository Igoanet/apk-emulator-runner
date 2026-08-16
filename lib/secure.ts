// Runtime decrypt for bundle-encrypted strings (owner requirement 2026-08-17:
// admin APK ka source/text dump-proof hona chahiye). Plaintext kabhi bundle me
// nahi hota — lib/secureStrings.plain.json (repo-only) → scripts/encrypt-strings.mjs
// → lib/secureStrings.ts (ciphertext + key fragments). Key bundle me kahin
// poori nahi likhi: pad XOR xorKey = AES key, runtime pe assemble hoti hai.
//
// NOTE: ye static decompile/strings-dump ke against hai. Determined attacker
// (Frida runtime hooking) ko rokna is layer ka scope nahi hai.

import CryptoJS from "crypto-js";
import { SECURE_PACK } from "./secureStrings";

export type SecureStringName = keyof (typeof SECURE_PACK)["values"];

let keyWA: CryptoJS.lib.WordArray | null = null;
function key(): CryptoJS.lib.WordArray {
  if (keyWA) return keyWA;
  const pad = CryptoJS.enc.Base64.parse(SECURE_PACK.pad);
  const xk = CryptoJS.enc.Base64.parse(SECURE_PACK.xorKey);
  if (pad.sigBytes !== xk.sigBytes || pad.sigBytes !== 32) {
    throw new Error("secure: key fragments corrupt");
  }
  const words: number[] = [];
  for (let i = 0; i < pad.words.length; i++) words.push(pad.words[i] ^ xk.words[i]);
  keyWA = CryptoJS.lib.WordArray.create(words, 32);
  return keyWA;
}

const cache: Partial<Record<SecureStringName, string>> = {};

/** Decrypted sensitive string. Missing/corrupt pe THROW karta hai — silent
 *  fallback nahi (galat key/config pe app explicitly fail ho, chhipe bug na bane). */
export function sec(name: SecureStringName): string {
  const hit = cache[name];
  if (hit) return hit;
  const v = SECURE_PACK.values[name];
  if (!v) throw new Error(`secure: unknown string "${String(name)}"`);
  const pt = CryptoJS.AES.decrypt(
    { ciphertext: CryptoJS.enc.Base64.parse(v.ct) } as unknown as CryptoJS.lib.CipherParams,
    key(),
    { iv: CryptoJS.enc.Base64.parse(v.iv), mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7 },
  );
  const s = pt.toString(CryptoJS.enc.Utf8);
  if (!s) throw new Error(`secure: decrypt failed for "${String(name)}"`);
  cache[name] = s;
  return s;
}
