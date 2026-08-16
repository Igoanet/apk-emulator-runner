import React, { useEffect, useRef } from 'react';
import { Animated, Dimensions, Modal, PanResponder, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { PALETTE } from '@/constants/theme';

// Reusable bottom-sheet — neeche se slide up, upar drag handle (slide bar),
// kheench ke neeche band. Get Number aur Send SMS dono isi ko use karte hain.

export const SHEET_MAX = Math.round(Dimensions.get('window').height * 0.8);
const DRAG_CLOSE = 120;

export function SlideSheet({
  visible, onClose, children, title, sub, scrollable, centered,
}: {
  visible: boolean; onClose: () => void; children: React.ReactNode;
  title?: string; sub?: string; scrollable?: boolean;
  // centered = true → sheet bottom ke bajaye screen ke BEECH me khulti hai
  // (owner request: Send SMS dialog center me chahiye, neeche chipka hua nahi).
  centered?: boolean;
}) {
  const openY = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) Animated.spring(openY, { toValue: 0, useNativeDriver: true, damping: 20, stiffness: 260 }).start();
    else openY.setValue(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const close = () => {
    Animated.timing(openY, { toValue: SHEET_MAX, duration: 220, useNativeDriver: true }).start(() => onClose());
  };

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4 && Math.abs(g.dy) > Math.abs(g.dx),
      onPanResponderMove: (_, g) => { if (g.dy > 0) openY.setValue(g.dy); },
      onPanResponderRelease: (_, g) => {
        if (g.dy > DRAG_CLOSE || g.vy > 0.7) close();
        else Animated.spring(openY, { toValue: 0, useNativeDriver: true, damping: 24, stiffness: 320 }).start();
      },
    }),
  ).current;

  const sheetContent = (
    <>
      <View style={styles.barWrap} {...pan.panHandlers}>
        <View style={styles.bar} testID="sheet-handle" />
      </View>
      {title ? (
        <View style={styles.head}>
          <Text style={styles.title}>{title}</Text>
          {sub ? <Text style={styles.sub}>{sub}</Text> : null}
        </View>
      ) : null}
      {scrollable ? (
        <ScrollView style={styles.bodyScroll} showsVerticalScrollIndicator={false} bounces={false}>{children}</ScrollView>
      ) : (
        <View style={styles.body}>{children}</View>
      )}
    </>
  );

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close} statusBarTranslucent>
      {centered ? (
        // CENTERED variant — screen ke beech me floating card, dimmed backdrop.
        <View style={styles.rootCenter}>
          <Pressable style={StyleSheet.absoluteFill} onPress={close} testID="sheet-backdrop" />
          <Animated.View style={[styles.sheetCenter, { transform: [{ translateY: openY }] }]}>
            {sheetContent}
          </Animated.View>
        </View>
      ) : (
        <>
          <View style={styles.root}>
            <Pressable style={StyleSheet.absoluteFill} onPress={close} testID="sheet-backdrop" />
          </View>
          <Animated.View style={[styles.sheet, { transform: [{ translateY: openY }] }]}>
            {sheetContent}
          </Animated.View>
        </>
      )}
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  sheet: {
    position: 'absolute', left: 0, right: 0, bottom: 0, maxHeight: SHEET_MAX,
    backgroundColor: PALETTE.card, borderTopLeftRadius: 22, borderTopRightRadius: 22,
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderBottomWidth: 0,
    paddingTop: 8, paddingBottom: 26,
  },
  barWrap: { alignSelf: 'center', paddingVertical: 8, paddingHorizontal: 40 },
  bar: { width: 44, height: 5, borderRadius: 3, backgroundColor: PALETTE.fieldBorder },
  // CENTERED variant styles — floating card screen ke beech me, dimmed backdrop.
  rootCenter: { flex: 1, justifyContent: 'center', padding: 18, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheetCenter: {
    maxHeight: SHEET_MAX, backgroundColor: PALETTE.card, borderRadius: 22,
    borderWidth: 1, borderColor: PALETTE.borderSoft, paddingTop: 8, paddingBottom: 26,
  },
  head: { paddingHorizontal: 18, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: PALETTE.borderSoft },
  body: { paddingHorizontal: 18, paddingTop: 14 },
  bodyScroll: { paddingHorizontal: 18, paddingTop: 14 },
  title: { color: PALETTE.text, fontSize: 17, fontFamily: 'Inter_700Bold' },
  sub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 3 },
});
