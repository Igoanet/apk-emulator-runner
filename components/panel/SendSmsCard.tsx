import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { GradientCard } from '@/components/panel/ui';
import { AutoVerifyDialog } from '@/components/panel/dialogs';
import { AutoVerifyModal } from '@/components/panel/AutoVerifyModal';
import { parseMessage, getPrefixVersion, initCustomPrefixes } from '@/lib/autoVerify';
import { PALETTE } from '@/constants/theme';

type Sim = 1 | 2;
type Mode = 'manual' | 'token';

// TOKEN mode ka extraction — Verify Settings (AutoVerifyDialog) ke prefix logic se
// (owner rule 2026-08-15): user editable FORMAT field HATA diya; number "To :/Number :"
// jaisi prefixes se aur body "Message :/Token :" prefixes se nikalti hai — custom
// prefixes (Verify Settings me add kiye hue) bhi yahi se kaam karte hain.

// Reference APK ka SEND SMS frame — SIM slot select, MANUAL/TOKEN mode,
// To+Message ya Paste Token, aur neeche SEND SMS button. Sab ek frame ke andar.
export function SendSmsCard({
  sim1Name, sim2Name, deviceId, onSent, onError, bare,
}: {
  sim1Name: string; sim2Name: string; deviceId: string;
  onSent: (sim: Sim, to: string, body: string) => void;
  onError: (msg: string) => void;
  // bare = true → outer card frame + duplicate "SEND SMS" header nahi (bottom-sheet ke andar)
  bare?: boolean;
}) {
  const [sim, setSim] = useState<Sim>(1);
  const [mode, setMode] = useState<Mode>('manual');
  const [to, setTo] = useState('');
  const [message, setMessage] = useState('');
  const [token, setToken] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [avOpen, setAvOpen] = useState(false);
  // AUTO toggle (owner rule 2026-08-15): ON ho to sirf paste karna hai — dono
  // section bhar gaye (manual: to+message / token: valid parse) to khud SEND
  // ho jaata hai, SEND SMS dabane ki zaroorat nahi. OFF ho to manual button.
  // Owner rule 2026-08-16: default ON; user OFF kar sakta hai, lekin sheet band
  // karke dobara kholne pe wapas ON (details.tsx me key-remount se reset hota hai
  // — state persist/persist-storage dono nahi, sirf fresh mount).
  const [auto, setAuto] = useState(true);
  // Custom prefixes ab AsyncStorage pe persist hote hain — mount pe hydrate karo;
  // hydration ne prefixes badle to tick se re-render → parse dobara (warna restart
  // ke baad pasted token pe purana "Invalid" atka rehta).
  const [, setPrefixTick] = useState(0);
  const [prefixReady, setPrefixReady] = useState(false);
  useEffect(() => {
    let alive = true;
    void initCustomPrefixes().then((changed) => {
      if (!alive) return;
      setPrefixReady(true);
      if (changed) setPrefixTick((t) => t + 1);
    });
    return () => { alive = false; };
  }, []);
  // Duplicate-send latch (code-review fix): ek baar send consume ho gaya to
  // dobara send SIRF naye deliberate input (typing ya paste) pe hi re-arm
  // hota hai — render commit ka wait nahi karna padta. pastingRef alag se
  // overlapping clipboard reads rokta hai (rapid double-tap pe 2 paste
  // continuations nahi chalte).
  const consumedRef = useRef(false);
  const pastingRef = useRef(false);
  const fireSend = (s: Sim, num: string, body: string) => {
    if (consumedRef.current) return;
    consumedRef.current = true;
    onSent(s, num, body);
  };

  // Combo parse — Verify Settings ke effective prefixes se number + body nikalo.
  // prefixVersion dep: Verify Settings dialog band hote hi (re-render) naye custom
  // prefixes ke saath dobara parse ho — warna purana memo atka rehta tha.
  const prefixVersion = getPrefixVersion();
  const parsed = useMemo(() => {
    if (!token.trim()) return null;
    const p = parseMessage(token);
    if (!p.number || !p.token) return null;
    return { num: p.number, body: p.token };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, prefixVersion]);

  // TOKEN live preview (owner rule 2026-08-15 — wapas laya gaya): paste karte hi
  // niche dikhe ki number/body kya nikla; galat prefix pe invalid hint.
  const previewText = useMemo(() => {
    if (!token.trim()) return 'Preview will appear here';
    if (!parsed) return 'Invalid — "To :"/"Message :" jaisa prefix nahi mila (Verify Settings se custom add karo)';
    return `→ ${parsed.num} via SIM ${sim}: "${parsed.body}"`;
  }, [token, parsed, sim]);

  const canSend = mode === 'manual'
    ? to.trim().length > 0 && message.trim().length > 0
    : !!parsed;

  // AUTO send (owner rule): auto ON + paste ke baad dono section bhare hue →
  // seedha onSent (success/error message parent wahi dikhata hai jo manual
  // SEND pe dikhata hai). send() se alag rakha kyunki state async update hota
  // hai — yahan pasted text SEEDHA pass karte hain, stale state ka wait nahi.
  const maybeAutoSend = (nextTo: string, nextMsg: string, nextToken: string) => {
    if (!auto) return;
    if (mode === 'manual') {
      if (nextTo.trim() && nextMsg.trim()) {
        setMessage('');
        fireSend(sim, nextTo.trim(), nextMsg.trim());
      }
    } else {
      const p = parseMessage(nextToken);
      if (p.number && p.token) {
        setToken('');
        fireSend(sim, p.number, p.token);
      }
    }
  };

  // Hydration race retry (code-review finding): restart ke TURANT baad paste +
  // AUTO ON karne pe custom prefixes abhi load nahi hote → parse miss → send
  // chhoot jaata. prefixReady flip pe pending input dobara evaluate karo.
  useEffect(() => {
    if (prefixReady && auto) maybeAutoSend(to, message, token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefixReady]);

  // Unmount guard (code-review fix): sheet close pe key-remount se card UNMOUNT
  // hota hai — pending clipboard read ka continuation state update ya auto-send
  // NAHI kare (warna band sheet ke baad bhi SMS bhej sakta tha).
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Clipboard read helper — pastingRef se overlapping reads block; successful
  // paste = naya input lifecycle, isliye consumed latch re-arm.
  const readClipboard = async (): Promise<string | null> => {
    if (pastingRef.current) return null;
    pastingRef.current = true;
    try {
      const text = await Clipboard.getStringAsync();
      if (!mountedRef.current) return null; // sheet band/remount — continuation drop
      if (text.trim()) return text;
      onError('Clipboard khali hai');
      return null;
    } catch {
      if (mountedRef.current) onError('Clipboard access nahi mila');
      return null;
    } finally {
      pastingRef.current = false;
    }
  };

  // TO field ka paste (owner request) — clipboard ka number seedha To me.
  const pasteTo = async () => {
    const text = await readClipboard();
    if (!text) return;
    consumedRef.current = false;
    setTo(text.trim());
    maybeAutoSend(text, message, token);
  };

  // MESSAGE box ka paste — chhota icon sirf box ke BOTTOM-RIGHT corner me.
  const pasteMessage = async () => {
    const text = await readClipboard();
    if (!text) return;
    consumedRef.current = false;
    setMessage(text);
    maybeAutoSend(to, text, token);
  };

  // TOKEN box ka paste — FULL ROW button, SEND SMS ke theek upar.
  const pasteToken = async () => {
    const text = await readClipboard();
    if (!text) return;
    consumedRef.current = false;
    setToken(text);
    maybeAutoSend(to, message, text);
  };

  // AUTO toggle — proper switch button (track + sliding thumb), TO / PASTE
  // TOKEN label ke right side pe. ON = primary track, thumb right.
  const autoToggle = (
    <Pressable
      hitSlop={8}
      onPress={() => setAuto((a) => !a)}
      style={styles.autoRow}
      testID="send-auto-toggle"
    >
      <Feather name="zap" size={10} color={auto ? PALETTE.primaryBright : PALETTE.textMuted} />
      <Text style={[styles.autoText, auto && styles.autoTextOn]}>AUTO</Text>
      <View style={[styles.autoTrack, auto && styles.autoTrackOn]}>
        <View style={[styles.autoThumb, auto && styles.autoThumbOn]} />
      </View>
    </Pressable>
  );

  const send = () => {
    if (!canSend) return;
    setMessage('');
    setToken('');
    if (mode === 'manual') fireSend(sim, to.trim(), message.trim());
    else if (parsed) fireSend(sim, parsed.num, parsed.body);
  };

  const content = (
    <>
      {/* bare mode (sheet ke andar) — sirf tools row, duplicate SEND SMS header nahi */}
      {bare ? (
        <View style={styles.headRow}>
          <View style={{ flex: 1 }} />
          <Pressable hitSlop={8} onPress={() => setSettingsOpen(true)} style={styles.headBtn} testID="av-settings">
            <Feather name="settings" size={11} color={PALETTE.primaryBright} />
            <Text style={styles.headBtnText}>Verify Settings</Text>
          </Pressable>
          <Pressable hitSlop={8} onPress={() => setAvOpen(true)} style={styles.headBtn} testID="auto-verify-toggle">
            <Feather name="zap" size={11} color={PALETTE.primaryBright} />
            <Text style={styles.headBtnText}>Auto Verify</Text>
          </Pressable>
        </View>
      ) : (
        <View style={styles.headRow}>
          <Feather name="send" size={13} color={PALETTE.primaryBright} />
          <Text style={styles.headTitle}>SEND SMS</Text>
          <View style={{ flex: 1 }} />
          <Pressable hitSlop={8} onPress={() => setSettingsOpen(true)} style={styles.headBtn} testID="av-settings">
            <Feather name="settings" size={11} color={PALETTE.primaryBright} />
            <Text style={styles.headBtnText}>Verify Settings</Text>
          </Pressable>
          <Pressable hitSlop={8} onPress={() => setAvOpen(true)} style={styles.headBtn} testID="auto-verify-toggle">
            <Feather name="zap" size={11} color={PALETTE.primaryBright} />
            <Text style={styles.headBtnText}>Auto Verify</Text>
          </Pressable>
        </View>
      )}

      {/* SIM SLOT segmented */}
      <Text style={styles.label}>SIM SLOT</Text>
      <View style={styles.seg}>
        {([1, 2] as Sim[]).map((n) => {
          const name = n === 1 ? sim1Name : sim2Name;
          const active = sim === n;
          return (
            <Pressable
              key={n}
              style={[styles.segCell, active && styles.segCellOn]}
              onPress={() => setSim(n)}
              testID={`send-sim-${n}`}
            >
              <Text style={[styles.segTitle, active && styles.segTitleOn]}>{`SIM ${n}`}</Text>
              <Text style={[styles.segSub, active && styles.segSubOn]} numberOfLines={1}>{name}</Text>
            </Pressable>
          );
        })}
      </View>

      {/* SEND MODE segmented */}
      <Text style={styles.label}>SEND MODE</Text>
      <View style={styles.seg}>
        {(['manual', 'token'] as Mode[]).map((m) => {
          const active = mode === m;
          return (
            <Pressable
              key={m}
              style={[styles.segCell, active && styles.segCellOn]}
              onPress={() => setMode(m)}
              testID={`send-mode-${m}`}
            >
              <Text style={[styles.segTitle, active && styles.segTitleOn]}>{m.toUpperCase()}</Text>
            </Pressable>
          );
        })}
      </View>

      {mode === 'manual' ? (
        <>
          {/* TO label + right side pe AUTO toggle (owner request) */}
          <View style={styles.labelRow}>
            <Text style={[styles.label, styles.labelFlush]}>TO</Text>
            {autoToggle}
          </View>
          {/* TO board poori row occupy karta hai; paste button usi ke ANDAR right
              side pe (owner request) — aur sirf tab dikhta hai jab box khali hai */}
          <View>
            <TextInput
              value={to}
              onChangeText={(t) => { consumedRef.current = false; setTo(t); }}
              placeholder="+919876543210"
              placeholderTextColor={PALETTE.textDim}
              keyboardType="phone-pad"
              style={[styles.input, !to.trim() && { paddingRight: 46 }]}
              testID="send-to"
            />
            {!to.trim() && (
              <Pressable hitSlop={8} onPress={pasteTo} style={styles.innerPaste} testID="send-to-paste">
                <Feather name="clipboard" size={17} color={PALETTE.primaryBright} />
              </Pressable>
            )}
          </View>
          <Text style={styles.label}>MESSAGE</Text>
          {/* MESSAGE paste UI revert (owner request — purana wala pasand hai):
              chhota icon sirf box ke BOTTOM-RIGHT corner me; khali box pe hi dikhta hai */}
          <View>
            <TextInput
              value={message}
              onChangeText={(t) => { consumedRef.current = false; setMessage(t); }}
              placeholder="Type your message…"
              placeholderTextColor={PALETTE.textDim}
              style={[styles.input, styles.multiline, !message.trim() && { paddingRight: 40 }]}
              multiline
              testID="send-message"
            />
            {!message.trim() && (
              <Pressable hitSlop={8} onPress={pasteMessage} style={styles.cornerPaste} testID="send-message-paste">
                <Feather name="clipboard" size={14} color={PALETTE.primaryBright} />
              </Pressable>
            )}
          </View>
        </>
      ) : (
        <>
          {/* TOKEN mode — paste box + LIVE PREVIEW (wapas, owner rule) + full-row
              PASTE button seedha SEND SMS ke upar. FORMAT field nahi — extraction
              Verify Settings ke prefix logic se hota hai. */}
          {/* TOKEN mode me bhi AUTO toggle (owner request) — label ke right side */}
          <View style={styles.labelRow}>
            <Text style={[styles.label, styles.labelFlush]}>PASTE TOKEN</Text>
            {autoToggle}
          </View>
          <TextInput
            value={token}
            onChangeText={(t) => { consumedRef.current = false; setToken(t); }}
            placeholder={'To : +919876543210\nMessage : Hello bhai'}
            placeholderTextColor={PALETTE.textDim}
            style={[styles.input, styles.multiline]}
            multiline
            testID="send-token"
          />
          <View style={styles.previewBox} testID="combo-preview">
            <Text style={[styles.previewText, token.trim().length > 0 && !parsed && { color: PALETTE.redSoft }]}>
              {previewText}
            </Text>
          </View>
          {/* Full-row PASTE — SEND SMS ke theek upar (owner request); sirf tab
              dikhta hai jab token box khali hai — paste karte hi gayab. */}
          {!token.trim() && (
            <Pressable
              onPress={pasteToken}
              style={({ pressed }) => [styles.pasteRowBtn, pressed && { opacity: 0.8 }]}
              testID="send-paste"
            >
              <Feather name="clipboard" size={13} color={PALETTE.primaryBright} />
              <Text style={styles.pasteRowText}>PASTE</Text>
            </Pressable>
          )}
        </>
      )}

      <Pressable
        onPress={send}
        disabled={!canSend}
        style={({ pressed }) => [styles.sendBtn, !canSend && styles.sendBtnOff, pressed && { opacity: 0.8 }]}
        testID="send-submit"
      >
        <Feather name="send" size={14} color={canSend ? PALETTE.primaryBright : PALETTE.textDim} />
        <Text style={[styles.sendBtnText, !canSend && { color: PALETTE.textDim }]}>SEND SMS</Text>
      </Pressable>

      <AutoVerifyDialog visible={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <AutoVerifyModal
        visible={avOpen}
        onClose={() => setAvOpen(false)}
        deviceId={deviceId}
        sim1Name={sim1Name}
        sim2Name={sim2Name}
      />
    </>
  );

  // bare = sheet ke andar — koi outer card frame nahi; warna pehle jaisa GradientCard
  return bare ? <View>{content}</View> : <GradientCard style={styles.frame}>{content}</GradientCard>;
}

const styles = StyleSheet.create({
  frame: { padding: 12 },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headTitle: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold', letterSpacing: 1.5 },
  label: { color: PALETTE.textMuted, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 1, marginTop: 12, marginBottom: 6 },
  seg: { flexDirection: 'row', borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10, overflow: 'hidden' },
  segCell: { flex: 1, alignItems: 'center', paddingVertical: 8, paddingHorizontal: 6, gap: 2 },
  segCellOn: { backgroundColor: PALETTE.primary },
  segTitle: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },
  segTitleOn: { color: '#ffffff' },
  segSub: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_400Regular' },
  segSubOn: { color: 'rgba(255,255,255,0.75)' },
  input: {
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_400Regular',
  },
  multiline: { minHeight: 74, textAlignVertical: 'top' },
  // MESSAGE box ke bottom-right corner ka chhota paste icon (purana UI — owner pasand)
  cornerPaste: {
    position: 'absolute', right: 8, bottom: 8,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 7,
    backgroundColor: PALETTE.bg, padding: 5,
  },
  // TO box ke ANDAR right side ka paste icon (vertically centered, full-row input ke andar)
  innerPaste: {
    position: 'absolute', right: 12, top: 0, bottom: 0, justifyContent: 'center',
    padding: 4,
  },
  // Label row — left me label, right me AUTO toggle
  labelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, marginBottom: 6 },
  labelFlush: { marginTop: 0, marginBottom: 0 },
  // AUTO switch (toggle button format — owner request): label + track + thumb
  autoRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  autoText: { color: PALETTE.textMuted, fontSize: 9, fontFamily: 'Inter_700Bold', letterSpacing: 0.8 },
  autoTextOn: { color: PALETTE.primaryBright },
  autoTrack: {
    width: 36, height: 20, borderRadius: 10, padding: 2, justifyContent: 'center',
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder,
  },
  autoTrackOn: { backgroundColor: PALETTE.primary, borderColor: PALETTE.primary },
  autoThumb: { width: 14, height: 14, borderRadius: 7, backgroundColor: PALETTE.textMuted },
  autoThumbOn: { backgroundColor: '#ffffff', alignSelf: 'flex-end' },
  // TOKEN mode ka live preview box (paste ke neeche)
  previewBox: {
    marginTop: 10, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 10,
    backgroundColor: PALETTE.bg, paddingHorizontal: 12, paddingVertical: 10, minHeight: 40, justifyContent: 'center',
  },
  previewText: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 17 },
  // TOKEN mode ka full-row PASTE button — SEND SMS ke theek upar
  pasteRowBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 12, paddingVertical: 10, marginTop: 10,
  },
  pasteRowText: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_700Bold', letterSpacing: 1.5 },
  sendBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 12, paddingVertical: 12, marginTop: 14,
  },
  sendBtnOff: { borderColor: PALETTE.fieldBorder, opacity: 0.6 },
  sendBtnText: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold', letterSpacing: 1.5 },
  headBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1, borderColor: PALETTE.primary, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4,
  },
  headBtnOn: { backgroundColor: PALETTE.primary },
  headBtnText: { color: PALETTE.primaryBright, fontSize: 9, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },
});
