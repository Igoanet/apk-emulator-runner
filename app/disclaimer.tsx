import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, useToast } from '@/components/panel/ui';
import { DISCLAIMER_BODY } from '@/constants/panelData';
import { PALETTE } from '@/constants/theme';

// Exact replica of dialog_disclaimer.xml (shown as a full screen here).
export default function DisclaimerScreen() {
  const [accepted, setAccepted] = useState(false);
  const [toast, showToast] = useToast();

  return (
    <ScreenShell>
      <View style={styles.wrap}>
        <GradientCard style={styles.card}>
          <Text style={styles.title}>Welcome to IgoanPanel</Text>
          <Text style={styles.sub}>Please read before you continue</Text>

          <ScrollView style={styles.bodyScroll} nestedScrollEnabled>
            <Text style={styles.body}>{DISCLAIMER_BODY}</Text>
          </ScrollView>

          <Pressable style={styles.acceptRow} onPress={() => setAccepted((a) => !a)} testID="toggle-terms">
            <View style={[styles.checkbox, accepted && styles.checkboxOn]}>
              {accepted ? <Feather name="check" size={12} color="#ffffff" /> : null}
            </View>
            <Text style={styles.acceptText}>I have read and agree to the Terms & Conditions</Text>
          </Pressable>

          <Pressable onPress={() => showToast('The full terms are shown in the scrollable text above')} testID="view-terms">
            <Text style={styles.termsLink}>View full Terms & Privacy Policy</Text>
          </Pressable>

          <GradientButton
            label="Continue"
            disabled={!accepted}
            onPress={() => router.replace('/main')}
            testID="btn-continue"
            style={{ marginTop: 16 }}
          />
        </GradientCard>
      </View>
      {toast}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: 'center', padding: 20 },
  card: { padding: 20 },
  title: { color: PALETTE.text, fontSize: 22, fontFamily: 'JetBrainsMono_700Bold' },
  sub: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_400Regular', marginTop: 4 },
  bodyScroll: { maxHeight: 280, marginTop: 14 },
  body: { color: PALETTE.textCbd, fontSize: 13, fontFamily: 'Inter_400Regular', lineHeight: 21 },
  acceptRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 14 },
  checkbox: {
    width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: PALETTE.fieldBorder,
    alignItems: 'center', justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: PALETTE.primary, borderColor: PALETTE.primary },
  acceptText: { flex: 1, color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_500Medium' },
  termsLink: { color: PALETTE.teal, fontSize: 13, fontFamily: 'Inter_700Bold', marginTop: 8, paddingVertical: 4 },
});
