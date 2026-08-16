import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientCard, GradientHeader, useToast } from '@/components/panel/ui';
import { panelAuthHeaders } from '@/lib/panelSession';
import { PALETTE } from '@/constants/theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_BASE } from '@/lib/apiBase';

export default function NotificationScreen() {
  const insets = useSafeAreaInsets();
  const [toast, showToast] = useToast();
  const track = { true: PALETTE.primaryBright, false: PALETTE.borderSoft };

  // Toggle state
  const [tgOtp, setTgOtp] = useState(false);
  const [savingToggle, setSavingToggle] = useState(false);

  // Chat ID save/edit cycle
  const [chatIdDraft, setChatIdDraft] = useState('');
  const [savedChatId, setSavedChatId] = useState('');
  const [chatIdEditing, setChatIdEditing] = useState(true); // first time = open
  const [savingId, setSavingId] = useState(false);

  // When toggle flips ON → always start in editing mode if no saved ID yet
  const handleToggle = (val: boolean) => {
    setTgOtp(val);
    if (val && !savedChatId) { setChatIdEditing(true); setChatIdDraft(''); }
  };

  // Save OTP toggle setting
  const saveToggle = async () => {
    if (savingToggle) return;
    setSavingToggle(true);
    try {
      await fetch(`${API_BASE}/api/panel/settings/notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ tgOtp, tgChatId: savedChatId }),
      });
      showToast('OTP setting saved ✓');
    } catch { showToast('Save fail — dobara try karo'); }
    finally { setSavingToggle(false); }
  };

  // Save Chat ID — transitions to saved state
  const saveChatId = async () => {
    if (savingId || !chatIdDraft.trim()) { showToast('Chat ID daalo pehle'); return; }
    setSavingId(true);
    try {
      const r = await fetch(`${API_BASE}/api/panel/settings/notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ tgOtp, tgChatId: chatIdDraft.trim() }),
      });
      if (r.ok) {
        setSavedChatId(chatIdDraft.trim());
        setChatIdEditing(false);
        showToast('Chat ID saved ✓');
      } else { showToast('Save fail — dobara try karo'); }
    } catch { showToast('Save fail — internet/API check karo'); }
    finally { setSavingId(false); }
  };

  // Enter edit mode
  const startEdit = () => {
    setChatIdDraft(savedChatId);
    setChatIdEditing(true);
  };

  return (
    <ScreenShell>
      <View style={{ flex: 1 }}>

        {/* ── Header ── */}
        <GradientHeader style={[styles.header, { paddingTop: insets.top + 10 }]}>
          <Pressable hitSlop={10} onPress={() => router.back()} style={styles.backBtn}>
            <Feather name="arrow-left" size={20} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle}>Notification</Text>
            <Text style={styles.headerSub}>Telegram alerts &amp; OTP settings</Text>
          </View>
        </GradientHeader>

        <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">

          {/* ── OTP toggle card ── */}
          <GradientCard style={styles.card}>
            <View style={styles.cardTitleRow}>
              <Feather name="shield" size={16} color={PALETTE.primaryBright} />
              <Text style={styles.cardTitle}>Two-Factor Auth (OTP)</Text>
            </View>

            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.toggleLabel}>Enable Telegram OTP (2FA)</Text>
                <Text style={styles.toggleSub}>Har naye device ke login pe OTP verify hoga</Text>
              </View>
              <Switch value={tgOtp} onValueChange={handleToggle} trackColor={track} thumbColor="#fff" />
            </View>

            {/* Chat ID section — only when 2FA ON */}
            {tgOtp && (
              <>
                <View style={styles.divider} />

                {/* Section label */}
                <View style={styles.cardTitleRow}>
                  <Feather name="send" size={14} color={PALETTE.primaryBright} />
                  <Text style={styles.cardTitle}>Telegram Chat ID</Text>
                </View>
                <Text style={styles.hint}>
                  <Text style={styles.hintLink}>@userinfobot</Text>
                  {' '}ko Telegram pe message karo — apna Chat ID milega.{'\n'}
                  OTP aur naye device alerts is number pe aayenge.
                </Text>

                {chatIdEditing ? (
                  /* ── EDITING STATE ── */
                  <>
                    <TextInput
                      value={chatIdDraft}
                      onChangeText={setChatIdDraft}
                      placeholder="e.g. 123456789"
                      placeholderTextColor={PALETTE.textFaint}
                      keyboardType="number-pad"
                      style={styles.input}
                      autoFocus={!!savedChatId} // only autofocus when re-editing
                      testID="input-tgchatid"
                    />
                    <Pressable
                      style={({ pressed }) => [styles.saveBtn, pressed && { opacity: 0.8 }]}
                      onPress={() => void saveChatId()}
                      testID="btn-save-chatid"
                    >
                      <Text style={styles.saveBtnText}>{savingId ? 'Saving…' : 'Save'}</Text>
                    </Pressable>
                  </>
                ) : (
                  /* ── SAVED STATE ── */
                  <>
                    <View style={styles.savedRow}>
                      <TextInput
                        value={savedChatId}
                        editable={false}
                        style={[styles.input, styles.inputSaved, { flex: 1, marginTop: 0 }]}
                        testID="display-tgchatid"
                      />
                      <Pressable
                        style={styles.editBtn}
                        onPress={startEdit}
                        testID="btn-edit-chatid"
                      >
                        <Text style={styles.editBtnText}>Edit</Text>
                      </Pressable>
                    </View>
                    <Text style={styles.savedLabel}>Saved ✓</Text>
                  </>
                )}
              </>
            )}
          </GradientCard>

          {/* ── How it works ── */}
          <GradientCard style={styles.card}>
            <View style={styles.cardTitleRow}>
              <Feather name="info" size={15} color={PALETTE.primaryBright} />
              <Text style={styles.cardTitle}>How it works</Text>
            </View>
            {[
              '2FA ON karte hi har naye device ke login pe OTP bheja jaata hai.',
              'OTP 6-digit ka hota hai aur 5 minute me expire ho jaata hai.',
              'SMS alerts alag hain — ye sirf panel login ke liye hai.',
              'Chat ID galat hone pe OTP nahi aayega — dobara check karo.',
            ].map((t, i) => (
              <View key={i} style={styles.howRow}>
                <View style={styles.howDot} />
                <Text style={styles.howText}>{t}</Text>
              </View>
            ))}
          </GradientCard>

          {/* OTP toggle save */}
          <Pressable
            style={({ pressed }) => [styles.saveBtn, { marginTop: 0 }, pressed && { opacity: 0.8 }]}
            onPress={() => void saveToggle()}
            testID="btn-save-toggle"
          >
            <Text style={styles.saveBtnText}>{savingToggle ? 'Saving…' : 'Save settings'}</Text>
          </Pressable>

        </ScrollView>
        {toast}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 14 },
  backBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#ffffff', fontSize: 20, fontFamily: 'Inter_700Bold' },
  headerSub: { color: 'rgba(255,255,255,0.7)', fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2 },

  body: { padding: 16, paddingBottom: 40 },
  card: { padding: 16, marginBottom: 14 },

  cardTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  cardTitle: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },

  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  toggleLabel: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },
  toggleSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 3 },

  divider: { height: 1, backgroundColor: PALETTE.borderSoft, marginVertical: 16 },

  hint: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18, marginBottom: 12 },
  hintLink: { color: PALETTE.primaryBright, fontFamily: 'Inter_700Bold' },

  // Editable input
  input: {
    backgroundColor: PALETTE.bg,
    borderWidth: 1, borderColor: PALETTE.fieldBorder,
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 13,
    color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_400Regular',
    marginTop: 4,
  },
  // Read-only saved state
  inputSaved: {
    borderColor: 'rgba(255,255,255,0.08)',
    color: PALETTE.textSoft,
  },

  // Saved row: input + Edit button side by side
  savedRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 },
  editBtn: {
    borderWidth: 1, borderColor: PALETTE.primaryBright,
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 13,
    alignItems: 'center', justifyContent: 'center',
  },
  editBtnText: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold' },

  // Faint "Saved ✓" label below
  savedLabel: {
    color: PALETTE.textFaint,
    fontSize: 11, fontFamily: 'Inter_400Regular',
    textAlign: 'center', marginTop: 8,
  },

  // Save button (shared for both Chat ID and toggle)
  saveBtn: {
    backgroundColor: PALETTE.primary,
    borderRadius: 14, paddingVertical: 15,
    alignItems: 'center', marginTop: 12,
  },
  saveBtnText: { color: '#ffffff', fontSize: 15, fontFamily: 'Inter_700Bold' },

  // How it works
  howRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 10 },
  howDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: PALETTE.primaryBright, marginTop: 5 },
  howText: { flex: 1, color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18 },
});
