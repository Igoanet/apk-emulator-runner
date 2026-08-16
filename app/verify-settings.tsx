import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader } from '@/components/panel/ui';
import {
  BUILTIN_NUMBER_PREFIXES,
  BUILTIN_TOKEN_PREFIXES,
  addCustomPrefix,
  getCustomPrefixes,
  initCustomPrefixes,
  parseMessage,
  removeCustomPrefix,
  type ParsedMessage,
  type PrefixKind,
} from '@/lib/autoVerify';
import { PALETTE } from '@/constants/theme';

export default function VerifySettingsScreen() {
  const [numCustom, setNumCustom] = useState<string[]>([]);
  const [msgCustom, setMsgCustom] = useState<string[]>([]);
  const [numInput, setNumInput] = useState('');
  const [msgInput, setMsgInput] = useState('');
  const [testMsg, setTestMsg] = useState('');
  const [testResult, setTestResult] = useState<ParsedMessage | null>(null);

  useEffect(() => {
    let alive = true;
    // Pehle AsyncStorage se hydrate — warna restart ke baad saved prefixes nahi dikhte.
    void initCustomPrefixes().then(() => {
      if (!alive) return;
      setNumCustom(getCustomPrefixes('number'));
      setMsgCustom(getCustomPrefixes('message'));
    });
    return () => { alive = false; };
  }, []);

  const add = (kind: PrefixKind) => {
    const raw = kind === 'number' ? numInput : msgInput;
    if (!addCustomPrefix(kind, raw)) return;
    if (kind === 'number') { setNumCustom(getCustomPrefixes('number')); setNumInput(''); }
    else { setMsgCustom(getCustomPrefixes('message')); setMsgInput(''); }
  };

  const remove = (kind: PrefixKind, p: string) => {
    removeCustomPrefix(kind, p);
    if (kind === 'number') setNumCustom(getCustomPrefixes('number'));
    else setMsgCustom(getCustomPrefixes('message'));
  };

  const renderSection = (
    kind: PrefixKind,
    title: string,
    emoji: string,
    builtins: string[],
    customs: string[],
    inputVal: string,
    setInput: (v: string) => void,
    placeholder: string,
  ) => (
    <GradientCard style={styles.card}>
      <View style={styles.secTitle}>
        <Text style={styles.secEmoji}>{emoji}</Text>
        <Text style={styles.secName}>{title}</Text>
      </View>
      <Text style={styles.mini}>SELECTED</Text>
      <View style={styles.chipWrap}>
        {builtins.map((p) => (
          <View key={p} style={styles.chip}><Text style={styles.chipText}>{p}</Text></View>
        ))}
        {customs.map((p) => (
          <View key={p} style={[styles.chip, styles.chipCustom]}>
            <Text style={styles.chipText}>{p}</Text>
            <Pressable hitSlop={8} onPress={() => remove(kind, p)} testID={`vs-remove-${p}`}>
              <Feather name="x" size={11} color={PALETTE.red} />
            </Pressable>
          </View>
        ))}
      </View>
      <View style={styles.inputRow}>
        <TextInput
          value={inputVal}
          onChangeText={setInput}
          placeholder={placeholder}
          placeholderTextColor={PALETTE.textFaint}
          style={styles.input}
          returnKeyType="done"
          onSubmitEditing={() => add(kind)}
          testID={`vs-input-${kind}`}
        />
        <Pressable style={styles.addBtn} onPress={() => add(kind)} testID={`vs-add-${kind}`}>
          <Text style={styles.addBtnText}>Add</Text>
        </Pressable>
      </View>
    </GradientCard>
  );

  return (
    <ScreenShell>
      <GradientHeader>
        <View style={styles.headerRow}>
          <Pressable hitSlop={10} onPress={() => router.back()}>
            <Feather name="chevron-left" size={24} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle}>Verify Settings</Text>
            <Text style={styles.headerSub}>Number + message nikalne ke prefixes</Text>
          </View>
        </View>
      </GradientHeader>

      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">

        {renderSection(
          'number', 'NUMBER', '📞',
          BUILTIN_NUMBER_PREFIXES, numCustom,
          numInput, setNumInput, 'e.g. Receiver: or Send No:',
        )}

        {renderSection(
          'message', 'MESSAGE', '💬',
          BUILTIN_TOKEN_PREFIXES, msgCustom,
          msgInput, setMsgInput, 'e.g. SMS: or Notification:',
        )}

        {/* Test Parsing */}
        <GradientCard style={styles.card}>
          <View style={styles.secTitle}>
            <Text style={styles.secEmoji}>🧪</Text>
            <Text style={styles.secName}>Test Parsing</Text>
          </View>
          <Text style={styles.testHint}>
            Telegram message paste karke check karo ki number aur message sahi parse ho raha hai.
          </Text>
          <TextInput
            value={testMsg}
            onChangeText={(t) => { setTestMsg(t); setTestResult(null); }}
            placeholder="Telegram message paste karein…"
            placeholderTextColor={PALETTE.textFaint}
            style={[styles.input, { minHeight: 80, textAlignVertical: 'top', marginTop: 10 }]}
            multiline
            testID="vs-test-input"
          />
          <GradientButton
            label="Run Test"
            onPress={() => setTestResult(parseMessage(testMsg))}
            style={{ marginTop: 10 }}
            testID="vs-test-run"
          />
          {testResult ? (
            <View style={styles.resultWrap}>
              <Text style={[styles.mini, {
                color: testResult.number || testResult.token ? PALETTE.green : PALETTE.red,
                marginBottom: 6,
              }]}>
                {testResult.number || testResult.token ? '✅ SUCCESSFUL' : '❌ FAILED — NO MATCHES'}
              </Text>
              <Text style={styles.mini}>NUMBER</Text>
              <Text style={styles.resultVal}>{testResult.number ?? '— not found —'}</Text>
              <Text style={[styles.mini, { marginTop: 8 }]}>MESSAGE</Text>
              <Text style={styles.resultVal}>{testResult.token ?? '— not found —'}</Text>
            </View>
          ) : null}
        </GradientCard>

      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', paddingBottom: 4 },
  headerTitle: { color: '#fff', fontSize: 18, fontFamily: 'Inter_700Bold' },
  headerSub: { color: 'rgba(255,255,255,0.65)', fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },

  body: { padding: 16, paddingBottom: 40 },
  card: { padding: 16, marginBottom: 14 },

  secTitle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  secEmoji: { fontSize: 16 },
  secName: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },

  mini: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.8, marginBottom: 8 },

  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginBottom: 12 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5,
  },
  chipCustom: { borderColor: PALETTE.primaryBright, backgroundColor: 'rgba(82,169,255,0.1)' },
  chipText: { color: PALETTE.textSoft, fontSize: 12, fontFamily: 'Inter_400Regular' },

  inputRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: {
    flex: 1,
    backgroundColor: PALETTE.bg,
    borderWidth: 1, borderColor: PALETTE.fieldBorder,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11,
    color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_400Regular',
  },
  addBtn: {
    backgroundColor: PALETTE.primaryBright,
    borderRadius: 10, paddingHorizontal: 18, paddingVertical: 11,
  },
  addBtnText: { color: '#fff', fontSize: 13, fontFamily: 'Inter_700Bold' },

  testHint: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18 },

  resultWrap: {
    marginTop: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 10, padding: 12,
  },
  resultVal: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_400Regular', marginBottom: 4 },
});
