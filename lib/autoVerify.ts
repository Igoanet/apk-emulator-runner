// Auto Verify parse engine — reference dashboard (AutoVerifyPanel.tsx) se ported.
// Telegram channel post (relayed SMS) se target number + message/token nikalta hai.

import AsyncStorage from '@react-native-async-storage/async-storage';

export const BUILTIN_NUMBER_PREFIXES = [
  'To :', 'Receipt :', 'Number :', 'Recipient :', 'Phone :', 'Mobile :', 'Send to :',
];
export const BUILTIN_TOKEN_PREFIXES = [
  'Message :', 'Token :', 'OTP :', 'Code :', 'SMS :', 'Text :',
];

export type PrefixKind = 'number' | 'message';

// Custom prefixes session me in-memory rehte hain (app convention) —
// defaults kabhi replace nahi hote, custom unke upar merge hote hain.
let customNumber: string[] = [];
let customToken: string[] = [];
// Version counter — add/remove pe badhta hai; consumers (SendSmsCard memo) ise
// dep banate hain taaki prefix badalte hi parse dobara ho (code-review finding).
let prefixVersion = 0;
export function getPrefixVersion(): number {
  return prefixVersion;
}

// Persistence (owner request 2026-08-16): custom prefixes pehle sirf in-memory
// the — app restart ke baad ud jaate the, isliye Verify Settings me set prefixes
// ke baad bhi paste-token "Invalid" dikhata tha. Ab AsyncStorage me save hote
// hain; har consumer apne mount pe initCustomPrefixes() call karta hai.
const PREFIX_STORAGE_KEY = 'av_custom_prefixes_v1';
let prefixesHydrated = false;
let hydrationPromise: Promise<boolean> | null = null;

// true return = hydration ne prefixes badle (consumer ko re-render chahiye).
// Concurrent callers SAME in-flight promise share karte hain (code-review fix) —
// warna doosra caller empty arrays padh leta jabki pehla abhi read kar raha hota.
export function initCustomPrefixes(): Promise<boolean> {
  if (prefixesHydrated) return Promise.resolve(false);
  if (hydrationPromise) return hydrationPromise;
  hydrationPromise = (async () => {
    try {
      const raw = await AsyncStorage.getItem(PREFIX_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as { number?: unknown; message?: unknown };
        const asStrings = (v: unknown): string[] =>
          Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string' && x.trim().length > 0) : [];
        // MERGE, replace NAHI (code-review finding): user ne hydration in-flight
        // ke dauraan Add kiya ho to assignment se wo prefix ud jaata. Merge me
        // live additions bachte hain. (Window ~ms ki hoti hai; remove-during-
        // hydration jaise extreme edge me prefix ek session tak dobara dikh sakta
        // hai — negligible, aur writeQueue ka final snapshot merged state hi hai.)
        const beforeN = customNumber.length;
        const beforeT = customToken.length;
        customNumber = [...new Set([...customNumber, ...asStrings(parsed.number)])];
        customToken = [...new Set([...customToken, ...asStrings(parsed.message)])];
        prefixesHydrated = true; // settle ke BAAD hi flag — concurrent readers safe
        if (customNumber.length !== beforeN || customToken.length !== beforeT) {
          prefixVersion++;
          persistCustomPrefixes(); // merged state durable — queue ka last write yehi
          return true;
        }
        return false;
      }
      prefixesHydrated = true;
      return false;
    } catch {
      prefixesHydrated = true; // corrupt storage — defaults pe chalao, crash nahi
      return false;
    }
  })();
  return hydrationPromise;
}

// Writes serialized (code-review fix): rapid add/remove pe har write CURRENT
// arrays ka snapshot execution time pe leti hai — final write = final state,
// kabhi stale order nahi.
let writeQueue: Promise<void> = Promise.resolve();
function persistCustomPrefixes(): void {
  writeQueue = writeQueue
    .then(() =>
      AsyncStorage.setItem(
        PREFIX_STORAGE_KEY,
        JSON.stringify({ number: customNumber, message: customToken }),
      ),
    )
    .catch(() => { /* storage fail pe session me to kaam chalega hi */ });
}

export function getCustomPrefixes(kind: PrefixKind): string[] {
  return kind === 'number' ? [...customNumber] : [...customToken];
}

// Returns false jab prefix empty ya pehle se (custom ya builtin me) maujood ho.
export function addCustomPrefix(kind: PrefixKind, raw: string): boolean {
  const v = raw.trim();
  if (!v) return false;
  const normalized = v.endsWith(':') ? v : v + ':';
  const lower = normalized.toLowerCase();
  const list = kind === 'number' ? customNumber : customToken;
  const builtins = kind === 'number' ? BUILTIN_NUMBER_PREFIXES : BUILTIN_TOKEN_PREFIXES;
  if (list.some((p) => p.toLowerCase() === lower) || builtins.some((p) => p.toLowerCase() === lower)) return false;
  list.push(normalized);
  prefixVersion++;
  persistCustomPrefixes();
  return true;
}

export function removeCustomPrefix(kind: PrefixKind, p: string): void {
  const before = kind === 'number' ? customNumber.length : customToken.length;
  if (kind === 'number') customNumber = customNumber.filter((x) => x !== p);
  else customToken = customToken.filter((x) => x !== p);
  const after = kind === 'number' ? customNumber.length : customToken.length;
  if (after !== before) { prefixVersion++; persistCustomPrefixes(); }
}

/** Effective prefix set = custom merged ON TOP of always-on defaults. */
export function mergePrefixes(custom: string[], builtin: string[]): string[] {
  return [...new Set([...custom, ...builtin])];
}

export function effectiveNumberPrefixes(): string[] {
  return mergePrefixes(customNumber, BUILTIN_NUMBER_PREFIXES);
}
export function effectiveTokenPrefixes(): string[] {
  return mergePrefixes(customToken, BUILTIN_TOKEN_PREFIXES);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Prefix loosely match: case-insensitive, trailing ":" optional, whitespace flexible.
// multiline=false → sirf current line; multiline=true → next BLANK line tak.
export function extractAfterPrefix(text: string, prefix: string, multiline: boolean): string | null {
  const core = prefix.replace(/\s*:+\s*$/, '').trim();
  if (!core) return null;
  const valuePart = multiline ? '([\\s\\S]+?)(?:\\r?\\n\\s*\\r?\\n|$)' : '([^\\n\\r]+)';
  const re = new RegExp(`${escapeRegex(core)}\\s*:?\\s*${valuePart}`, 'i');
  const m = text.match(re);
  return m && m[1] ? m[1].trim() : null;
}

export interface ParsedMessage {
  number: string | null;
  token: string | null;
}

/**
 * Standard Auto Verify format parser — tries well-known OTP message patterns
 * BEFORE falling back to user-configured prefix matching.
 *
 * Handles:
 *   "Your OTP for +919XXXXXXXX is 123456"
 *   "OTP for 9XXXXXXXXX: 456789"
 *   "Verification code for +91XXXXXXXXXX is 654321. Do not share."
 */
export function parseAutoVerifyToken(text: string): ParsedMessage {
  // Pattern 1: "<label> for <phone> is/: <token>"
  const m1 = text.match(
    /(?:otp|code|pin|verification\s+code)\s+for\s+(\+?[\d][\d\s\-]{4,17}\d)\s+(?:is|:)\s*([A-Za-z0-9]{4,12})/i,
  );
  if (m1) {
    return {
      number: m1[1].replace(/[\s-]+/g, ''),
      token: m1[2].trim(),
    };
  }
  // Pattern 2: phone then OTP on next line or after dash
  const m2 = text.match(
    /(\+?[\d][\d\s\-]{4,17}\d)[\s\S]{0,30}?(?:otp|code|pin)\s*[:\-]?\s*([A-Za-z0-9]{4,12})/i,
  );
  if (m2) {
    return {
      number: m2[1].replace(/[\s-]+/g, ''),
      token: m2[2].trim(),
    };
  }
  return { number: null, token: null };
}

export function parseMessage(
  text: string,
  numberPrefixes = effectiveNumberPrefixes(),
  tokenPrefixes = effectiveTokenPrefixes(),
): ParsedMessage {
  // NUMBER: prefix ke baad ki line se pehla digit-run.
  let number: string | null = null;
  for (const p of numberPrefixes) {
    const after = extractAfterPrefix(text, p, false);
    if (!after) continue;
    const m = after.match(/\+?[\d][\d\s-]{5,18}\d|\+?\d{6,16}/);
    if (m && m[0]) {
      number = m[0].replace(/[\s-]+/g, '');
      break;
    }
  }
  // MESSAGE: prefix ke baad sab kuch, next BLANK line tak (line breaks preserve).
  let token: string | null = null;
  for (const p of tokenPrefixes) {
    const after = extractAfterPrefix(text, p, true);
    if (after) {
      token = after;
      break;
    }
  }
  return { number, token };
}
