import React from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { PALETTE } from '@/constants/theme';

/**
 * Full-bleed dark background wrapper used by every panel screen.
 * Handles safe-area top padding (and the web status-bar inset).
 */
export function ScreenShell({
  children,
  pad = true,
}: {
  children: React.ReactNode;
  pad?: boolean;
}) {
  const insets = useSafeAreaInsets();
  // On web the iframe reports 0 insets; guarantee a small status-bar gap.
  const topInset = Platform.OS === 'web' ? Math.max(insets.top, 12) : insets.top;
  return (
    <View style={styles.root}>
      <View style={[styles.inner, pad && { paddingTop: topInset }]}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: PALETTE.bg },
  inner: { flex: 1 },
});
