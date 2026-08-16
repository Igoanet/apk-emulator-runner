import React from 'react';
import { Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, OutlineButton } from '@/components/panel/ui';
import { PALETTE } from '@/constants/theme';
import { sec } from '@/lib/secure';

// Exact replica of activity_tampering.xml — text-only lockout screen,
// two side-by-side buttons, no icon artwork.
export default function TamperScreen() {
  return (
    <ScreenShell>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>App tampering detected</Text>
        <Text style={styles.body}>For legitimate access contact @Igoan on Telegram.</Text>
        <Text style={styles.reason}>Reason: integrity check failed (demo)</Text>
        <Text style={styles.note}>Admin password is not configured or changed from this app.</Text>

        <View style={styles.btnRow}>
          <GradientButton label="Contact @Igoan" onPress={() => Linking.openURL(sec('telegramChannel'))} testID="btn-contact" style={{ flex: 1 }} />
          <OutlineButton label="Exit app" onPress={() => router.replace('/' as const)} testID="btn-exit-app" style={{ flex: 1 }} />
        </View>
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 20 },
  title: { color: PALETTE.redSoft, fontSize: 22, fontFamily: 'Inter_700Bold' },
  body: { color: PALETTE.textE2, fontSize: 15, fontFamily: 'Inter_400Regular', marginTop: 8, lineHeight: 22 },
  reason: { color: PALETTE.textMuted, fontSize: 14, fontFamily: 'Inter_400Regular', marginTop: 12 },
  note: { color: PALETTE.textFaint, fontSize: 13, fontFamily: 'Inter_400Regular', marginTop: 16, lineHeight: 19 },
  btnRow: { flexDirection: 'row', gap: 8, marginTop: 20 },
});
