import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader, usePanelTheme, useToast } from '@/components/panel/ui';
import { SessionRow } from '@/components/panel/dialogs';
import { panelAuthHeaders } from '@/lib/panelSession';
import {
  SESSION_ADMIN,
  SESSION_AUTO_LOGOUT,
  SESSION_THIS_DEVICE,
  SESSIONS,
  THEME_GRADIENTS,
  THEMES,
} from '@/constants/panelData';
import { PALETTE } from '@/constants/theme';

// otp.tsx jaisa hi base URL — Expo dev proxy ke through api-server.
import { API_BASE } from '@/lib/apiBase';

function CollapsibleSection({ title, children }: { title: string, children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <View style={styles.card}>
      <Pressable style={styles.collapsibleHeader} onPress={() => setExpanded(!expanded)}>
        <Text style={styles.cardTitle}>{title}</Text>
        <Feather name={expanded ? "chevron-up" : "chevron-down"} size={20} color="#f8fafc" />
      </Pressable>
      {expanded ? <View style={styles.collapsibleBody}>{children}</View> : null}
    </View>
  );
}

export default function SettingsScreen() {
  const { theme, setTheme } = usePanelTheme();
  const [toast, showToast] = useToast();
  const [aggressive, setAggressive] = useState(true);
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [sessions, setSessions] = useState(SESSIONS);

  const track = { false: PALETTE.borderSoft, true: THEME_GRADIENTS[theme][0] };

  return (
    <ScreenShell>
      <View style={{ flex: 1 }}>
        <GradientHeader style={styles.header}>
          <Pressable hitSlop={10} onPress={() => router.back()} testID="settings-back" style={styles.backBtn}>
            <Feather name="arrow-left" size={20} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle}>Settings</Text>
            <Text style={styles.headerSub}>Profile · security · Firebase</Text>
          </View>
        </GradientHeader>

        <ScrollView contentContainerStyle={styles.body}>
          {/* My Info */}
          <GradientCard style={styles.infoCard}>
            <Text style={styles.sectionLabel}>My Info</Text>
            <Text style={styles.infoUsername}>admin_01</Text>
            <View style={styles.infoDivider} />
            <Text style={styles.infoExp}>Plan expiry: 28-Aug-2026</Text>
            <Text style={styles.infoStatus}>Status: Active</Text>
            <Text style={styles.infoSession}>{'Session: a9f3…k2 · since 28-Jul 10:40'}</Text>
            <View style={styles.toggleRow}>
              <Text style={styles.toggleLabel}>Aggressive device online (4s pulse)</Text>
              <Switch
                value={aggressive}
                onValueChange={(v) => {
                  setAggressive(v);
                  // REAL sync — sab slots ke Firebase panelConfig/aggressiveOnline pe likho
                  void fetch(`${API_BASE}/api/panel/slots/aggressive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
                    body: JSON.stringify({ enabled: v }),
                  })
                    .then((r) => {
                      if (!r.ok) setAggressive(!v);
                      showToast(r.ok ? `Aggressive online ${v ? 'ON' : 'OFF'} — sab slots pe sync ✓` : 'Sync fail hua — dobara try karo');
                    })
                    .catch(() => { setAggressive(!v); showToast('Sync fail hua — connection check karo'); });
                }}
                trackColor={track}
                thumbColor="#fff"
              />
            </View>
          </GradientCard>

          {/* Change password */}
          <CollapsibleSection title="Change password">
            <TextInput value={newPass} onChangeText={setNewPass} placeholder="New password (min 6)" placeholderTextColor={PALETTE.textFaint} secureTextEntry style={[styles.input, { marginTop: 12 }]} testID="input-newpass" />
            <TextInput value={confirmPass} onChangeText={setConfirmPass} placeholder="Confirm new password" placeholderTextColor={PALETTE.textFaint} secureTextEntry style={[styles.input, { marginTop: 8 }]} testID="input-confirmpass" />
            {newPass.length >= 6 && newPass === confirmPass ? (
              <GradientButton label="Save changes" onPress={() => { setNewPass(''); setConfirmPass(''); showToast('Password updated'); }} testID="btn-save-pass" style={{ marginTop: 12 }} />
            ) : null}
          </CollapsibleSection>

          {/* Theme */}
          <CollapsibleSection title="Change theme">
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.themeRow}>
              {THEMES.map((t) => (
                <Pressable key={t} style={styles.themeItem} onPress={() => { setTheme(t); showToast('Theme updated'); }} testID={`theme-${t}`}>
                  <View style={[styles.themeCircle, { backgroundColor: THEME_GRADIENTS[t][0] }, theme === t && styles.themeCircleSelected]} />
                  <Text style={[styles.themeName, theme === t && { color: PALETTE.text }]}>{t}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </CollapsibleSection>

          {/* Active sessions */}
          <CollapsibleSection title="Active sessions">
            <Text style={styles.sessionLimit}>{sessions.length} / 2 devices logged in</Text>
            <Text style={styles.sessionInfo}>{SESSION_ADMIN}</Text>
            <Text style={styles.sessionInfo}>{SESSION_AUTO_LOGOUT}</Text>
            <Text style={styles.sessionInfo}>{SESSION_THIS_DEVICE}</Text>
            <View style={{ marginTop: 10 }}>
              {sessions.map((sess) => (
                <SessionRow key={sess.id} session={sess} onLogout={() => setSessions((p) => p.filter((x) => x.id !== sess.id))} />
              ))}
            </View>
            <GradientButton label="Refresh sessions" onPress={() => showToast('Sessions refreshed')} testID="btn-refresh-sessions" />
          </CollapsibleSection>

          {/* Sign out — FAB ke neeche na chhupe isliye bottom margin */}
          <View style={{ marginTop: 14, marginBottom: 96 }}>
            <GradientButton label="Sign out" onPress={() => router.replace('/')} testID="btn-signout" />
          </View>

        </ScrollView>
        <View style={styles.fabContainer}>
          <Pressable style={styles.fab} onPress={() => showToast('Settings saved')} testID="btn-save-settings">
            <Feather name="save" size={24} color="#ffffff" />
          </Pressable>
        </View>
      </View>
      {toast}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#ffffff', fontSize: 22, fontFamily: 'Inter_700Bold' },
  headerSub: { color: '#bcd8f0', fontSize: 12, fontFamily: 'Inter_400Regular' },
  body: { padding: 16, paddingBottom: 88 },
  infoCard: { padding: 16, marginBottom: 14, backgroundColor: PALETTE.cardAlt, borderRadius: 16, borderWidth: 1, borderColor: PALETTE.borderSoft },
  card: { marginBottom: 14, backgroundColor: PALETTE.cardAlt, borderRadius: 16, borderWidth: 1, borderColor: PALETTE.borderSoft },
  collapsibleHeader: { padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  collapsibleBody: { padding: 16, paddingTop: 0 },
  cardTitle: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold', flex: 1 },
  sectionLabel: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_700Bold' },
  infoUsername: { color: PALETTE.text, fontSize: 22, fontFamily: 'Inter_700Bold', marginTop: 8 },
  infoDivider: { height: 1, backgroundColor: PALETTE.border, marginVertical: 12 },
  infoExp: { color: PALETTE.redSoft, fontSize: 14, fontFamily: 'Inter_700Bold' },
  infoStatus: { color: PALETTE.green, fontSize: 13, fontFamily: 'Inter_400Regular', marginTop: 6 },
  infoSession: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 6, lineHeight: 17 },
  toggleRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  toggleLabel: { flex: 1, color: PALETTE.textE2, fontSize: 14, fontFamily: 'Inter_400Regular', marginRight: 10 },
  input: {
    backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.fieldBorder, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 12, color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_400Regular',
  },
  themeRow: { gap: 14, paddingVertical: 14, paddingHorizontal: 2 },
  themeItem: { alignItems: 'center', gap: 6 },
  themeCircle: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: 'transparent' },
  themeCircleSelected: { borderColor: PALETTE.textE2 },
  themeName: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_500Medium' },
  sessionLimit: { color: PALETTE.amber, fontSize: 12, fontFamily: 'Inter_700Bold', marginTop: 4 },
  sessionInfo: { color: PALETTE.textCbd, fontSize: 13, fontFamily: 'Inter_400Regular', marginTop: 6, lineHeight: 19 },
  fabContainer: { position: 'absolute', bottom: 20, width: '100%', alignItems: 'center' },
  fab: { width: 56, height: 56, borderRadius: 28, backgroundColor: PALETTE.primary, alignItems: 'center', justifyContent: 'center', elevation: 4, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.25, shadowRadius: 4 },
});
