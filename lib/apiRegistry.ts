// External API registry — owner Telegram bot ke Owner Panel → "API Management" se
// manage hoti hai (api-server pe data/external-apis.json). Public endpoint sirf
// ON kinds deta hai (URLs server-side rehte hain). FAIL-CLOSED: fetch fail ya
// cache stale (30s+) → feature band maano. Owner ne running API remove ki to
// max ~30s me panel app me wo feature band.

import { API_BASE } from './apiBase';

export type ExternalApiKind = 'get_number' | 'aadhaar';

const CACHE_MS = 30_000;
let cache: { at: number; kinds: ExternalApiKind[] } | null = null;

// kind ka feature ON hai? — registry me us kind ki API hai ya nahi.
export async function hasActiveApi(kind: ExternalApiKind): Promise<boolean> {
  const now = Date.now();
  if (cache && now - cache.at <= CACHE_MS) {
    return cache.kinds.includes(kind);
  }
  try {
    const r = await fetch(`${API_BASE}/api/external-apis`);
    if (!r.ok) throw new Error(`registry ${r.status}`);
    const data = (await r.json()) as { kinds?: ExternalApiKind[] };
    cache = { at: now, kinds: Array.isArray(data.kinds) ? data.kinds : [] };
    return cache.kinds.includes(kind);
  } catch {
    cache = null; // fail-closed — stale cache ko zinda nahi rakhte
    return false;
  }
}
