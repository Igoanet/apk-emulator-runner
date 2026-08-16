#!/usr/bin/env node
// lib/secureStrings.plain.json → lib/secureStrings.ts (AES-256-CBC encrypted).
//
// Key model (owner requirement: APK dump se text na mile):
//   K = 32-byte random AES key, P = 32-byte random pad. Bundle me K kahin
//   nahi hota — sirf P aur (K XOR P) alag-alag fields me. Runtime dono ko
//   XOR karke key banata hai. `strings`/jadx dump se plaintext/na key milti.
//   (Ye obfuscation hai, Frida-level runtime hooking ka ilaaj nahi — par
//   static decompile-read poori tarah band.)
//
// Chalana: node scripts/encrypt-strings.mjs   (igoan-panel dir se)
import { createRequire } from "node:module";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const require = createRequire(import.meta.url);
const CryptoJS = require("crypto-js");

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const plainPath = path.join(root, "lib", "secureStrings.plain.json");
const outPath = path.join(root, "lib", "secureStrings.ts");

const raw = JSON.parse(fs.readFileSync(plainPath, "utf8"));
const entries = Object.entries(raw).filter(([k, v]) => !k.startsWith("//") && typeof v === "string" && v.length > 0);
if (entries.length === 0) {
  console.error("plain file me koi string nahi mili — abort (kuchh overwrite nahi hua)");
  process.exit(1);
}

const K = crypto.randomBytes(32);
const P = crypto.randomBytes(32);
const X = Buffer.alloc(32);
for (let i = 0; i < 32; i++) X[i] = K[i] ^ P[i];

const keyWA = CryptoJS.enc.Base64.parse(K.toString("base64"));
const values = {};
for (const [name, plain] of entries) {
  const iv = crypto.randomBytes(16);
  const enc = CryptoJS.AES.encrypt(plain, keyWA, {
    iv: CryptoJS.enc.Base64.parse(iv.toString("base64")),
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7,
  });
  values[name] = { iv: iv.toString("base64"), ct: enc.ciphertext.toString(CryptoJS.enc.Base64) };
}

const ts = `// GENERATED FILE — scripts/encrypt-strings.mjs se bana, haath se edit MAT karo.
// Sirf ciphertext + obfuscated key fragments hain; plaintext ke liye
// lib/secureStrings.plain.json dekho (repo-only, APK me nahi jati).
export const SECURE_PACK = ${JSON.stringify({ pad: P.toString("base64"), xorKey: X.toString("base64"), values }, null, 2)} as const;
`;
fs.writeFileSync(outPath, ts);
console.log(`OK — ${entries.length} strings encrypted → ${path.relative(root, outPath)} (${entries.map(([k]) => k).join(", ")})`);
