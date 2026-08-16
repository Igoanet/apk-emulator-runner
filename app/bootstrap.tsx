import React, { useEffect, useRef, useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { BOOTSTRAP_STEPS } from '@/constants/panelData';
import { PALETTE } from '@/constants/theme';

export default function BootstrapScreen() {
  const [pct, setPct] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    for (let i = 0; i <= 100; i += 5) {
      timers.current.push(setTimeout(() => setPct(i), i * 26));
    }
    timers.current.push(setTimeout(() => router.replace('/disclaimer'), 2900));
    return () => timers.current.forEach(clearTimeout);
  }, []);

  const doneSteps = Math.floor((pct / 100) * BOOTSTRAP_STEPS.length);
  const syncing = pct >= 60 && pct < 90;

  return (
    <ScreenShell>
      <View style={styles.container}>
        <Image source={require('@/assets/images/login_hacker12.png')} style={styles.logo} />
        <Text style={styles.title}>IgoanPanel</Text>
        <Text style={styles.subtitle}>{syncing ? 'Syncing Firebase (1/2)…' : 'Preparing your dashboard…'}</Text>

        <View style={styles.track}>
          <View style={[styles.fill, { width: `${pct}%` }]} />
        </View>
        <Text style={styles.pct}>{pct}%</Text>

        <View style={styles.steps}>
          {BOOTSTRAP_STEPS.map((step, i) => {
            const done = i < doneSteps;
            const active = i === doneSteps;
            return (
              <View key={step} style={styles.stepRow}>
                <Text style={[styles.stepIcon, done && styles.stepIconDone]}>{done ? '✓' : '○'}</Text>
                <Text style={[styles.stepText, done && styles.stepTextDone, active && styles.stepTextActive]}>{step}</Text>
              </View>
            );
          })}
        </View>

        {pct >= 90 ? <Text style={styles.devices}>2 slots · 8 connections loaded</Text> : null}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: 32 },
  logo: { width: 72, height: 72, borderRadius: 36, borderWidth: 2, borderColor: PALETTE.primary, alignSelf: 'center', marginBottom: 16 },
  title: { color: PALETTE.text, fontSize: 24, fontFamily: 'JetBrainsMono_700Bold', textAlign: 'center' },
  subtitle: { color: PALETTE.textFaint, fontSize: 13, fontFamily: 'Inter_400Regular', marginTop: 4, marginBottom: 28, textAlign: 'center' },
  track: { height: 6, borderRadius: 4, backgroundColor: PALETTE.border, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: PALETTE.primary, borderRadius: 4 },
  pct: { color: PALETTE.primary, fontSize: 12, fontFamily: 'Inter_700Bold', marginTop: 8, textAlign: 'center' },
  steps: { marginTop: 24, gap: 8 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  stepIcon: { color: PALETTE.textDim, fontSize: 13, width: 16, textAlign: 'center' },
  stepIconDone: { color: PALETTE.primary },
  stepText: { color: PALETTE.textDim, fontSize: 13, fontFamily: 'Inter_400Regular' },
  stepTextActive: { color: PALETTE.textMuted },
  stepTextDone: { color: PALETTE.textMuted },
  devices: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 20, textAlign: 'center' },
});
