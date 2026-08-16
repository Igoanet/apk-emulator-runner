import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Image, Linking, Modal, Pressable,
  ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { usePanelTheme, useToast } from '@/components/panel/ui';
import { panelAuthHeaders } from '@/lib/panelSession';
import { getActiveSlot } from '@/lib/activeSlot';
import { DEV_PREVIEW } from '@/lib/devPreview';
import { PALETTE } from '@/constants/theme';
import { sec } from '@/lib/secure';

import { API_BASE } from '@/lib/apiBase';

// Hermes (APK) me AbortSignal.timeout support flaky hai — isliye manual
// AbortController + setTimeout. Bina iske har probe turant throw karta hai aur
// connection test millisecond me "fail" dikhata hai (koi fetch hota hi nahi).
async function fetchWithTimeout(url: string, ms: number, init?: RequestInit): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(t);
  }
}

// ── Drawer row ────────────────────────────────────────────────────
function DrawerRow({
  emoji, featherIcon, title, sub, onPress, testID, danger,
}: {
  emoji?: string; featherIcon?: React.ComponentProps<typeof Feather>['name'];
  title: string; sub?: string; onPress: () => void; testID?: string; danger?: boolean;
}) {
  return (
    <Pressable
      style={({ pressed }) => [styles.row, danger && styles.rowDanger, pressed && { opacity: 0.8 }]}
      onPress={onPress}
      testID={testID}
    >
      <View style={styles.rowIconWrap}>
        {featherIcon
          ? <Feather name={featherIcon} size={20} color={danger ? '#e57373' : '#94a3b8'} />
          : <Text style={styles.rowEmoji}>{emoji}</Text>}
      </View>
      <View style={{ flex: 1, marginLeft: 12 }}>
        <Text style={[styles.rowTitle, danger && styles.rowTitleDanger]}>{title}</Text>
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
    </Pressable>
  );
}

// ── Connection test types ─────────────────────────────────────────
interface TestRow {
  label: string;
  ok: boolean | null;   // null = pending
  detail: string;
}

export default function DrawerScreen() {
  usePanelTheme();
  const [toast, showToast] = useToast();

  const [slotCount, setSlotCount] = useState<number | null>(null);
  const [slotLabel, setSlotLabel] = useState('');
  const [expAt, setExpAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (DEV_PREVIEW) {
        if (!cancelled) {
          setSlotCount(2);
          setSlotLabel('Firebase 1');
          setExpAt(Date.now() + 60 * 24 * 60 * 60 * 1000);
        }
        return;
      }
      try {
        const headers = panelAuthHeaders();
        const [slotsRes, accessRes] = await Promise.all([
          fetch(`${API_BASE}/api/panel/slots`, { headers }),
          fetch(`${API_BASE}/api/panel/app/access`, { headers }),
        ]);
        const data = await slotsRes.json().catch(() => ({}));
        if (slotsRes.ok) {
          const slots = (Array.isArray(data.slots) ? data.slots : []) as { id: string }[];
          const active = await getActiveSlot();
          if (cancelled) return;
          setSlotCount(slots.length);
          const idx = active ? slots.findIndex((s) => s.id === active.id) : -1;
          setSlotLabel(slots.length === 0 ? '' : `Firebase ${idx >= 0 ? idx + 1 : 1}`);
        }
        if (accessRes.ok) {
          const acc = await accessRes.json().catch(() => ({})) as { expAt?: number };
          if (!cancelled && acc.expAt) setExpAt(acc.expAt);
        }
      } catch {
        // API down — fail-open
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const go = (route: '/broadcast' | '/settings' | '/switch') => {
    router.back();
    setTimeout(() => router.navigate(route), 60);
  };

  const goFirebase = () => {
    router.back();
    setTimeout(() => router.navigate('/firebase'), 60);
  };

  const logout = () => {
    try { router.dismissAll(); } catch {}
    router.replace('/' as const);
  };

  // ── Connection test modal ──────────────────────────────────────
  const [testVisible, setTestVisible] = useState(false);
  const [testRunning, setTestRunning] = useState(false);
  const [testResults, setTestResults] = useState<TestRow[]>([]);
  const testInFlight = useRef(false); // sync guard — openApiCheck ka auto-run + jaldi Re-run dabane se double-run race rukti hai

  const runConnectionTest = async () => {
    if (testInFlight.current) return; // ek run pehle se chal raha hai
    testInFlight.current = true;
    setTestRunning(true);
    setTestResults([
      { label: 'Panel API',       ok: null, detail: 'Checking…' },
      { label: 'Active Firebase', ok: null, detail: 'Checking…' },
      { label: 'Bot Channel',     ok: null, detail: 'Checking…' },
      { label: 'Aadhaar API',     ok: null, detail: 'Checking…' },
      { label: 'Get Number API',  ok: null, detail: 'Checking…' },
    ]);

    const results: TestRow[] = [];

    // 1. Panel API — ping /api/panel/app/access and measure latency.
    // Koi bhi HTTP response (404 bhi) = server reachable — sirf network fail pe red.
    try {
      const t0 = Date.now();
      const r = await fetchWithTimeout(`${API_BASE}/api/panel/app/access`, 8000, {
        headers: panelAuthHeaders(),
      });
      const ms = Date.now() - t0;
      results.push({
        label: 'Panel API',
        ok: r.status < 500,
        detail: r.ok ? `Connected — ${ms}ms` : `Reachable (HTTP ${r.status}) — ${ms}ms`,
      });
    } catch {
      results.push({ label: 'Panel API', ok: false, detail: 'Unreachable — check your connection' });
    }
    setTestResults([...results,
      { label: 'Active Firebase', ok: null, detail: 'Checking…' },
      { label: 'Bot Channel',     ok: null, detail: 'Checking…' },
    ]);

    // 2. Active Firebase — probe the RTDB .json endpoint (lightweight GET)
    try {
      const slot = DEV_PREVIEW ? null : await getActiveSlot();
      if (!slot?.databaseUrl) {
        results.push({ label: 'Active Firebase', ok: false, detail: 'No active slot configured' });
      } else {
        const t0 = Date.now();
        const r = await fetchWithTimeout(`${slot.databaseUrl.replace(/\/$/, '')}/.json?shallow=true`, 8000);
        const ms = Date.now() - t0;
        // RTDB returns 401 when rules block — that still means it's reachable
        const reachable = r.status < 500;
        results.push({
          label: 'Active Firebase',
          ok: reachable,
          detail: reachable ? `Reachable — ${ms}ms` : `RTDB error ${r.status} — ${ms}ms`,
        });
      }
    } catch {
      results.push({ label: 'Active Firebase', ok: false, detail: 'RTDB unreachable' });
    }
    setTestResults([...results,
      { label: 'Bot Channel',    ok: null, detail: 'Checking…' },
      { label: 'Aadhaar API',    ok: null, detail: 'Checking…' },
      { label: 'Get Number API', ok: null, detail: 'Checking…' },
    ]);

    // 3. Bot / slot-agent status
    try {
      const t0 = Date.now();
      const r = await fetchWithTimeout(`${API_BASE}/api/panel/sa/status`, 8000, {
        headers: panelAuthHeaders(),
      });
      const ms = Date.now() - t0;
      if (r.ok) {
        const body = await r.json().catch(() => ({})) as Record<string, unknown>;
        const status = typeof body.status === 'string' ? body.status : 'ok';
        results.push({ label: 'Bot Channel', ok: true, detail: `${status} — ${ms}ms` });
      } else {
        results.push({ label: 'Bot Channel', ok: false, detail: `HTTP ${r.status} — ${ms}ms` });
      }
    } catch {
      results.push({ label: 'Bot Channel', ok: false, detail: 'Bot channel unreachable' });
    }
    setTestResults([...results,
      { label: 'Aadhaar API',    ok: null, detail: 'Checking…' },
      { label: 'Get Number API', ok: null, detail: 'Checking…' },
    ]);

    // 4 & 5. External APIs — server pings the actual URLs, only status returns
    try {
      const r = await fetchWithTimeout(`${API_BASE}/api/panel/external-apis/status`, 12000, {
        headers: panelAuthHeaders(),
      });
      if (r.ok) {
        const body = await r.json().catch(() => ({})) as Record<string, { configured: boolean; ok: boolean; ms: number }>;
        const fmt = (kind: string, label: string) => {
          const s = body[kind];
          if (!s) { results.push({ label, ok: false, detail: 'No data' }); return; }
          if (!s.configured) { results.push({ label, ok: false, detail: 'Not configured' }); return; }
          results.push({ label, ok: s.ok, detail: s.ok ? `Reachable — ${s.ms}ms` : `Unreachable — ${s.ms}ms` });
        };
        fmt('aadhaar',    'Aadhaar API');
        fmt('get_number', 'Get Number API');
      } else {
        results.push({ label: 'Aadhaar API',    ok: false, detail: `Server error ${r.status}` });
        results.push({ label: 'Get Number API', ok: false, detail: `Server error ${r.status}` });
      }
    } catch {
      results.push({ label: 'Aadhaar API',    ok: false, detail: 'Could not reach panel API' });
      results.push({ label: 'Get Number API', ok: false, detail: 'Could not reach panel API' });
    }

    setTestResults(results);
    setTestRunning(false);
    testInFlight.current = false;
  };

  const openApiCheck = () => {
    setTestVisible(true);
    setTestResults([]);
    // auto-run on open
    setTimeout(() => void runConnectionTest(), 80);
  };

  return (
    <View style={styles.overlay}>
      <View style={styles.panel}>
        <ScrollView contentContainerStyle={{ flexGrow: 1 }} style={{ backgroundColor: PALETTE.bg }} showsVerticalScrollIndicator={false}>
          <View style={styles.header}>
            <View style={styles.brandRow}>
              <Image source={require('@/assets/images/login_hacker12.png')} style={styles.brandIcon} />
              <View>
                <Text style={styles.brand}>Igoan Panel</Text>
                <Text style={styles.brandSub}>Admin menu</Text>
                {expAt ? (
                  <Text style={[styles.brandSub, {
                    marginTop: 3,
                    color: expAt < Date.now() ? '#e57373' : expAt - Date.now() < 7 * 24 * 3600 * 1000 ? '#ffb74d' : '#4caf89',
                    fontSize: 10,
                  }]}>
                    {expAt < Date.now()
                      ? '⚠ Access expired'
                      : `Expires: ${new Date(expAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`}
                  </Text>
                ) : null}
              </View>
            </View>
            <View style={styles.adminChip}>
              <Text style={styles.adminChipText}>{slotLabel}</Text>
            </View>
          </View>

          <View style={styles.menu}>
            <DrawerRow
              featherIcon="repeat"
              title="Switch Firebase"
              sub="Kis slot me enter karna hai chunu"
              onPress={() => {
                if (slotCount !== null && slotCount <= 1) {
                  showToast('No other Firebase added — pehle Add Firebase se naya slot jodo');
                  return;
                }
                go('/switch');
              }}
              testID="drawer-switch-firebase"
            />
            <DrawerRow emoji="🔥" title="Firebase" sub="Slots manage karo, naya add karo" onPress={goFirebase} testID="drawer-add-firebase" />
            <DrawerRow emoji="📬" title="Broadcast" sub="Announcements" onPress={() => go('/broadcast')} testID="drawer-broadcast" />
            <DrawerRow emoji="🔔" title="Notification" sub="Telegram Chat ID set karo" onPress={() => go('/notification')} testID="drawer-notification" />
            <DrawerRow emoji="✅" title="Auto Verify" sub="OTP auto-detect settings" onPress={() => go('/autoverify')} testID="drawer-autoverify" />
            <DrawerRow emoji="🎛️" title="Verify Settings" sub="Number + message prefixes" onPress={() => go('/verify-settings')} testID="drawer-verify-settings" />
            <DrawerRow
              emoji="🎧"
              title="Contact Support"
              sub="Help & feedback"
              onPress={() => Linking.openURL(sec('telegramChannel')).catch(() => showToast('Could not open Telegram'))}
              testID="drawer-support"
            />
            <DrawerRow
              emoji="📡"
              title="API Check"
              sub="Ping server & see connection status"
              onPress={openApiCheck}
              testID="drawer-api-check"
            />
            <DrawerRow emoji="⚙️" title="Settings" sub="2FA, slots, sessions" onPress={() => go('/settings')} testID="drawer-settings" />

            <View style={styles.divider} />

            <DrawerRow emoji="🚪" title="Logout" danger onPress={logout} testID="drawer-logout" />
          </View>
        </ScrollView>
        {toast}
      </View>

      {/* Backdrop */}
      <Pressable style={styles.backdrop} onPress={() => router.back()} testID="drawer-backdrop" />

      {/* ── Connection Test Modal ──────────────────────────────── */}
      <Modal
        visible={testVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setTestVisible(false)}
      >
        <Pressable style={styles.modalOverlay} onPress={() => { if (!testRunning) setTestVisible(false); }}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            {/* Header */}
            <View style={styles.modalHeader}>
              <Feather name="activity" size={18} color={PALETTE.teal} style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Connection Test</Text>
              {testRunning && <ActivityIndicator size="small" color={PALETTE.teal} style={{ marginLeft: 8 }} />}
            </View>

            {/* Rows */}
            <View style={styles.modalBody}>
              {testResults.length === 0
                ? <Text style={styles.testDetail}>Starting…</Text>
                : testResults.map((row, i) => (
                  <View key={i} style={[styles.testRow, i === testResults.length - 1 && { borderBottomWidth: 0 }]}>
                    <View style={[
                      styles.testDot,
                      row.ok === null && { backgroundColor: '#555' },
                      row.ok === true  && { backgroundColor: '#4caf89' },
                      row.ok === false && { backgroundColor: '#e57373' },
                    ]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.testLabel}>{row.label}</Text>
                      <Text style={styles.testDetail}>{row.detail}</Text>
                    </View>
                  </View>
                ))
              }
            </View>

            {/* Footer buttons */}
            <View style={styles.modalFooter}>
              <Pressable
                style={({ pressed }) => [styles.modalBtn, styles.modalBtnSecondary, (pressed || testRunning) && { opacity: 0.75 }]}
                onPress={() => { if (!testRunning) void runConnectionTest(); }}
                disabled={testRunning}
              >
                {testRunning
                  ? <ActivityIndicator size="small" color={PALETTE.teal} />
                  : <Text style={styles.modalBtnTextSecondary}>Re-run</Text>}
              </Pressable>
              <Pressable
                style={({ pressed }) => [styles.modalBtn, styles.modalBtnPrimary, pressed && { opacity: 0.75 }]}
                onPress={() => setTestVisible(false)}
              >
                <Text style={styles.modalBtnText}>Close</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, flexDirection: 'row', backgroundColor: 'transparent' },
  panel: { width: '78%', height: '100%', backgroundColor: PALETTE.bg },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  header: { backgroundColor: PALETTE.cardAlt, paddingTop: 40, paddingBottom: 22, paddingHorizontal: 22 },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  brandIcon: { width: 40, height: 40, borderRadius: 20 },
  brand: { color: PALETTE.text, fontSize: 24, fontFamily: 'JetBrainsMono_700Bold' },
  brandSub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 4 },
  adminChip: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg, padding: 10, marginTop: 10, borderRadius: 8 },
  adminChipText: { color: PALETTE.teal, fontSize: 13, fontFamily: 'Inter_700Bold' },
  menu: { padding: 16 },
  row: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: PALETTE.card, borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 12, padding: 14, marginVertical: 7,
  },
  rowDanger: { backgroundColor: '#241917', borderColor: '#241917' },
  rowIconWrap: { width: 36, alignItems: 'center', justifyContent: 'center' },
  rowEmoji: { fontSize: 22, width: 36, textAlign: 'center' },
  rowTitle: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  rowTitleDanger: { color: PALETTE.redSoft },
  rowSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular' },
  divider: { height: 1, backgroundColor: PALETTE.borderSoft, marginVertical: 14 },

  // ── Connection Test Modal ──────────────────────────────────────
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.72)',
    justifyContent: 'center', alignItems: 'center', padding: 24,
  },
  modalCard: {
    width: '100%', backgroundColor: PALETTE.card,
    borderRadius: 16, borderWidth: 1, borderColor: PALETTE.borderSoft,
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center',
    padding: 18, borderBottomWidth: 1, borderBottomColor: PALETTE.borderSoft,
  },
  modalTitle: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold', flex: 1 },
  modalBody: { padding: 18, gap: 0 },
  testRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: PALETTE.borderSoft,
  },
  testDot: { width: 12, height: 12, borderRadius: 6, marginTop: 3, backgroundColor: '#555' },
  testLabel: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },
  testDetail: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2 },
  modalFooter: {
    flexDirection: 'row', justifyContent: 'flex-end', gap: 10,
    padding: 14, borderTopWidth: 1, borderTopColor: PALETTE.borderSoft,
  },
  modalBtn: { paddingVertical: 9, paddingHorizontal: 20, borderRadius: 10 },
  modalBtnPrimary: { backgroundColor: PALETTE.teal },
  modalBtnSecondary: { backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft },
  modalBtnText: { color: '#000', fontFamily: 'Inter_700Bold', fontSize: 14 },
  modalBtnTextSecondary: { color: PALETTE.text, fontFamily: 'Inter_700Bold', fontSize: 14 },
});
