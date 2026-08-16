import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Haptics from 'expo-haptics';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { PALETTE } from '@/constants/theme';
import { loadPanelToken, setPanelToken } from '@/lib/panelSession';
import { getDeviceId } from '@/lib/deviceId';
import { applySupabaseSession } from '@/lib/supabase';
import { DEV_PREVIEW } from '@/lib/devPreview';

// Premium Bomber reference (user ka screenshot) ka exact layout:
// purple ring logo → Igoan Panel → Powered by Igoan → Access Key card (green Activate)
// → Contact Support card → version pill. Front screen = security gate — koi settings/extra button nahi.
//
// Login rule (owner): NAYE device pe password ke baad Telegram OTP zaroori hai;
// verify hote hi device 7 DIN trusted — us window me saved session se seedha andar.
// Hafte baad session+trust dono expire → password + OTP dobara.
import { API_BASE } from '@/lib/apiBase';

// DEV PREVIEW BYPASS (owner request 2026-08-14): login/OTP gate SKIP — app seedha
// /main (devices screen) pe khulti hai taaki andar ke UI fixes jaldi ho saken.
// Normal login wapas chahiye to isko false karo — poora auth flow neeche INTACT hai.
// DEV PREVIEW BYPASS (owner request 2026-08-14/15): login/OTP gate SKIP — app seedha
// /main (devices screen) pe khulti hai. Centralized gate: lib/devPreview.ts ka
// DEV_PREVIEW — __DEV__ se gated, production APK me kabhi true nahi ho sakta.
// Normal login wapas chahiye to DEV_PREVIEW_ENABLED=false — poora auth flow INTACT hai.

// ── Remember password (owner request) ────────────────────────────────────────
// Checkbox ON + successful login → Admin ID + password AsyncStorage me save.
// Agli launch pe dono boxes auto-fill + checkbox ON rehta hai. Password badalne
// pe bhi — har successful login saved creds OVERWRITE karta hai, to naya
// password khud update ho jaata hai. Checkbox OFF karte hi saved creds delete.
const REMEMBER_KEY = 'panel_remembered_creds_v1';

async function loadRemembered(): Promise<{ adminId: string; password: string } | null> {
  try {
    const raw = await AsyncStorage.getItem(REMEMBER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { adminId?: unknown; password?: unknown };
    if (typeof parsed?.adminId === 'string' && typeof parsed?.password === 'string') {
      return { adminId: parsed.adminId, password: parsed.password };
    }
    return null;
  } catch {
    return null;
  }
}

async function saveRemembered(adminId: string, password: string): Promise<void> {
  try { await AsyncStorage.setItem(REMEMBER_KEY, JSON.stringify({ adminId, password })); } catch { /* storage fail pe login flow nahi todna */ }
}

async function clearRemembered(): Promise<void> {
  try { await AsyncStorage.removeItem(REMEMBER_KEY); } catch { /* ignore */ }
}

export default function LoginScreen() {
  const [adminId, setAdminId] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [otp, setOtp] = useState('');
  const [stage, setStage] = useState<'creds' | 'otp'>('creds');
  const [notice, setNotice] = useState('');
  const [resendsUsed, setResendsUsed] = useState(0); // owner rule: login OTP + 5 resend per chain, phir 60s cooldown
  const [resendWait, setResendWait] = useState(0); // owner rule: do sends ke beech min 30s — live countdown
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true); // saved-session auto-resume

  // App launch: saved session hai to seedha andar — lifetime access (trusted device).
  useEffect(() => {
    let alive = true;
    (async () => {
      // DEV bypass: pehle dev-login se REAL session lo (warna upload/slots APIs
      // 401 unauthorized dete hain), phir seedha devices screen. Dev-login fail
      // ho (server down/prod) to bhi andar bhejo — UI preview phir bhi chalega.
      if (DEV_PREVIEW) {
        try {
          const r = await fetch(`${API_BASE}/api/panel/app/dev-login`, { method: 'POST' });
          const data = await r.json().catch(() => ({}));
          if (r.ok && data.session?.token) {
            setPanelToken(data.session.token);
            if (data.supabaseSession) await applySupabaseSession(data.supabaseSession);
          }
        } catch { /* server unreachable — UI preview ke liye token zaroori nahi */ }
        router.replace('/main');
        return;
      }
      const token = await loadPanelToken();
      if (token) {
        try {
          // Token zinda hai? Server restart/expiry pe 401 aata hai.
          const r = await fetch(`${API_BASE}/api/panel/devices`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (r.ok) {
            router.replace('/bootstrap');
            return;
          }
          if (r.status === 401) setPanelToken(null); // expired — login dikhao
          // baaki (5xx/network) — token rehne do, agli launch pe phir try hoga
        } catch {
          // network fail — token mat saaf karo
        }
      }
      // Login form dikhne wala hai — remembered creds se boxes auto-fill karo.
      const remembered = await loadRemembered();
      if (remembered && alive) {
        setAdminId(remembered.adminId);
        setPassword(remembered.password);
        setRememberMe(true);
      }
      if (alive) setChecking(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Resend cooldown countdown — 1s tick (30s gap ya 60s lockout, dono isi se dikhte hain)
  useEffect(() => {
    if (resendWait <= 0) return;
    const t = setTimeout(() => setResendWait((s) => Math.max(0, s - 1)), 1000);
    return () => clearTimeout(t);
  }, [resendWait]);

  const finishLogin = async (data: { session?: { token?: string }; supabaseSession?: unknown }) => {
    // Realtime ke liye session PEHLE apply karo — warna main screen anon
    // subscribe kar degi aur RLS use reject kar degi (race).
    if (data.session?.token) setPanelToken(data.session.token); // scoped API calls ke liye (persist bhi hota hai)
    if (data.supabaseSession) await applySupabaseSession(data.supabaseSession as Parameters<typeof applySupabaseSession>[0]);
    // Remember password: har SUCCESSFUL login pe saved creds refresh (password
    // badla ho to naya save ho jaye); checkbox OFF hai to saved creds saaf.
    if (rememberMe) void saveRemembered(adminId.trim(), password);
    else void clearRemembered();
    router.replace('/bootstrap');
  };

  const toggleRemember = () => {
    const next = !rememberMe;
    setRememberMe(next);
    if (!next) void clearRemembered(); // uncheck = saved ID/password turant delete
  };

  const signIn = async () => {
    if (!adminId.trim() || !password || busy) return; // dono fields zaroori
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API_BASE}/api/panel/app/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adminId: adminId.trim(), password, deviceId: await getDeviceId() }),
      });
      const data = await r.json().catch(() => ({}));
      // Naya device — OTP Telegram pe gaya. OTP stage pe jao.
      if (r.ok && data.otpRequired) {
        setStage('otp');
        setOtp('');
        setNotice('');
        setResendsUsed(1); // pehla OTP login ne bheja — ab 5 resend bache
        setResendWait(30); // agla OTP min 30s baad hi (server bhi enforce karta hai)
        return;
      }
      if (!r.ok) {
        // Naya device — 24h security quarantine (owner rule): OTP abhi NAHI gaya,
        // 24 ghante baad wali request pe hi aayega. Creds screen pe hi raho.
        if (data.error === 'otp_wait') {
          const hrs = Math.max(1, Math.ceil((data.remainingMs ?? 0) / 3600000));
          setError(`Naya device hai — security ke liye OTP is device pe ~${hrs} ghante baad milega. Tab wapas sign in karna.`);
          return;
        }
        // 30s ke andar dobara login = OTP abhi-abhi bheja gaya tha (server ka resend
        // gate). Error dikhane ke bajaye seedha OTP screen pe le jao — warna user
        // baar-baar login karta hai aur pehla wala OTP "galat" lagta hai (supersede).
        if (data.error === 'cooldown' && typeof data.retryAfterSec === 'number' && data.retryAfterSec <= 30) {
          setStage('otp');
          setOtp('');
          setError('');
          setNotice('OTP abhi-abhi tumhare Telegram pe bheja gaya hai — check karo. Naya chahiye to timer ke baad Resend dabao.');
          setResendsUsed(1);
          setResendWait(Math.max(1, data.retryAfterSec));
          return;
        }
        setError(
          data.error === 'wrong_credentials'
            ? 'Galat Admin ID ya Password'
            : data.error === 'cooldown'
              ? `Thoda ruko — ${data.retryAfterSec ?? 60} second baad dobara try karo`
              : 'Login fail — thodi der baad dobara try karo',
        );
        return;
      }
      // Trusted device — bina OTP ke seedha session
      await finishLogin(data);
    } catch {
      setError('Panel unreachable — connection check karke dobara try karo');
    } finally {
      setBusy(false);
    }
  };

  // Resend (owner rule): chain me login OTP + max 5 resend; har send ke beech 30s
  // gap (server bhi enforce karta hai) — quota khatam pe 60s cooldown.
  const resendOtp = async () => {
    if (busy || resendWait > 0) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const r = await fetch(`${API_BASE}/api/panel/app/otp/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adminId: adminId.trim(), password, deviceId: await getDeviceId() }),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok) {
        setResendsUsed((n) => n + 1);
        setResendWait(30);
        setOtp('');
        setNotice('Naya OTP Telegram pe bheja gaya ✓');
        return;
      }
      if (data.error === 'otp_wait') {
        const hrs = Math.max(1, Math.ceil((data.remainingMs ?? 0) / 3600000));
        setError(`Naya device — OTP ~${hrs} ghante baad hi aayega (24h security wait).`);
        return;
      }
      if (data.error === 'cooldown') {
        const waitSec = typeof data.retryAfterSec === 'number' && data.retryAfterSec > 0 ? data.retryAfterSec : 60;
        setResendWait(waitSec); // server ke hisaab se countdown — 30s gap ya 60s lockout
        setError(
          waitSec <= 30
            ? `30 second ka gap hai — ${waitSec}s baad resend karo`
            : `5 resend ho gaye — ${waitSec} second ka cooldown, uske baad phir 5 milenge`,
        );
        return;
      }
      setError(
        data.error === 'wrong_credentials'
          ? 'Session expire ho gaya — wapas jakar dobara sign in karo'
          : 'OTP bhejna fail — thodi der baad try karo',
      );
    } catch {
      setError('Panel unreachable — connection check karo');
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async () => {
    if (!otp.trim() || busy) return;
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API_BASE}/api/panel/app/otp/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adminId: adminId.trim(), otp: otp.trim(), deviceId: await getDeviceId() }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(
          data.error === 'wrong_otp'
            ? 'Galat OTP — dobara try karo'
            : data.error === 'otp_expired'
              ? 'OTP expire ho gaya — wapas jakar dobara sign in karo (naya OTP aayega)'
              : data.error === 'too_many_attempts'
                ? 'Bahut baar galat OTP — thodi der baad try karo'
                : 'Verify fail — thodi der baad dobara try karo',
        );
        return;
      }
      // Sahi OTP — ye device ab lifetime trusted; session ~1 saal valid
      await finishLogin(data);
    } catch {
      setError('Panel unreachable — connection check karke dobara try karo');
    } finally {
      setBusy(false);
    }
  };

  if (checking) {
    return (
      <ScreenShell>
        <View style={styles.checkingWrap}>
          <Image source={require('@/assets/images/login_hacker12.png')} style={styles.logo} />
          <ActivityIndicator color={PALETTE.textMuted} style={{ marginTop: 18 }} />
        </View>
      </ScreenShell>
    );
  }

  return (
    <ScreenShell>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Flat hooded hacker icon — fully clean, tight crop (face bada) */}
        <Image source={require('@/assets/images/login_hacker12.png')} style={styles.logo} />
        <Text style={styles.title}>Igoan Panel</Text>

        {/* Access Key card */}
        <View style={styles.card}>
          <Text style={styles.accessTitle}>{stage === 'otp' ? 'OTP VERIFICATION' : 'ACCESS TERMINAL'}</Text>

          {stage === 'creds' ? (
            <>
              <Text style={styles.fieldLabel}>Admin ID</Text>
              <TextInput
                value={adminId}
                onChangeText={setAdminId}
                placeholder="Enter your admin ID"
                placeholderTextColor="#5f6b7a"
                style={styles.input}
                autoCapitalize="none"
                maxLength={64}
                testID="input-adminid"
              />
              <Text style={[styles.fieldLabel, { marginTop: 18 }]}>Password</Text>
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="Enter your password"
                placeholderTextColor="#5f6b7a"
                style={styles.input}
                secureTextEntry
                maxLength={128}
                testID="input-password"
              />
              {/* Remember password — ON = successful login pe creds save, agli launch pe auto-fill */}
              <Pressable onPress={toggleRemember} style={styles.rememberRow} hitSlop={6} testID="chk-remember">
                <View style={[styles.checkbox, rememberMe && styles.checkboxOn]}>
                  {rememberMe ? <Feather name="check" size={13} color="#ffffff" /> : null}
                </View>
                <Text style={styles.rememberText}>Remember password</Text>
              </Pressable>
              <Text style={styles.helper}>Enter your admin ID and password — naye device pe OTP Telegram pe aayega</Text>
              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              <Pressable onPress={signIn} disabled={busy} testID="btn-signin" style={({ pressed }) => [styles.activateBtn, (pressed || busy) && { opacity: 0.7 }]}>
                <Text style={styles.activateText}>{busy ? 'Checking…' : 'Activate'}</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text style={styles.fieldLabel}>Telegram OTP</Text>
              <TextInput
                value={otp}
                onChangeText={setOtp}
                placeholder="6-digit OTP"
                placeholderTextColor="#5f6b7a"
                style={styles.input}
                keyboardType="number-pad"
                maxLength={6}
                testID="input-otp"
              />
              <Text style={styles.helper}>
                OTP tumhare Telegram pe bheja gaya hai (IgoanPanel bot) — 5 min valid.{'\n'}
                Verify ke baad ye device 7 din trusted rahega.
              </Text>
              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              {notice ? <Text style={styles.noticeText}>{notice}</Text> : null}
              <Pressable onPress={verifyOtp} disabled={busy} testID="btn-verify-otp" style={({ pressed }) => [styles.activateBtn, (pressed || busy) && { opacity: 0.7 }]}>
                <Text style={styles.activateText}>{busy ? 'Verifying…' : 'Verify OTP'}</Text>
              </Pressable>
              <Pressable onPress={resendOtp} disabled={busy || resendWait > 0} testID="btn-resend-otp" style={({ pressed }) => [styles.resendBtn, (pressed || busy || resendWait > 0) && { opacity: 0.6 }]}>
                <Text style={styles.resendText}>
                  {resendWait > 0 ? `Resend ${resendWait}s baad available` : `OTP nahi aaya? Resend (${Math.max(0, 6 - resendsUsed)} left)`}
                </Text>
              </Pressable>
              {/* "Wapas" link REMOVED (owner rule 2026-08-13) — naya OTP ke liye yahi Resend hai */}
            </>
          )}
        </View>

        {/* Contact Support card — reference style (icon box + text + chevron + @Igoan row) */}
        <Pressable
          style={({ pressed }) => [styles.supportCard, pressed && { opacity: 0.85 }]}
          onPress={() => Linking.openURL('https://t.me/Igoan')}
          testID="btn-tutorial"
        >
          <View style={styles.supportRow}>
            <View style={styles.supportIconBox}>
              <Image source={require('@/assets/images/support_agent2.png')} style={styles.supportEmojiImg} />
            </View>
            <View style={styles.supportGap} />
            <View style={styles.supportTexts}>
              <Text style={styles.supportTitle}>Contact Support</Text>
              <Text style={styles.supportSub}>Don't have credential?{'\n'}Contact us here</Text>
            </View>
            <View style={styles.chevronBox}>
              <Feather name="chevron-right" size={14} color={PALETTE.textMuted} />
            </View>
          </View>
        </Pressable>

        <View style={{ flex: 1, minHeight: 24 }} />
        {/* Version — bahut chhota text, downside */}
        <Text style={styles.version}>Admin Panel V/1.0</Text>
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, alignItems: 'center', paddingHorizontal: 22, paddingTop: 56, paddingBottom: 18 },
  checkingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  logo: { width: 84, height: 84, borderRadius: 42, marginBottom: 16 },
  title: { color: PALETTE.text, fontSize: 28, fontFamily: 'JetBrainsMono_700Bold' },
  card: {
    width: '100%', backgroundColor: PALETTE.card, borderRadius: 18,
    borderWidth: 1, borderColor: PALETTE.border, padding: 22, marginTop: 40,
  },
  accessTitle: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold', letterSpacing: 3, textAlign: 'center', marginBottom: 16 },
  fieldLabel: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_600SemiBold', marginBottom: 8 },
  input: {
    backgroundColor: '#151e2b', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(82,169,255,0.14)',
    paddingHorizontal: 14, paddingVertical: 14, color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_400Regular',
  },
  helper: { color: '#7a8494', fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 10, lineHeight: 16 },
  rememberRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 14 },
  checkbox: {
    width: 20, height: 20, borderRadius: 6, borderWidth: 1.5,
    borderColor: 'rgba(139,92,246,0.55)', backgroundColor: '#151e2b',
    alignItems: 'center', justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: '#8b5cf6', borderColor: '#8b5cf6' }, // screenshot ka purple
  rememberText: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_400Regular' },
  errorText: { color: PALETTE.red, fontSize: 12, fontFamily: 'Inter_600SemiBold', marginTop: 10 },
  activateBtn: {
    backgroundColor: '#4ade80', borderRadius: 10, alignItems: 'center',
    justifyContent: 'center', paddingVertical: 14, marginTop: 22,
  },
  activateText: { color: '#ffffff', fontSize: 15, fontFamily: 'Inter_700Bold' },
  resendBtn: { alignItems: 'center', paddingVertical: 8, marginTop: 2 },
  resendText: { color: '#52a9ff', fontSize: 13, fontFamily: 'Inter_600SemiBold' },
  noticeText: { color: '#4ade80', fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 8, textAlign: 'center' },
  backBtn: { alignItems: 'center', paddingVertical: 12, marginTop: 6 },
  backText: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_600SemiBold' },

  supportCard: {
    width: '100%', backgroundColor: PALETTE.card, borderRadius: 18,
    borderWidth: 1, borderColor: PALETTE.border, padding: 16, marginTop: 40,
  },
  supportRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  supportGap: { width: 10 },
  supportIconBox: { width: 52, height: 52, borderRadius: 14, backgroundColor: '#2a3648', alignItems: 'center', justifyContent: 'center' },
  supportEmojiImg: { width: 42, height: 42 },
  supportTexts: { flex: 1 },
  supportTitle: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold' },
  supportSub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 3, lineHeight: 17 },
  chevronBox: { width: 24, height: 24, borderRadius: 7, backgroundColor: '#2a3648', alignItems: 'center', justifyContent: 'center' },
  version: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_400Regular', marginBottom: 4 },
});
