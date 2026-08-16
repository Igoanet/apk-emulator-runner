import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientCard, GradientHeader } from '@/components/panel/ui';
import { BROADCASTS } from '@/constants/panelData';
import { PALETTE } from '@/constants/theme';

// Exact replica of activity_broadcast_inbox.xml + item_broadcast_inbox.xml.
export default function BroadcastScreen() {
  return (
    <ScreenShell>
      <GradientHeader style={styles.header}>
        <Pressable hitSlop={10} onPress={() => router.back()} testID="broadcast-back" style={styles.backBtn}>
          <Feather name="arrow-left" size={20} color="#ffffff" />
        </Pressable>
        <Text style={styles.headerTitle}>Broadcast</Text>
      </GradientHeader>

      <ScrollView contentContainerStyle={styles.body}>
        {BROADCASTS.map((b) => (
          <GradientCard key={b.id} style={styles.card}>
            <Text style={styles.cardDate}>{b.date}</Text>
            <Text style={styles.cardMessage}>{b.message}</Text>
            {b.isNew ? (
              <View style={styles.newBadge}><Text style={styles.newBadgeText}>NEW</Text></View>
            ) : null}
          </GradientCard>
        ))}
      </ScrollView>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#ffffff', fontSize: 20, fontFamily: 'Inter_700Bold', marginLeft: 8 },
  body: { padding: 16, paddingBottom: 40 },
  card: { padding: 14, marginBottom: 10 },
  cardDate: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular' },
  cardMessage: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_400Regular', marginTop: 6, lineHeight: 21 },
  newBadge: {
    alignSelf: 'flex-start', backgroundColor: 'rgba(251,191,36,0.2)', borderRadius: 4,
    paddingHorizontal: 8, paddingVertical: 2, marginTop: 8,
  },
  newBadgeText: { color: PALETTE.amber, fontSize: 10, fontFamily: 'Inter_700Bold' },
});
