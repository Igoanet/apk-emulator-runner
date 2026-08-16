import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientHeader, useToast } from '@/components/panel/ui';
import { OtpConfirmDialog } from '@/components/panel/dialogs';
import { getActiveSlot, setActiveSlot, ActiveSlot } from '@/lib/activeSlot';
import { requestActionOtp } from '@/lib/devices';
import { ensureDevSession, panelAuthHeaders } from '@/lib/panelSession';
import { PALETTE } from '@/constants/theme';

import { API_BASE } from '@/lib/apiBase';

interface ApiSlot {
  id: string;
  label: string;
  projectId: string;
  databaseUrl: string;
  enabled: boolean;
  connections: number;
  capacity: number;
  isNew?: boolean;
}

export default function SwitchFirebaseScreen() {
  const [slots, setSlots] = useState<ApiSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(null);
  const [toast, showToast] = useToast();

  const load = async () => {
    const cur = await getActiveSlot();
    setActive(cur?.id ?? null);
    try {
      let r = await fetch(`${API_BASE}/api/panel/slots`, { headers: panelAuthHeaders() });
      // 401 pe PEHLE dev-session self-heal + ek retry (fetchMyDevices jaisa) —
      // seedha sign-in pe mat phenko jab tak session sach me recover na ho.
      if (r.status === 401) {
        await ensureDevSession(API_BASE);
        r = await fetch(`${API_BASE}/api/panel/slots`, { headers: panelAuthHeaders() });
      }
      // Tab bhi 401 (session sach me dead) — tabhi sign-in pe bhejo.
      if (r.status === 401) {
        showToast('Session expire ho gaya — dobara sign in karo');
        setTimeout(() => router.replace('/'), 500);
        return;
      }
      const data = await r.json();
      if (r.ok) setSlots((data.slots ?? []).filter((s: ApiSlot) => s.enabled !== false));
      else setSlots([]);
    } catch {
      // API down ho to bhi kuch dikhe — fallback nahi, sirf error toast
      setSlots([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const enter = async (slot: ApiSlot) => {
    const entry: ActiveSlot = { id: slot.id, label: slot.label, projectId: slot.projectId, databaseUrl: slot.databaseUrl };
    await setActiveSlot(entry);
    setActive(slot.id);
    showToast(`${slot.label} me enter — devices load ho rahi hain`);
    // Loading screen (bootstrap) se guzar ke main pe jao — seedha main pe nahi.
    setTimeout(() => router.replace('/bootstrap'), 260);
  };

  // Slot REMOVE (owner ask 2026-08-15) — destructive action, isliye pehle
  // Telegram action-OTP (SMS/device delete wala hi flow), phir server delete.
  const [delSlot, setDelSlot] = useState<ApiSlot | null>(null);
  const [delError, setDelError] = useState<string | null>(null);

  const askRemove = async (slot: ApiSlot) => {
    setDelError(null);
    const r = await requestActionOtp();
    if (r.status === 'cooldown') {
      showToast(`Thoda ruko — ${r.retryAfterSec ?? 60}s baad dobara try karo`);
      return;
    }
    if (r.status === 'fail') {
      showToast('OTP bhej nahi paya — internet check karke dobara try karo');
      return;
    }
    setDelSlot(slot); // OTP Telegram pe gaya — dialog kholo
  };

  const doRemove = async (slot: ApiSlot, otp: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/panel/slots/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ id: slot.id, otp }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const err = (data as { error?: string })?.error;
        // Galat/expired OTP pe dialog KHULA rakho — user dobara try kar sake
        if (err === 'wrong_otp' || err === 'too_many_attempts') {
          setDelError('Wrong OTP — Telegram wala 6-digit code daalo');
          return;
        }
        if (err === 'otp_expired' || err === 'otp_required') {
          setDelError('OTP expired — Cancel karke dobara delete dabao');
          return;
        }
        setDelSlot(null);
        showToast('Slot remove nahi hua — dobara try karo');
        return;
      }
      setSlots((prev) => prev.filter((s) => s.id !== slot.id));
      // Active slot hi remove hua to selection bhi clear karo
      if (active === slot.id) { await setActiveSlot(null); setActive(null); }
      setDelSlot(null);
      setDelError(null);
      showToast(`${slot.label} removed ✓`);
    } catch {
      setDelSlot(null);
      showToast('Slot remove nahi hua — internet/API check karo');
    }
  };

  return (
    <ScreenShell>
      <GradientHeader style={styles.header}>
        <Pressable hitSlop={10} onPress={() => router.back()} testID="switch-back" style={styles.backBtn}>
          <Feather name="arrow-left" size={20} color="#ffffff" />
        </Pressable>
        <View style={{ flex: 1, marginLeft: 8 }}>
          <Text style={styles.headerTitle}>Switch Firebase</Text>
          <Text style={styles.headerSub}>Kis Firebase me enter karna hai — chunu</Text>
        </View>
      </GradientHeader>

      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.limit}>{slots.length} / 10 Firebase available</Text>
        <Text style={styles.hint}>Neeche se ek choose karo. Usi slot ke devices load honge. Jo slot pehle selected hai wo ✓ se marked hai.</Text>

        {loading ? <Text style={styles.hint}>Slots load ho rahe hain…</Text> : null}
        {!loading && slots.length === 0 ? (
          <View style={styles.emptyBox}>
            <Feather name="inbox" size={22} color={PALETTE.textFaint} />
            <Text style={styles.emptyText}>Koi Firebase slot nahi mila — Settings → Upload google-services.json se pehle ek slot add karo.</Text>
          </View>
        ) : null}

        {slots.map((slot) => {
          const isActive = active === slot.id;
          return (
            <Pressable
              key={slot.id}
              style={[styles.slot, isActive && styles.slotActive]}
              onPress={() => enter(slot)}
              testID={`slot-${slot.id}`}
            >
              <View style={{ flex: 1 }}>
                <View style={styles.slotTop}>
                  <Text style={styles.slotName}>{slot.label}{slot.isNew ? '  · NEW' : ''}</Text>
                  {isActive ? (
                    <View style={styles.activeBadge}><Feather name="check" size={12} color="#0b1c2c" /></View>
                  ) : null}
                </View>
                <Text style={styles.project}>{slot.projectId}</Text>
                <Text style={styles.count}>{slot.connections} / {slot.capacity} connections</Text>
              </View>
              {/* Remove slot — Telegram OTP confirm ke baad server se delete */}
              <Pressable
                hitSlop={10}
                onPress={() => void askRemove(slot)}
                testID={`slot-del-${slot.id}`}
                style={styles.trashBtn}
              >
                <Feather name="trash-2" size={15} color="#ff6b6b" />
              </Pressable>
              <Feather name={isActive ? 'check-circle' : 'arrow-right-circle'} size={20} color={isActive ? PALETTE.greenBright : PALETTE.primaryBright} />
            </Pressable>
          );
        })}

        <Pressable style={styles.allBtn} onPress={async () => { await setActiveSlot(null); setActive(null); showToast('Sab slots — full list'); setTimeout(() => router.replace('/bootstrap'), 260); }} testID="switch-all">
          <Feather name="layers" size={16} color={PALETTE.primaryBright} />
          <Text style={styles.allText}>Enter all slots (full list)</Text>
        </Pressable>
      </ScrollView>
      <OtpConfirmDialog
        visible={delSlot !== null}
        onClose={() => { setDelSlot(null); setDelError(null); }}
        actionLabel="Remove"
        error={delError}
        onConfirm={(code) => { if (delSlot) void doRemove(delSlot, code); }}
        onResend={() => { if (delSlot) void askRemove(delSlot); }}
      />
      {toast}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#ffffff', fontSize: 20, fontFamily: 'Inter_700Bold' },
  headerSub: { color: '#bcd8f0', fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2 },
  body: { padding: 16, paddingBottom: 40 },
  limit: { color: PALETTE.amber, fontSize: 13, fontFamily: 'Inter_700Bold' },
  hint: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 8, lineHeight: 16 },
  slot: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: PALETTE.card, borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 14, padding: 14, marginTop: 10,
  },
  slotActive: { borderColor: PALETTE.greenBright, backgroundColor: '#0f2e1f' },
  slotTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  slotName: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  activeBadge: { width: 18, height: 18, borderRadius: 9, backgroundColor: PALETTE.greenBright, alignItems: 'center', justifyContent: 'center' },
  project: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },
  count: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 4 },
  trashBtn: { padding: 8, borderRadius: 10, backgroundColor: 'rgba(255,107,107,0.12)' },
  allBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 14, paddingVertical: 13, marginTop: 18,
  },
  allText: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold' },
  emptyBox: { alignItems: 'center', gap: 8, paddingVertical: 32, paddingHorizontal: 12 },
  emptyText: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', textAlign: 'center', lineHeight: 18 },
});
