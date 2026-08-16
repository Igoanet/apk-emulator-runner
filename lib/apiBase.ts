// Shared API base URL.
// Dev server (Expo web): EXPO_PUBLIC_DOMAIN = Replit dev domain (proxied).
// Release APK: env var is empty at gradle time → encrypted prod URL
// (sec()) se aati hai — bundle me plaintext Railway URL nahi dikhti
// (owner hardening requirement 2026-08-17).
import { sec } from "./secure";

export const API_BASE = process.env.EXPO_PUBLIC_DOMAIN
  ? `https://${process.env.EXPO_PUBLIC_DOMAIN}`
  : sec("apiBaseProd");
