import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader } from '@/components/panel/ui';
import {
  checkKeyStatus,
  connectChannel,
  saveKey,
} from '@/lib/avApi';
import { getActiveSlot } from '@/lib/activeSlot';
import { PALETTE } from '@/constants/theme';

// ── Types ────────────────────────────────────────────────────────────────────
type KeyState = 'empty' | 'checking' | 'active' | 'inactive' | 'offline';

interface SavedBot {
  id: string;
  key: string;
  chatId?: string; // channel chat ID (chat-ID connect se aaya; purane saved cards me nahi hoga)
  name: string;
  memberCount: number;
}

const BOTS_STORAGE = 'av_bots_v1';
const SELECTED_STORAGE = 'av_selected_v1';
const MAX_BOTS = 2;

// ── Helpers ──────────────────────────────────────────────────────────────────
async function loadBots(): Promise<SavedBot[]> {
  try { return JSON.parse((await AsyncStorage.getItem(BOTS_STORAGE)) ?? '[]'); }
  catch { return []; }
}
async function saveBots(bots: SavedBot[]): Promise<void> {
  try { await AsyncStorage.setItem(BOTS_STORAGE, JSON.stringify(bots)); } catch { /* ignore */ }
}
async function loadSelectedId(): Promise<string> {
  try { return (await AsyncStorage.getItem(SELECTED_STORAGE)) ?? ''; } catch { return ''; }
}
async function saveSelectedId(id: string): Promise<void> {
  try { await AsyncStorage.setItem(SELECTED_STORAGE, id); } catch { /* ignore */ }
}

// ── Main screen ───────────────────────────────────────────────────────────────
export default function AutoVerifyScreen() {
  // Bot management state
  const [bots, setBots] = useState<SavedBot[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [howItWorksOpen, setHowItWorksOpen] = useState(false);

  // Add/Edit modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingBot, setEditingBot] = useState<SavedBot | null>(null); // null = add new
  const [keyInput, setKeyInput] = useState('');
  const [chatIdInput, setChatIdInput] = useState('');
  const [connectMode, setConnectMode] = useState<'chatid' | 'key'>('chatid');
  const [addingLoading, setAddingLoading] = useState(false);
  const [addError, setAddError] = useState('');

  // Active bot key state (bot card ka status badge isi se chalta hai)
  const [activeKey, setActiveKey] = useState('');
  const [keyState, setKeyState] = useState<KeyState>('empty');
  const [channelTitle, setChannelTitle] = useState('');
  const [slotLabel, setSlotLabel] = useState('');
  const retriesRef = useRef(0);

  // ── Load bots + selected on mount ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [savedBots, savedSelectedId, slot] = await Promise.all([
        loadBots(), loadSelectedId(), getActiveSlot(),
      ]);
      if (cancelled) return;
      setBots(savedBots);
      setSelectedId(savedSelectedId);
      if (slot) setSlotLabel(slot.label);

      // Activate the selected bot key
      const sel = savedBots.find((b) => b.id === savedSelectedId);
      if (sel) {
        setActiveKey(sel.key);
        setChannelTitle(sel.name);
        void verifyKey(sel.key);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ── KEY verify ───────────────────────────────────────────────────────────
  const verifyKey = useCallback(async (key: string) => {
    setKeyState('checking');
    retriesRef.current = 0;
    const attempt = async (): Promise<void> => {
      const st = await checkKeyStatus(key);
      if (!st) { setKeyState('offline'); return; }
      if (st.exists && st.isAdmin) {
        setKeyState('active');
        setChannelTitle(st.channelTitle ?? '');
        return;
      }
      if (!st.exists && retriesRef.current < 4) {
        retriesRef.current += 1;
        setTimeout(() => void attempt(), 5000 * 2 ** (retriesRef.current - 1));
        return;
      }
      setKeyState('inactive');
      setChannelTitle(st.channelTitle ?? '');
    };
    await attempt();
  }, []);

  useEffect(() => {
    if (!activeKey) return;
    const t = setInterval(() => void verifyKey(activeKey), 60_000);
    return () => clearInterval(t);
  }, [activeKey, verifyKey]);

  // ── Bot management ───────────────────────────────────────────────────────
  const openAddBot = () => {
    setEditingBot(null);
    setKeyInput('');
    setChatIdInput('');
    setConnectMode('chatid'); // default: direct chat-ID connect (owner flow)
    setAddError('');
    setEditModalOpen(true);
  };

  const openEditBot = (bot: SavedBot) => {
    setEditingBot(bot);
    setKeyInput(bot.key);
    setChatIdInput(bot.chatId ?? '');
    setConnectMode('chatid'); // edit bhi chat-ID-first (channel change karne ka flow)
    setAddError('');
    setEditModalOpen(true);
  };

  const handleSaveBot = async () => {
    const trimmed = keyInput.trim();
    if (!trimmed) { setAddError('KEY cannot be empty'); return; }
    setAddingLoading(true);
    setAddError('');
    try {
      const st = await checkKeyStatus(trimmed);
      if (!st) { setAddError('Server unreachable — try again'); return; }
      if (!st.exists || !st.isAdmin) { setAddError('KEY invalid or bot is not admin in the channel'); return; }

      const newBot: SavedBot = {
        id: editingBot?.id ?? String(Date.now()),
        key: trimmed,
        // chatId sirf tab preserve karo jab key WOH hi ho (same channel) —
        // nayi key = naya channel, purana chatId galat dikhayega (code-review).
        chatId: editingBot && editingBot.key === trimmed ? editingBot.chatId : undefined,
        name: st.channelTitle ?? trimmed.slice(0, 12),
        memberCount: st.memberCount ?? 0,
      };

      const updated = editingBot
        ? bots.map((b) => b.id === editingBot.id ? newBot : b)
        : [...bots, newBot];

      setBots(updated);
      await saveBots(updated);

      // Auto-select if first bot or editing the currently selected one
      if (!editingBot || editingBot.id === selectedId) {
        setSelectedId(newBot.id);
        await saveSelectedId(newBot.id);
        await saveKey(newBot.key);
        setActiveKey(newBot.key);
        setChannelTitle(newBot.name);
        setKeyState('active');
      }

      setEditModalOpen(false);
    } finally {
      setAddingLoading(false);
    }
  };

  // Chat ID se direct connect — server verify karta hai (bot channel me admin?)
  // aur ACTIVE hote hi key AUTO-issue karta hai. Telegram bot pe Generate Key
  // karne ki zaroorat nahi (owner flow 2026-08-16).
  const handleConnectByChatId = async () => {
    const trimmed = chatIdInput.trim();
    if (!/^-?\d{5,20}$/.test(trimmed)) { setAddError('Sahi chat ID daalo — `-100…` wala number'); return; }
    setAddingLoading(true);
    setAddError('');
    try {
      const res = await connectChannel(trimmed);
      if (!res.ok || !res.key) {
        setAddError(
          res.error === 'not_channel_admin'
            ? 'Connect sirf channel ke ADMIN kar sakte hain — tum is channel ke admin nahi dikhte.'
            : res.error === 'bot_not_admin'
            ? `INACTIVE — bot "${res.channelTitle || 'is channel'}" me admin nahi hai. Pehle admin banao, phir try karo.`
            : res.error === 'channel_not_found'
              ? 'Channel nahi mila — pehle bot ko channel me add/admin banao.'
              : res.error === 'key_cap_reached'
                ? 'Key limit poori ho gayi — Telegram bot se purani key delete karo.'
                : res.error === 'telegram_unreachable' || res.error === 'bot_offline' || res.error === 'network'
                  ? 'Server abhi verify nahi kar paya — thodi der baad try karo.'
                  : 'Connect nahi ho paya — chat ID check karke dobara try karo.',
        );
        return;
      }
      // Edit me naya channel kisi DOOSRE card ka already-connected key nikal
      // aaye to reject karo — warna do cards ek hi relay pe ho jayenge (code-review).
      if (editingBot && bots.some((b) => b.id !== editingBot.id && b.key === res.key)) {
        setAddError('Ye channel doosre card se already connected hai — pehle use delete karo.');
        return;
      }
      // Edit ho rahi hai to usi card ko replace karo; warna same-key card pehle
      // se hai to UPDATE karo — naya slot mat khao (MAX_BOTS=2, code-review).
      const existing = editingBot ?? bots.find((b) => b.key === res.key);
      const newBot: SavedBot = {
        id: existing?.id ?? String(Date.now()),
        key: res.key,
        chatId: trimmed,
        name: res.channelTitle ?? trimmed,
        memberCount: res.memberCount ?? existing?.memberCount ?? 0,
      };
      const updated = existing ? bots.map((b) => (b.id === existing.id ? newBot : b)) : [...bots, newBot];
      setBots(updated);
      await saveBots(updated);
      // Active relay sirf ADD ya SELECTED-card edit pe switch ho (KEY-edit jaisa) —
      // non-selected card edit karte waqt selection chupke mat badlo (code-review).
      if (!editingBot || editingBot.id === selectedId) {
        setSelectedId(newBot.id);
        await saveSelectedId(newBot.id);
        await saveKey(newBot.key);
        setActiveKey(newBot.key);
        setChannelTitle(newBot.name);
        setKeyState('active');
      }
      setEditModalOpen(false);
    } finally {
      setAddingLoading(false);
    }
  };

  const handleSelectBot = async (bot: SavedBot) => {
    setSelectedId(bot.id);
    await saveSelectedId(bot.id);
    await saveKey(bot.key);
    setActiveKey(bot.key);
    setChannelTitle(bot.name);
    void verifyKey(bot.key);
  };

  const handleDeleteBot = async (bot: SavedBot) => {
    const updated = bots.filter((b) => b.id !== bot.id);
    setBots(updated);
    await saveBots(updated);
    if (bot.id === selectedId) {
      const next = updated[0];
      const nextId = next?.id ?? '';
      setSelectedId(nextId);
      await saveSelectedId(nextId);
      if (next) {
        await saveKey(next.key);
        setActiveKey(next.key);
        setChannelTitle(next.name);
        void verifyKey(next.key);
      } else {
        await saveKey('');
        setActiveKey('');
        setChannelTitle('');
        setKeyState('empty');
      }
    }
  };

  const handleClose = () => { router.back(); };

  return (
    <ScreenShell>
      <GradientHeader>
        <View style={styles.headerRow}>
          <Pressable hitSlop={10} onPress={handleClose}>
            <Feather name="chevron-left" size={24} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle}>Auto Verify</Text>
            <Text style={styles.headerSub}>OTP auto-detect settings</Text>
          </View>
        </View>
      </GradientHeader>

      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">

        {/* ── HOW IT WORKS ── */}
        <GradientCard style={styles.collapseCard}>
          <Pressable style={styles.collapseHeader} onPress={() => setHowItWorksOpen((o) => !o)} testID="av-how-toggle">
            <Feather name="zap" size={13} color={PALETTE.primaryBright} />
            <Text style={styles.collapseTitle}>HOW IT WORKS</Text>
            <View style={{ flex: 1 }} />
            <Feather name={howItWorksOpen ? 'chevron-up' : 'chevron-down'} size={16} color={PALETTE.textMuted} />
          </Pressable>
          {howItWorksOpen ? (
            <View style={styles.collapseBody}>
              {[
                '1. Apne Telegram channel me hamare bot ko ADMIN banao.',
                '2. Yahan + Add Bot pe channel ka CHAT ID daalo (`-100…`) — app turant ACTIVE/INACTIVE batayega.',
                '3. ACTIVE hote hi auto-connect (key khud ban jati hai) — channel ke naye posts ~1 second me live.',
              ].map((line, i) => (
                <Text key={i} style={styles.howLine}>{line}</Text>
              ))}
            </View>
          ) : null}
        </GradientCard>

        {/* ── TELEGRAM BOT ── */}
        <GradientCard style={styles.botCard}>
          {/* Section header */}
          <View style={styles.botSectionHeader}>
            <Feather name="send" size={14} color={PALETTE.primaryBright} />
            <Text style={styles.botSectionTitle}>Telegram Bot</Text>
          </View>

          {bots.length === 0 ? (
            /* Empty state */
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No Telegram bots configured yet. Add one to enable Auto Verify.</Text>
            </View>
          ) : (
            /* Bot cards */
            bots.map((bot) => {
              const isSelected = bot.id === selectedId;
              const botKeyState = isSelected ? keyState : 'empty';
              const statusLabel = isSelected
                ? (keyState === 'active' ? 'ACTIVE' : keyState === 'checking' ? 'CHECKING' : keyState === 'inactive' ? 'INACTIVE' : keyState === 'offline' ? 'OFFLINE' : 'UNKNOWN')
                : 'INACTIVE';
              const statusColor = statusLabel === 'ACTIVE' ? PALETTE.green : statusLabel === 'CHECKING' ? PALETTE.amber : PALETTE.red;

              return (
                <View key={bot.id} style={[styles.botEntry, isSelected && styles.botEntrySelected]}>
                  {/* Bot name */}
                  <Text style={styles.botName}>{bot.name || 'Bot'}</Text>

                  {/* CHAT ID row (key internal hai — user ko sirf channel dikhta hai) */}
                  <View style={styles.botKeyRow}>
                    <View style={styles.botKeyBox}>
                      <Text style={styles.botKeyLabel}>CHAT ID  –  </Text>
                      <Text style={styles.botKeyVal} numberOfLines={1}>{bot.chatId ?? bot.key.slice(0, 18) + '…'}</Text>
                    </View>
                    <View style={[styles.statusPill, { borderColor: statusColor }]}>
                      <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
                      <Text style={[styles.statusText, { color: statusColor }]}>{statusLabel}</Text>
                    </View>
                  </View>

                  {/* Member count */}
                  <View style={styles.memberRow}>
                    <Feather name="users" size={12} color={PALETTE.textFaint} />
                    <Text style={styles.memberCount}>{bot.memberCount}</Text>
                  </View>

                  {/* Actions */}
                  <View style={styles.botActions}>
                    <Pressable style={styles.actionBtn} onPress={() => openEditBot(bot)} testID={`av-edit-${bot.id}`}>
                      <Feather name="edit-2" size={11} color={PALETTE.textMuted} />
                      <Text style={styles.actionBtnText}>EDIT</Text>
                    </Pressable>
                    <Pressable
                      style={[styles.actionBtn, isSelected && styles.actionBtnSelected]}
                      onPress={() => void handleSelectBot(bot)}
                      testID={`av-select-${bot.id}`}
                    >
                      <Feather name="check-circle" size={11} color={isSelected ? PALETTE.primaryBright : PALETTE.textMuted} />
                      <Text style={[styles.actionBtnText, isSelected && { color: PALETTE.primaryBright }]}>
                        {isSelected ? 'SELECTED' : 'SELECT'}
                      </Text>
                    </Pressable>
                    <Pressable style={[styles.actionBtn, styles.actionBtnDelete]} onPress={() => void handleDeleteBot(bot)} testID={`av-delete-${bot.id}`}>
                      <Feather name="trash-2" size={11} color={PALETTE.red} />
                      <Text style={[styles.actionBtnText, { color: PALETTE.red }]}>DELETE</Text>
                    </Pressable>
                  </View>
                </View>
              );
            })
          )}

          {/* Add Bot button */}
          {bots.length < MAX_BOTS ? (
            <Pressable style={styles.addBotBtn} onPress={openAddBot} testID="av-add-bot">
              <Text style={styles.addBotText}>+ Add Bot ({bots.length}/{MAX_BOTS})</Text>
            </Pressable>
          ) : null}

        </GradientCard>

      </ScrollView>

      {/* ── ADD / EDIT BOT MODAL ── */}
      <Modal visible={editModalOpen} transparent animationType="fade" onRequestClose={() => setEditModalOpen(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{editingBot ? 'Edit Bot' : 'Add Bot'}</Text>
              <Pressable hitSlop={10} onPress={() => setEditModalOpen(false)}>
                <Feather name="x" size={18} color={PALETTE.textMuted} />
              </Pressable>
            </View>
            <View style={styles.modalDivider} />

            {connectMode === 'chatid' ? (
              <>
                <Text style={styles.modalLabel}>CHANNEL CHAT ID</Text>
                <TextInput
                  value={chatIdInput}
                  onChangeText={(t) => { setChatIdInput(t); setAddError(''); }}
                  placeholder="e.g. -1001234567890"
                  placeholderTextColor={PALETTE.textFaint}
                  style={styles.modalInput}
                  autoCapitalize="none"
                  autoCorrect={false}
                  testID="av-chatid-input"
                />
                {addError ? <Text style={styles.modalError}>{addError}</Text> : null}

                <Text style={styles.modalHint}>Bot ko apne channel me ADMIN banao, phir chat ID yahan daalo — ACTIVE hote hi auto-connect ho jayega (key khud ban jayegi).</Text>

                <GradientButton
                  label={addingLoading ? 'Verifying…' : 'Verify & Connect'}
                  onPress={() => void handleConnectByChatId()}
                  disabled={addingLoading}
                  style={{ marginTop: 16 }}
                  testID="av-connect-chatid"
                />
                <Pressable onPress={() => { setConnectMode('key'); setAddError(''); }} style={{ marginTop: 12 }} testID="av-mode-key">
                  <Text style={styles.modeToggle}>Advanced: KEY se connect karo</Text>
                </Pressable>
              </>
            ) : (
              <>
                <Text style={styles.modalLabel}>PASTE YOUR BOT KEY</Text>
                <TextInput
                  value={keyInput}
                  onChangeText={(t) => { setKeyInput(t); setAddError(''); }}
                  placeholder="e.g. 26VRQ2TPXUBLMQWK"
                  placeholderTextColor={PALETTE.textFaint}
                  style={styles.modalInput}
                  autoCapitalize="none"
                  autoCorrect={false}
                  testID="av-key-input"
                />
                {addError ? <Text style={styles.modalError}>{addError}</Text> : null}

                <Text style={styles.modalHint}>Get this from your Telegram bot → Auto Verify → Generate KEY</Text>

                <GradientButton
                  label={addingLoading ? 'Verifying…' : (editingBot ? 'Save Changes' : 'Add & Verify')}
                  onPress={() => void handleSaveBot()}
                  disabled={addingLoading}
                  style={{ marginTop: 16 }}
                  testID="av-save-bot"
                />
                <Pressable onPress={() => { setConnectMode('chatid'); setAddError(''); }} style={{ marginTop: 12 }} testID="av-mode-chatid">
                  <Text style={styles.modeToggle}>Chat ID se connect karo (recommended)</Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>

    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'center', paddingBottom: 4 },
  headerTitle: { color: '#fff', fontSize: 18, fontFamily: 'Inter_700Bold' },
  headerSub: { color: 'rgba(255,255,255,0.65)', fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },

  body: { padding: 16, paddingBottom: 40 },
  card: { padding: 16, marginBottom: 14 },

  // HOW IT WORKS
  collapseCard: { padding: 0, marginBottom: 14, overflow: 'hidden' },
  collapseHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 14 },
  collapseTitle: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_700Bold', letterSpacing: 1 },
  collapseBody: { paddingHorizontal: 16, paddingBottom: 14, gap: 6 },
  howLine: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 19 },

  // TELEGRAM BOT SECTION
  botCard: { padding: 16, marginBottom: 14 },
  botSectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  botSectionTitle: { color: PALETTE.primaryBright, fontSize: 14, fontFamily: 'Inter_700Bold' },

  emptyState: { paddingVertical: 20, alignItems: 'center' },
  emptyText: { color: PALETTE.textFaint, fontSize: 13, fontFamily: 'Inter_400Regular', textAlign: 'center', fontStyle: 'italic' },

  botEntry: {
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    borderRadius: 10,
    marginBottom: 10,
    overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.02)',
  },
  botEntrySelected: {
    borderColor: PALETTE.primaryBright,
    backgroundColor: 'rgba(82,169,255,0.05)',
  },

  botName: {
    color: PALETTE.primaryBright,
    fontSize: 14,
    fontFamily: 'Inter_700Bold',
    textAlign: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: PALETTE.borderSoft,
  },

  botKeyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: PALETTE.borderSoft,
    gap: 8,
  },
  botKeyBox: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  botKeyLabel: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_700Bold' },
  botKeyVal: { flex: 1, color: PALETTE.text, fontSize: 11, fontFamily: 'Inter_400Regular' },

  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },

  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: PALETTE.borderSoft,
  },
  memberCount: { color: PALETTE.textFaint, fontSize: 12, fontFamily: 'Inter_400Regular' },

  botActions: { flexDirection: 'row' },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 10,
    borderRightWidth: 1,
    borderRightColor: PALETTE.borderSoft,
  },
  actionBtnSelected: { backgroundColor: 'rgba(82,169,255,0.08)' },
  actionBtnDelete: { borderRightWidth: 0, borderLeftWidth: 1, borderLeftColor: 'rgba(220,50,50,0.3)' },
  actionBtnText: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_700Bold', letterSpacing: 0.5 },

  addBotBtn: {
    marginTop: 4,
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.02)',
  },
  addBotText: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold' },

  // ADD/EDIT MODAL
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalCard: { width: '100%', backgroundColor: '#0d1829', borderRadius: 16, borderWidth: 1, borderColor: PALETTE.borderSoft, padding: 20 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  modalTitle: { color: PALETTE.primaryBright, fontSize: 15, fontFamily: 'Inter_700Bold' },
  modalDivider: { height: 1, backgroundColor: PALETTE.borderSoft, marginBottom: 16 },
  modalLabel: { color: PALETTE.textFaint, fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.9, marginBottom: 8 },
  modalInput: {
    backgroundColor: PALETTE.bg,
    borderWidth: 1,
    borderColor: PALETTE.fieldBorder,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: PALETTE.text,
    fontSize: 13,
    fontFamily: 'Inter_400Regular',
  },
  modalError: { color: PALETTE.red, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 6 },
  modalHint: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 10, lineHeight: 17 },
  modeToggle: { color: PALETTE.primaryBright, fontSize: 11, fontFamily: 'Inter_700Bold', textAlign: 'center' },
});
