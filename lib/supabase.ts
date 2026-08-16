// Supabase client — panel ke live updates (Realtime) ke liye.
// Login (OTP verify) ke baad backend se mila session yahan set hota hai;
// RLS ensure karti hai ki user ko sirf usi ke events milein.

import { createClient, type SupabaseClient, type Session } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return null; // env missing — realtime band, app normal chalegi
  if (!client) {
    client = createClient(url, anonKey, {
      auth: {
        persistSession: false, // session backend se aata hai, local persist nahi karte
        autoRefreshToken: false,
      },
    });
  }
  return client;
}

// Backend (POST /api/panel/app/otp/verify) se mila Supabase session attach karo.
export async function applySupabaseSession(session: {
  access_token: string;
  refresh_token: string;
}): Promise<boolean> {
  const sb = getSupabase();
  if (!sb) return false;
  try {
    const { error } = await sb.auth.setSession({
      access_token: session.access_token,
      refresh_token: session.refresh_token,
    });
    return !error;
  } catch {
    return false;
  }
}

export type { Session };
