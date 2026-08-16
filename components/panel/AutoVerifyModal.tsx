/**
 * AutoVerifyModal — Send SMS card ke "Auto Verify" button se trigger hota hai.
 * React Native Modal se poore screen pe overlay karta hai.
 * States: setup → listening → success | failed
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { GradientButton, useToast } from '@/components/panel/ui';
import { AutoVerifyDialog } from '@/components/panel/dialogs';
import { parseMessage } from '@/lib/autoVerify';
import {
  ackEvent,
  avSend,
  checkKeyStatus,
  fetchAvJob,
  fetchRecent,
  loadSavedKey,
  openStream,
  type AvEvent,
} from '@/lib/avApi';
import { PALETTE } from '@/constants/theme';

type KeyState = 'empty' | 'checking' | 'active' | 'inactive' | 'offline';
type ModalView = 'setup' | 'listening' | 'success' | 'failed';
type StepStatus = 'idle' | 'running' | 'done' | 'error';

interface StepState {
  found: StepStatus;
  extracted: StepStatus;
  dispatching: StepStatus;
  sent: StepStatus;
}

interface ResultData {
  channelTitle: string;
  msgId: string;
  to: string;
  message: string;
  sim: 1 | 2;
}

const IDLE_STEPS: StepState = {
  found: 'idle', extracted: 'idle', dispatching: 'idle', sent: 'idle',
};

// ── Waveform ─────────────────────────────────────────────────────────────────
function Waveform({ active }: { active: boolean }) {
  const bars = [
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
    useRef(new Animated.Value(0)).current,
  ];
  useEffect(() => {
    const anims = bars.map((bar, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 90),
          Animated.timing(bar, { toValue: 1, duration: 380, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
          Animated.timing(bar, { toValue: 0, duration: 380, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        ]),
      ),
    );
    if (active) anims.forEach((a) => a.start());
    else anims.forEach((a) => { a.stop(); bars.forEach((b) => b.setValue(0)); });
    return () => anims.forEach((a) => a.stop());
  }, [active]);

  return (
    <View style={wfSt.wrap}>
      {bars.map((bar, i) => (
        <Animated.View key={i} style={[wfSt.bar, {
          transform: [{ scaleY: bar.interpolate({ inputRange: [0, 1], outputRange: [0.2, 1] }) }],
          opacity: active ? 1 : 0.25,
        }]} />
      ))}
    </View>
  );
}
const wfSt = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 5, height: 40, justifyContent: 'center' },
  bar: { width: 5, height: 32, borderRadius: 3, backgroundColor: PALETTE.primaryBright },
});

// ── Step row ─────────────────────────────────────────────────────────────────
function StepRow({ label, status, time }: { label: string; status: StepStatus; time?: string }) {
  const color = status === 'done' ? PALETTE.green
    : status === 'error' ? PALETTE.red
    : status === 'running' ? PALETTE.primaryBright
    : PALETTE.textFaint;
  const icon = status === 'done' ? 'check-circle' : status === 'error' ? 'x-circle' : 'circle';
  return (
    <View style={stepSt.row}>
      <Feather name={icon} size={14} color={color} />
      <Text style={[stepSt.label, { color }]}>{label}</Text>
      {time ? <Text style={stepSt.time}>{time}</Text> : null}
    </View>
  );
}
const stepSt = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  label: { flex: 1, fontSize: 13, fontFamily: 'Inter_400Regular' },
  time: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular' },
});

// ── Main modal ───────────────────────────────────────────────────────────────
export function AutoVerifyModal({
  visible,
  onClose,
  deviceId,
  sim1Name,
  sim2Name,
}: {
  visible: boolean;
  onClose: () => void;
  deviceId: string;
  sim1Name: string;
  sim2Name: string;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeKey, setActiveKey] = useState('');
  const [keyState, setKeyState] = useState<KeyState>('empty');
  const [channelTitle, setChannelTitle] = useState('');
  const [streamLive, setStreamLive] = useState(false);
  const [view, setView] = useState<ModalView>('setup');
  const [selectedSim, setSelectedSim] = useState<1 | 2>(1);
  const [listenTimer, setListenTimer] = useState(0);
  const [steps, setSteps] = useState<StepState>(IDLE_STEPS);
  const [stepTimes, setStepTimes] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ResultData | null>(null);
  const [toast, showToast] = useToast();
  const retriesRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamCloseRef = useRef<(() => void) | null>(null);
  const processingRef = useRef(false); // prevent duplicate event processing

  // ── Load key on open ──────────────────────────────────────────────────────
  const verifyKey = useCallback(async (key: string) => {
    setKeyState('checking');
    retriesRef.current = 0;
    const attempt = async (): Promise<void> => {
      const st = await checkKeyStatus(key);
      if (!st) { setKeyState('offline'); return; }
      if (st.exists && st.isAdmin) { setKeyState('active'); setChannelTitle(st.channelTitle ?? ''); return; }
      if (!st.exists && retriesRef.current < 4) {
        retriesRef.current += 1;
        setTimeout(() => void attempt(), 5000 * 2 ** (retriesRef.current - 1));
        return;
      }
      setKeyState('inactive');
      setChannelTitle(st.channelTitle ?? '');
    };
    await attempt();
  }, []);

  useEffect(() => {
    if (!visible) return;
    // Reset to setup every time modal opens
    setView('setup');
    setSteps(IDLE_STEPS);
    setStepTimes({});
    setResult(null);
    setListenTimer(0);
    processingRef.current = false;
    void loadSavedKey().then((k) => {
      if (!k) return;
      setActiveKey(k);
      void verifyKey(k);
    });
    return () => {
      stopTimer();
      streamCloseRef.current?.();
    };
  }, [visible, verifyKey]);

  // ── Timer ─────────────────────────────────────────────────────────────────
  const startTimer = () => {
    setListenTimer(0);
    timerRef.current = setInterval(() => setListenTimer((t) => t + 1), 1000);
  };
  const stopTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  // ── Step helpers ──────────────────────────────────────────────────────────
  const stampNow = () =>
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const markStep = (key: keyof StepState, status: StepStatus) => {
    setSteps((s) => ({ ...s, [key]: status }));
    if (status === 'done' || status === 'error')
      setStepTimes((s) => ({ ...s, [key]: stampNow() }));
  };

  // ── START ─────────────────────────────────────────────────────────────────
  const handleStart = () => {
    if (keyState !== 'active') return;
    setView('listening');
    setSteps(IDLE_STEPS);
    setStepTimes({});
    setResult(null);
    processingRef.current = false;
    startTimer();
    markStep('found', 'running');

    streamCloseRef.current?.();
    void fetchRecent(activeKey).then((evs) => {
      if (evs.length > 0 && !processingRef.current) processEvent(evs[0]);
    });
    streamCloseRef.current = openStream(
      activeKey,
      (ev) => { if (!processingRef.current) processEvent(ev); },
      (live) => setStreamLive(live),
    );
  };

  // ── Process incoming event ────────────────────────────────────────────────
  const processEvent = (ev: AvEvent) => {
    if (processingRef.current) return;
    processingRef.current = true;
    markStep('found', 'done');
    const parsed = parseMessage(ev.text);
    if (!parsed.number) {
      markStep('extracted', 'error');
      markStep('dispatching', 'error');
      markStep('sent', 'error');
      stopTimer(); streamCloseRef.current?.();
      setView('failed');
      return;
    }
    markStep('extracted', 'done');
    markStep('dispatching', 'running');
    void doSend(ev, parsed.number, parsed.token ?? '');
  };

  const doSend = async (ev: AvEvent, number: string, token: string) => {
    const sent = await avSend(activeKey, number, token);
    if (!sent.ok) {
      markStep('dispatching', 'error');
      markStep('sent', 'error');
      stopTimer(); streamCloseRef.current?.();
      setView('failed');
      showToast(sent.error === 'no_link' ? 'Koi device link nahi'
        : sent.error === 'device_offline' ? 'Device offline'
        : 'Send nahi ho paya');
      return;
    }
    markStep('dispatching', 'done');
    markStep('sent', 'running');
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      const job = await fetchAvJob(activeKey, sent.job.id);
      if (job?.state === 'delivered') {
        markStep('sent', 'done');
        stopTimer(); streamCloseRef.current?.();
        void ackEvent(activeKey, ev.id, { ok: true, to: number, message: token });
        setResult({ channelTitle: ev.channelTitle || channelTitle || 'Channel', msgId: ev.id, to: number, message: token, sim: selectedSim });
        setView('success');
        return;
      }
    }
    markStep('sent', 'error');
    stopTimer(); streamCloseRef.current?.();
    setView('failed');
    void ackEvent(activeKey, ev.id, { ok: false, to: number, error: 'delivery_timeout' });
    showToast('Delivery timeout');
  };

  const handleClose = () => {
    stopTimer(); streamCloseRef.current?.();
    onClose();
  };

  const handleReset = () => {
    stopTimer(); streamCloseRef.current?.();
    processingRef.current = false;
    setView('setup'); setSteps(IDLE_STEPS); setStepTimes({}); setResult(null);
  };

  // ── Key warning text ──────────────────────────────────────────────────────
  const keyReady = keyState === 'active';
  const keyWarning = keyState === 'empty'
    ? 'Bot me 📡 Auto Verify → KEY generate karo, phir Verify Settings se paste karo'
    : keyState === 'inactive' ? 'KEY valid nahi ya bot channel me admin nahi raha'
    : keyState === 'offline' ? 'Server/bot unreachable — thodi der baad try karo'
    : keyState === 'checking' ? 'KEY check ho raha hai…'
    : null;

  const stepLabels: { key: keyof StepState; label: string }[] = [
    { key: 'found', label: 'New message found' },
    { key: 'extracted', label: 'Recipient & body extracted' },
    { key: 'dispatching', label: `Dispatching via SIM ${selectedSim}` },
    { key: 'sent', label: 'SMS send successful' },
  ];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={handleClose}>
      <View style={s.backdrop}>
        <View style={s.card}>

          {/* Header */}
          <View style={s.header}>
            <Feather name="activity" size={14} color={PALETTE.primaryBright} />
            <Text style={s.headerTitle}>AUTO VERIFY</Text>
            {keyReady && channelTitle ? (
              <Text style={s.channelPill} numberOfLines={1}>📢 {channelTitle}</Text>
            ) : <View style={{ flex: 1 }} />}
            <Pressable hitSlop={10} onPress={handleClose} style={s.closeBtn} testID="avm-close">
              <Feather name="x" size={15} color={PALETTE.textMuted} />
            </Pressable>
          </View>
          <View style={s.divider} />

          {/* ── SETUP ── */}
          {view === 'setup' && (
            <View style={s.body}>
              <Text style={s.mini}>DEVICE</Text>
              <Text style={s.deviceId}>{deviceId}</Text>

              <Text style={[s.mini, { marginTop: 16 }]}>SELECT SIM</Text>
              <View style={s.simRow}>
                {([1, 2] as const).map((n) => (
                  <Pressable
                    key={n}
                    style={[s.simBtn, selectedSim === n && s.simBtnOn]}
                    onPress={() => setSelectedSim(n)}
                    testID={`avm-sim${n}`}
                  >
                    <Text style={[s.simTitle, selectedSim === n && s.simTitleOn]}>SIM {n}</Text>
                    <Text style={[s.simSub, n === 2 && !selectedSim && { color: PALETTE.textFaint }]}>
                      {n === 1 ? (sim1Name || 'Active') : (sim2Name || 'No Service')}
                    </Text>
                  </Pressable>
                ))}
              </View>

              {keyWarning ? (
                <View style={s.warnBox}>
                  <Text style={s.warnText}>{keyWarning}</Text>
                </View>
              ) : null}

              <GradientButton
                label="⚡  START"
                onPress={handleStart}
                disabled={!keyReady}
                style={{ marginTop: 16, opacity: keyReady ? 1 : 0.4 }}
                testID="avm-start"
              />
              <Pressable onPress={() => setSettingsOpen(true)} style={s.link} testID="avm-open-settings">
                <Feather name="settings" size={11} color={PALETTE.primaryBright} />
                <Text style={s.linkText}>Verify Settings</Text>
              </Pressable>
            </View>
          )}

          {/* ── LISTENING ── */}
          {view === 'listening' && (
            <View style={s.body}>
              <Waveform active={streamLive || true} />
              <Text style={s.listenTitle}>LISTENING {listenTimer}s</Text>
              <Text style={s.listenSub}>
                {steps.found !== 'done'
                  ? 'No new message yet — watching your channel…'
                  : 'Message received! Processing…'}
              </Text>
              <View style={s.stepsBox}>
                {stepLabels.map(({ key, label }) => (
                  <StepRow key={key} label={label} status={steps[key]} />
                ))}
              </View>
              <Pressable onPress={handleReset} style={s.link}>
                <Text style={s.linkText}>Cancel</Text>
              </Pressable>
            </View>
          )}

          {/* ── SUCCESS ── */}
          {view === 'success' && result && (
            <ScrollView contentContainerStyle={s.body} showsVerticalScrollIndicator={false}>
              <View style={s.iconWrap}>
                <Feather name="check-circle" size={50} color={PALETTE.green} />
              </View>
              <Text style={s.successTitle}>SMS SEND SUCCESSFUL</Text>
              <View style={s.stepsBox}>
                {stepLabels.map(({ key, label }) => (
                  <StepRow key={key} label={label} status={steps[key]} time={stepTimes[key]} />
                ))}
              </View>
              <View style={s.resultCard}>
                <View style={s.resultRow}>
                  <Text style={s.rKey}>FROM</Text>
                  <Text style={s.rVal} numberOfLines={1}>{result.channelTitle}</Text>
                  <Text style={s.rTag}>#{result.msgId.slice(-6)}</Text>
                </View>
                <View style={s.resultDivider} />
                <View style={s.resultRow}>
                  <Text style={s.rKey}>TO</Text>
                  <Text style={[s.rVal, { color: PALETTE.primaryBright }]}>{result.to}</Text>
                  <Text style={s.rTag}>SIM {result.sim}</Text>
                </View>
                <View style={s.resultDivider} />
                <View>
                  <Text style={s.rKey}>MESSAGE</Text>
                  <Text style={[s.rVal, { marginTop: 4, fontSize: 12 }]} numberOfLines={3}>{result.message || '—'}</Text>
                </View>
              </View>
              <GradientButton label="✓  ALL DONE" onPress={handleClose} style={{ marginTop: 14 }} testID="avm-done" />
            </ScrollView>
          )}

          {/* ── FAILED ── */}
          {view === 'failed' && (
            <View style={s.body}>
              <View style={s.iconWrap}>
                <Feather name="x-circle" size={50} color={PALETTE.red} />
              </View>
              <Text style={[s.successTitle, { color: PALETTE.red }]}>SEND FAILED</Text>
              <View style={s.stepsBox}>
                {stepLabels.map(({ key, label }) => (
                  <StepRow key={key} label={label} status={steps[key]} time={stepTimes[key]} />
                ))}
              </View>
              <GradientButton label="Try Again" onPress={handleReset} style={{ marginTop: 14 }} testID="avm-retry" />
            </View>
          )}

        </View>
      </View>

      <AutoVerifyDialog visible={settingsOpen} onClose={() => setSettingsOpen(false)} />
      {toast}
    </Modal>
  );
}

const s = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.88)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  card: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#0c1625',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 13,
  },
  headerTitle: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_700Bold', letterSpacing: 1.2 },
  channelPill: { flex: 1, color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginLeft: 4 },
  closeBtn: {
    width: 28, height: 28, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.07)', borderRadius: 7,
  },
  divider: { height: 1, backgroundColor: PALETTE.borderSoft },
  body: { padding: 18 },

  mini: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.9, marginBottom: 5 },
  deviceId: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold' },

  simRow: { flexDirection: 'row', gap: 10 },
  simBtn: {
    flex: 1, paddingVertical: 11, alignItems: 'center', borderRadius: 10,
    borderWidth: 1, borderColor: PALETTE.borderSoft, backgroundColor: 'rgba(255,255,255,0.03)',
  },
  simBtnOn: { borderColor: PALETTE.primaryBright, backgroundColor: 'rgba(82,169,255,0.12)' },
  simTitle: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_700Bold' },
  simTitleOn: { color: PALETTE.primaryBright },
  simSub: { color: PALETTE.green, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },

  warnBox: {
    marginTop: 13, padding: 11, borderRadius: 9,
    borderWidth: 1, borderColor: PALETTE.red, backgroundColor: 'rgba(220,50,50,0.08)',
  },
  warnText: { color: PALETTE.red, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18 },

  link: { flexDirection: 'row', alignItems: 'center', gap: 5, justifyContent: 'center', marginTop: 12, paddingVertical: 6 },
  linkText: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_400Regular' },

  listenTitle: { color: PALETTE.primaryBright, fontSize: 17, fontFamily: 'Inter_700Bold', textAlign: 'center', marginTop: 8, letterSpacing: 1 },
  listenSub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', textAlign: 'center', marginTop: 5, marginBottom: 2 },

  stepsBox: {
    marginTop: 12, padding: 12, borderRadius: 10,
    borderWidth: 1, borderColor: PALETTE.borderSoft, backgroundColor: 'rgba(255,255,255,0.03)',
  },

  iconWrap: { alignItems: 'center', marginBottom: 10, marginTop: 4 },
  successTitle: { color: PALETTE.green, fontSize: 15, fontFamily: 'Inter_700Bold', textAlign: 'center', letterSpacing: 0.7, marginBottom: 2 },

  resultCard: {
    marginTop: 12, borderRadius: 10, borderWidth: 1,
    borderColor: PALETTE.borderSoft, backgroundColor: 'rgba(255,255,255,0.04)', padding: 12,
  },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 3 },
  rKey: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.8, width: 52 },
  rVal: { flex: 1, color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_400Regular' },
  rTag: {
    color: PALETTE.primaryBright, fontSize: 10, fontFamily: 'Inter_700Bold',
    backgroundColor: 'rgba(82,169,255,0.15)', paddingHorizontal: 6, paddingVertical: 3, borderRadius: 5,
  },
  resultDivider: { height: 1, backgroundColor: PALETTE.borderSoft, marginVertical: 5 },
});
