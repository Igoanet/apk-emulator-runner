import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { Animated, Modal, Pressable, StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { PALETTE } from '@/constants/theme';
import { THEME_GRADIENTS, ThemeName } from '@/constants/panelData';

/* ---------- Theme context (AdminThemeHelper equivalent) ---------- */

const ThemeCtx = createContext<{ theme: ThemeName; setTheme: (t: ThemeName) => void; cycleTheme: () => void }>({
  theme: 'Ocean',
  setTheme: () => {},
  cycleTheme: () => {},
});

export function usePanelTheme() {
  return useContext(ThemeCtx);
}

export const ThemeProvider = ThemeCtx.Provider;

function useGrad(): [string, string] {
  const { theme } = useContext(ThemeCtx);
  return THEME_GRADIENTS[theme] ?? THEME_GRADIENTS.Ocean;
}

/* ---------- Gradient header — bg_vip_header ---------- */

export function GradientHeader({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  const grad = useGrad();
  return (
    <LinearGradient colors={grad} start={{ x: 0, y: 0 }} end={{ x: 0, y: 1 }} style={[styles.header, style]}>
      {children}
    </LinearGradient>
  );
}

/* ---------- Gradient button — bg_vip_btn / VipButtonPrimary ---------- */

export function GradientButton({
  label, onPress, testID, style, innerStyle, disabled,
}: {
  label: string; onPress?: () => void; testID?: string; style?: ViewStyle; innerStyle?: ViewStyle; disabled?: boolean;
}) {
  const grad = useGrad();
  return (
    <Pressable onPress={onPress} disabled={disabled} testID={testID} style={({ pressed }) => [{ borderRadius: 14, overflow: 'hidden' }, style, pressed && { opacity: 0.85 }, disabled && { opacity: 0.45 }]}>
      <LinearGradient colors={grad} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={[styles.btn, innerStyle]}>
        <Text style={styles.btnText}>{label}</Text>
      </LinearGradient>
    </Pressable>
  );
}

/* ---------- Outline button — VipButtonOutline / bg_vip_btn_outline ---------- */

export function OutlineButton({
  label, onPress, testID, style, color,
}: {
  label: string; onPress?: () => void; testID?: string; style?: ViewStyle; color?: string;
}) {
  return (
    <Pressable onPress={onPress} testID={testID} style={({ pressed }) => [styles.outlineBtn, style, pressed && { opacity: 0.8 }]}>
      <Text style={[styles.outlineBtnText, color ? { color } : null]}>{label}</Text>
    </Pressable>
  );
}

/* ---------- Two-tone navy card — bg_vip_card ---------- */

export function GradientCard({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <LinearGradient colors={[...PALETTE.cardGrad]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.card, style]}>
      {children}
    </LinearGradient>
  );
}

/* ---------- Centered dialog shell ---------- */

export function PanelModal({
  visible, onClose, children,
}: {
  visible: boolean; onClose: () => void; children: React.ReactNode;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.dialogWrap} onPress={() => {}}>
          <LinearGradient colors={[...PALETTE.cardGrad]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.dialog}>
            {children}
          </LinearGradient>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

/* ---------- Minimal toast (Android Toast equivalent) ---------- */

export function useToast(): [React.ReactNode, (msg: string) => void] {
  const [msg, setMsg] = useState('');
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const show = (text: string) => {
    setMsg(text);
    if (timer.current) clearTimeout(timer.current);
    Animated.timing(opacity, { toValue: 1, duration: 150, useNativeDriver: true }).start();
    timer.current = setTimeout(() => {
      Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => setMsg(''));
    }, 2200);
  };

  const node = msg ? (
    <Animated.View style={[styles.toast, { opacity }]} pointerEvents="none">
      <Text style={styles.toastText}>{msg}</Text>
    </Animated.View>
  ) : null;
  return [node, show];
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 12, paddingVertical: 12 },
  btn: { paddingVertical: 13, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center' },
  btnText: { color: '#ffffff', fontSize: 15, fontFamily: 'Inter_700Bold' },
  outlineBtn: {
    paddingVertical: 11, paddingHorizontal: 16, borderRadius: 12, alignItems: 'center',
    backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.primaryBright,
  },
  outlineBtnText: { color: PALETTE.text, fontSize: 13, fontFamily: 'Inter_600SemiBold' },
  card: { borderRadius: 18, borderWidth: 1, borderColor: PALETTE.borderSoft },
  backdrop: { flex: 1, backgroundColor: 'rgba(2,6,17,0.72)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  dialogWrap: { width: '100%', maxWidth: 380 },
  dialog: { borderRadius: 18, borderWidth: 1, borderColor: PALETTE.borderSoft, padding: 18 },
  toast: {
    position: 'absolute', bottom: 42, alignSelf: 'center', zIndex: 50,
    backgroundColor: '#1f2937', borderRadius: 20, paddingHorizontal: 16, paddingVertical: 9,
    borderWidth: 1, borderColor: PALETTE.borderSoft,
  },
  toastText: { color: '#f9fafb', fontSize: 13, fontFamily: 'Inter_500Medium' },
});
