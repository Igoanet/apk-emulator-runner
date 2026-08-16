// Shared API base URL.
// Dev server (Expo web): EXPO_PUBLIC_DOMAIN = Replit dev domain (proxied).
// Release APK: env var is empty at gradle time → fall back to Railway production.
export const API_BASE = process.env.EXPO_PUBLIC_DOMAIN
  ? `https://${process.env.EXPO_PUBLIC_DOMAIN}`
  : 'https://backend-production-1d65.up.railway.app';
