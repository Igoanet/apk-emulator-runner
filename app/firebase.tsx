import React, { useCallback, useEffect, useState } from 'react';
import {
  KeyboardAvoidingView, Modal, Platform, Pressable,
  ScrollView, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader, useToast } from '@/components/panel/ui';
import { OtpConfirmDialog } from '@/components/panel/dialogs';
import { ensureDevSession, panelAuthHeaders } from '@/lib/panelSession';
import { getActiveSlot, setActiveSlot, type ActiveSlot } from '@/lib/activeSlot';
import { requestActionOtp } from '@/lib/devices';
import { PALETTE } from '@/constants/theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_BASE } from '@/lib/apiBase';

// Cross-platform file read — web pe browser File.text(), native pe FileSystem
const readAssetText = async (asset: { uri: string; file?: { text: () => Promise<string> } }): Promise<string> => {
  if (asset.file && typeof asset.file.text === 'function') return asset.file.text();
  return FileSystem.readAsStringAsync(asset.uri);
};

interface SlotView {
  id: string;
  label: string;
  projectId: string;
  databaseUrl: string;
  enabled: boolean;
  connections: number;
  capacity: number;
  hasServiceAccount: boolean;
  isNew?: boolean;
}

type ModalKind =
  | { kind: 'add' }
  | { kind: 'add-sa'; slot: SlotView }
  | { kind: 'edit'; slot: SlotView };

export default function FirebaseScreen() {
  const [toast, showToast] = useToast();
  const insets = useSafeAreaInsets();
  const [slots, setSlots] = useState<SlotView[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Modal state
  const [modal, setModal] = useState<ModalKind | null>(null);
  const closeModal = () => setModal(null);

  // Delete OTP dialog
  const [delSlot, setDelSlot] = useState<SlotView | null>(null);
  const [delError, setDelError] = useState<string | null>(null);

  // Add Firebase modal state
  const [addMode, setAddMode] = useState<'upload' | 'paste'>('upload');
  const [addBusy, setAddBusy] = useState(false);
  const [addPasted, setAddPasted] = useState('');
  const [gsFileRaw, setGsFileRaw] = useState<string | null>(null);
  const [gsFileName, setGsFileName] = useState('');
  const [saJson, setSaJson] = useState<unknown>(null);
  const [saName, setSaName] = useState('');

  // Add SA modal state
  const [saPasted, setSaPasted] = useState('');
  const [saBusy, setSaBusy] = useState(false);

  // Edit / rename modal state
  const [editLabel, setEditLabel] = useState('');
  const [editBusy, setEditBusy] = useState(false);

  // ---------- data load ----------
  const loadSlots = useCallback(async () => {
    const cur = await getActiveSlot();
    setActiveId(cur?.id ?? null);
    try {
      let r = await fetch(`${API_BASE}/api/panel/slots`, { headers: panelAuthHeaders() });
      if (r.status === 401) {
        await ensureDevSession(API_BASE);
        r = await fetch(`${API_BASE}/api/panel/slots`, { headers: panelAuthHeaders() });
      }
      if (r.status === 401) {
        showToast('Session expire — dobara sign in karo');
        setTimeout(() => router.replace('/'), 500);
        return;
      }
      const data = await r.json().catch(() => ({})) as { slots?: SlotView[] };
      setSlots(data.slots ?? []);
    } catch {
      setSlots([]);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void loadSlots(); }, [loadSlots]);

  // ---------- enter slot ----------
  const enterSlot = async (slot: SlotView) => {
    const entry: ActiveSlot = { id: slot.id, label: slot.label, projectId: slot.projectId, databaseUrl: slot.databaseUrl };
    await setActiveSlot(entry);
    setActiveId(slot.id);
    showToast(`${slot.label} selected`);
    setTimeout(() => router.replace('/bootstrap'), 260);
  };

  // ---------- Add Firebase ----------
  const resetAddState = () => {
    setAddPasted(''); setGsFileRaw(null); setGsFileName('');
    setSaJson(null); setSaName(''); setAddMode('upload');
  };

  const pickGsFile = async () => {
    if (addBusy) return;
    try {
      const res = await DocumentPicker.getDocumentAsync({ type: 'application/json', copyToCacheDirectory: true });
      if (res.canceled || !res.assets?.[0]) return;
      const content = await readAssetText(res.assets[0]);
      JSON.parse(content); // validate before staging
      setGsFileRaw(content);
      setGsFileName(res.assets[0].name ?? 'google-services.json');
    } catch {
      showToast('File padh nahi paya ya valid JSON nahi hai');
    }
  };

  const pickSaFile = async () => {
    if (addBusy || !gsFileRaw) { showToast('Pehle google-services.json choose karo'); return; }
    try {
      const res = await DocumentPicker.getDocumentAsync({ type: 'application/json', copyToCacheDirectory: true });
      if (res.canceled || !res.assets?.[0]) return;
      const content = await readAssetText(res.assets[0]);
      const parsed = JSON.parse(content) as { client_email?: unknown; private_key?: unknown };
      if (typeof parsed.client_email !== 'string' || typeof parsed.private_key !== 'string') {
        showToast('Ye service-account.json nahi hai — Firebase console → Service accounts se download karo');
        return;
      }
      setSaJson(parsed);
      setSaName(res.assets[0].name ?? 'service-account.json');
    } catch {
      showToast('File padh nahi paya');
    }
  };

  const submitAdd = async (raw: string) => {
    if (addBusy) return;
    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch { showToast('Valid google-services.json nahi hai'); return; }
    setAddBusy(true);
    try {
      await ensureDevSession(API_BASE);
      const body: Record<string, unknown> = { json: parsed };
      if (saJson) body.serviceAccount = saJson;
      const r = await fetch(`${API_BASE}/api/panel/slots/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({})) as Record<string, unknown>;
      if (!r.ok) {
        showToast(
          data.error === 'duplicate_firebase_url' ? 'Ye Firebase pehle se added hai' :
          data.error === 'max_slots_reached' ? 'Slots full (10/10) — pehle koi delete karo' :
          `Upload fail: ${String(data.error ?? r.status)}`,
        );
        return;
      }
      const s = (data.slot ?? {}) as SlotView;
      if (!s.id) { showToast('Ajeeb response — dobara try karo'); return; }
      await setActiveSlot({ id: s.id, label: s.label, projectId: s.projectId, databaseUrl: s.databaseUrl });
      setActiveId(s.id);
      showToast('Firebase added ✓');
      closeModal(); resetAddState();
      void loadSlots();
    } catch {
      showToast('Upload fail — internet/API check karo');
    } finally {
      setAddBusy(false);
    }
  };

  // ---------- Add SA to existing slot ----------
  const submitAddSa = async () => {
    if (modal?.kind !== 'add-sa' || saBusy) return;
    const target = modal.slot;
    let parsed: { client_email?: unknown; private_key?: unknown };
    try { parsed = JSON.parse(saPasted); } catch { showToast('Valid service-account.json nahi hai'); return; }
    if (typeof parsed.client_email !== 'string' || typeof parsed.private_key !== 'string') {
      showToast('Ye service-account.json nahi hai — Firebase console → Service accounts se download karo');
      return;
    }
    setSaBusy(true);
    try {
      await ensureDevSession(API_BASE);
      const r = await fetch(`${API_BASE}/api/panel/slots/add-sa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ id: target.id, serviceAccount: parsed }),
      });
      const data = await r.json().catch(() => ({})) as Record<string, unknown>;
      if (!r.ok) { showToast(`SA add fail: ${String(data.error ?? r.status)}`); return; }
      showToast('Wake key added ✓ — ping ab soye device ko bhi jagayega');
      closeModal(); setSaPasted('');
      void loadSlots();
    } catch {
      showToast('SA add fail — internet/API check karo');
    } finally {
      setSaBusy(false);
    }
  };

  // ---------- Rename slot ----------
  const submitRename = async () => {
    if (modal?.kind !== 'edit' || editBusy || !editLabel.trim()) return;
    const target = modal.slot;
    setEditBusy(true);
    try {
      await ensureDevSession(API_BASE);
      const r = await fetch(`${API_BASE}/api/panel/slots/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ id: target.id, label: editLabel.trim() }),
      });
      const data = await r.json().catch(() => ({})) as Record<string, unknown>;
      if (!r.ok) { showToast(`Rename fail: ${String(data.error ?? r.status)}`); return; }
      showToast('Name updated ✓');
      closeModal(); setEditLabel('');
      void loadSlots();
    } catch {
      showToast('Rename fail — internet/API check karo');
    } finally {
      setEditBusy(false);
    }
  };

  // ---------- Delete slot ----------
  const askRemove = async (slot: SlotView) => {
    setDelError(null);
    const r = await requestActionOtp();
    if (r.status === 'cooldown') { showToast(`${r.retryAfterSec ?? 60}s baad try karo`); return; }
    if (r.status === 'fail') { showToast('OTP bhej nahi paya — internet check karo'); return; }
    setDelSlot(slot);
  };

  const doRemove = async (slot: SlotView, otp: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/panel/slots/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ id: slot.id, otp }),
      });
      const data = await r.json().catch(() => ({})) as Record<string, unknown>;
      if (!r.ok) {
        const err = data.error as string | undefined;
        if (err === 'wrong_otp' || err === 'too_many_attempts') { setDelError('Wrong OTP — Telegram wala code daalo'); return; }
        if (err === 'otp_expired' || err === 'otp_required') { setDelError('OTP expired — Cancel karke dobara try karo'); return; }
        setDelSlot(null); showToast('Remove fail — dobara try karo'); return;
      }
      setSlots((prev) => prev.filter((s) => s.id !== slot.id));
      if (activeId === slot.id) { await setActiveSlot(null); setActiveId(null); }
      setDelSlot(null); setDelError(null);
      showToast(`${slot.label} removed ✓`);
    } catch {
      setDelSlot(null);
      showToast('Remove fail — internet/API check karo');
    }
  };

  // ---------- render ----------
  return (
    <ScreenShell>
      <View style={{ flex: 1 }}>
        <GradientHeader style={[styles.header, { paddingTop: insets.top + 10 }]}>
          <Pressable hitSlop={10} onPress={() => router.back()} style={styles.backBtn}>
            <Feather name="arrow-left" size={20} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle}>Firebase</Text>
            <Text style={styles.headerSub}>{loading ? 'Loading…' : `${slots.length} / 10 slots`}</Text>
          </View>
        </GradientHeader>

        <ScrollView contentContainerStyle={styles.body}>

          {/* ── Add Firebase button — matches DrawerRow exactly ── */}
          <Pressable
            style={({ pressed }) => [styles.addBtn, pressed && { opacity: 0.8 }]}
            onPress={() => { resetAddState(); setModal({ kind: 'add' }); }}
            testID="btn-add-firebase"
          >
            <View style={styles.addBtnIconWrap}>
              <Feather name="plus" size={20} color="#94a3b8" />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={styles.addBtnTitle}>Add Firebase</Text>
              <Text style={styles.addBtnSub}>Naya google-services.json slot jodo</Text>
            </View>
          </Pressable>

          {loading && <Text style={styles.hint}>Slots load ho rahe hain…</Text>}

          {!loading && slots.length === 0 && (
            <View style={styles.emptyBox}>
              <Feather name="database" size={32} color={PALETTE.textFaint} />
              <Text style={styles.emptyTitle}>Koi Firebase nahi</Text>
              <Text style={styles.emptyHint}>Upar wale button se pehla Firebase jodo</Text>
            </View>
          )}

          {/* ── Slot list ── */}
          {slots.map((slot) => {
            const isActive = activeId === slot.id;
            return (
              <GradientCard key={slot.id} style={[styles.slotCard, isActive && styles.slotCardActive]}>

                {/* Name row */}
                <View style={styles.slotNameRow}>
                  <Text style={styles.slotName} numberOfLines={1}>{slot.label}</Text>
                  {isActive && (
                    <View style={styles.activeBadge}>
                      <Feather name="check" size={10} color="#0b1c2c" />
                      <Text style={styles.activeBadgeText}>Active</Text>
                    </View>
                  )}
                </View>

                {/* Project + connections */}
                <Text style={styles.slotProject} numberOfLines={1}>{slot.projectId}</Text>
                <View style={styles.slotMeta}>
                  <Feather name="smartphone" size={11} color={PALETTE.textFaint} />
                  <Text style={styles.slotMetaText}>{slot.connections} / {slot.capacity}</Text>
                  <View style={styles.metaDot} />
                  <Feather
                    name={slot.hasServiceAccount ? 'key' : 'alert-circle'}
                    size={11}
                    color={slot.hasServiceAccount ? PALETTE.greenBright : PALETTE.amber}
                  />
                  <Text style={[styles.slotMetaText, { color: slot.hasServiceAccount ? PALETTE.greenBright : PALETTE.amber }]}>
                    {slot.hasServiceAccount ? 'Wake key ✓' : 'No SA'}
                  </Text>
                </View>

                {/* Action row */}
                <View style={styles.actionRow}>
                  {/* Edit */}
                  <Pressable
                    style={styles.actionChip}
                    onPress={() => { setEditLabel(slot.label); setModal({ kind: 'edit', slot }); }}
                    hitSlop={6}
                    testID={`slot-edit-${slot.id}`}
                  >
                    <Feather name="edit-2" size={12} color={PALETTE.primaryBright} />
                    <Text style={styles.actionChipText}>Edit</Text>
                  </Pressable>

                  {/* Add SA — only if missing */}
                  {!slot.hasServiceAccount && (
                    <Pressable
                      style={[styles.actionChip, styles.actionChipAmber]}
                      onPress={() => { setSaPasted(''); setModal({ kind: 'add-sa', slot }); }}
                      hitSlop={6}
                      testID={`slot-addsa-${slot.id}`}
                    >
                      <Feather name="key" size={12} color={PALETTE.amber} />
                      <Text style={[styles.actionChipText, { color: PALETTE.amber }]}>Add SA</Text>
                    </Pressable>
                  )}

                  <View style={{ flex: 1 }} />

                  {/* Delete */}
                  <Pressable
                    style={styles.trashBtn}
                    onPress={() => void askRemove(slot)}
                    hitSlop={10}
                    testID={`slot-del-${slot.id}`}
                  >
                    <Feather name="trash-2" size={14} color={PALETTE.red} />
                  </Pressable>

                  {/* Enter */}
                  <Pressable
                    style={[styles.enterBtn, isActive && styles.enterBtnActive]}
                    onPress={() => void enterSlot(slot)}
                    testID={`slot-enter-${slot.id}`}
                  >
                    <Text style={styles.enterBtnText}>{isActive ? 'Re-enter' : 'Enter'}</Text>
                    <Feather name="arrow-right" size={12} color="#ffffff" />
                  </Pressable>
                </View>

              </GradientCard>
            );
          })}
        </ScrollView>

        {/* ═══════════ ADD FIREBASE MODAL ═══════════ */}
        <Modal
          visible={modal?.kind === 'add'}
          transparent
          animationType="slide"
          onRequestClose={closeModal}
        >
          <Pressable style={styles.backdrop} onPress={closeModal} />
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.sheetWrap}
          >
            <View style={[styles.sheet, { paddingBottom: insets.bottom + 16 }]}>
              <View style={styles.sheetHandle} />
              <View style={styles.sheetHeader}>
                <Text style={styles.sheetTitle}>Add Firebase</Text>
                <Pressable hitSlop={10} onPress={closeModal}>
                  <Feather name="x" size={20} color={PALETTE.textMuted} />
                </Pressable>
              </View>

              {/* Mode toggle */}
              <View style={styles.segWrap}>
                {(['upload', 'paste'] as const).map((m) => (
                  <Pressable
                    key={m}
                    onPress={() => setAddMode(m)}
                    style={[styles.segBtn, addMode === m && styles.segBtnActive]}
                  >
                    <Feather
                      name={m === 'upload' ? 'upload' : 'clipboard'}
                      size={13}
                      color={addMode === m ? '#fff' : PALETTE.textMuted}
                    />
                    <Text style={[styles.segText, addMode === m && styles.segTextActive]}>
                      {m === 'upload' ? 'Upload file' : 'Paste JSON'}
                    </Text>
                  </Pressable>
                ))}
              </View>

              <ScrollView contentContainerStyle={styles.sheetBody} keyboardShouldPersistTaps="handled">
                {addMode === 'upload' ? (
                  <>
                    {/* ── GS JSON section ── */}
                    <View style={styles.uploadSection}>
                      <View style={styles.sectionLabelRow}>
                        <Feather name="file-text" size={13} color={PALETTE.primaryBright} />
                        <Text style={styles.sectionLabel}>google-services.json</Text>
                        <View style={styles.requiredBadge}><Text style={styles.requiredText}>Required</Text></View>
                      </View>
                      {gsFileRaw ? (
                        <Pressable onPress={() => void pickGsFile()} style={styles.chosenBtn}>
                          <Feather name="check-circle" size={14} color="#fff" />
                          <Text style={styles.chosenText} numberOfLines={1}>{gsFileName}</Text>
                          <Text style={styles.chosenChange}>Change</Text>
                        </Pressable>
                      ) : (
                        <Pressable onPress={() => void pickGsFile()} style={styles.uploadPickBtn}>
                          <Feather name="upload" size={14} color={PALETTE.primaryBright} />
                          <Text style={styles.uploadPickText}>Choose file</Text>
                        </Pressable>
                      )}
                    </View>

                    {/* ── SA section ── */}
                    <View style={[styles.uploadSection, !gsFileRaw && { opacity: 0.45 }]}>
                      <View style={styles.sectionLabelRow}>
                        <Feather name="key" size={13} color={PALETTE.amber} />
                        <Text style={styles.sectionLabel}>service-account.json</Text>
                        <View style={[styles.requiredBadge, { backgroundColor: 'rgba(251,191,36,0.12)', borderColor: 'rgba(251,191,36,0.3)' }]}>
                          <Text style={[styles.requiredText, { color: PALETTE.amber }]}>Optional</Text>
                        </View>
                      </View>
                      <Text style={styles.sectionHint}>Soye device ko FCM ping ke liye — baad mein bhi add ho sakta hai.</Text>
                      {saJson ? (
                        <Pressable onPress={() => void pickSaFile()} style={[styles.chosenBtn, { backgroundColor: 'rgba(34,197,94,0.18)', borderColor: 'rgba(34,197,94,0.35)' }]}>
                          <Feather name="check-circle" size={14} color={PALETTE.greenBright} />
                          <Text style={[styles.chosenText, { color: PALETTE.greenBright }]} numberOfLines={1}>{saName}</Text>
                          <Text style={[styles.chosenChange, { color: PALETTE.greenBright }]}>Change</Text>
                        </Pressable>
                      ) : (
                        <Pressable onPress={() => gsFileRaw ? void pickSaFile() : undefined} style={styles.uploadPickBtn}>
                          <Feather name="upload" size={14} color={PALETTE.textMuted} />
                          <Text style={[styles.uploadPickText, { color: PALETTE.textMuted }]}>Choose file</Text>
                        </Pressable>
                      )}
                    </View>

                    <GradientButton
                      label={addBusy ? 'Uploading…' : 'Upload'}
                      onPress={() => gsFileRaw ? void submitAdd(gsFileRaw) : showToast('Pehle google-services.json choose karo')}
                      style={{ marginTop: 4 }}
                    />
                  </>
                ) : (
                  <>
                    <Text style={styles.sheetHint}>
                      Firebase console se download ki hui <Text style={{ color: PALETTE.textSoft }}>google-services.json</Text> ka poora content paste karo:
                    </Text>
                    <TextInput
                      value={addPasted}
                      onChangeText={setAddPasted}
                      placeholder={'{"project_info": {...}}'}
                      placeholderTextColor={PALETTE.textFaint}
                      multiline
                      style={styles.textArea}
                      testID="input-add-paste"
                    />
                    <GradientButton
                      label={addBusy ? 'Uploading…' : 'Upload'}
                      onPress={() => void submitAdd(addPasted)}
                      style={{ marginTop: 12 }}
                    />
                  </>
                )}
              </ScrollView>
            </View>
          </KeyboardAvoidingView>
        </Modal>

        {/* ═══════════ ADD SA MODAL ═══════════ */}
        <Modal
          visible={modal?.kind === 'add-sa'}
          transparent
          animationType="slide"
          onRequestClose={closeModal}
        >
          <Pressable style={styles.backdrop} onPress={closeModal} />
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.sheetWrap}
          >
            <View style={[styles.sheet, { paddingBottom: insets.bottom + 16 }]}>
              <View style={styles.sheetHandle} />
              <View style={styles.sheetHeader}>
                <View>
                  <Text style={styles.sheetTitle}>Add Wake Key</Text>
                  {modal?.kind === 'add-sa' && (
                    <Text style={styles.sheetSub}>{modal.slot.label}</Text>
                  )}
                </View>
                <Pressable hitSlop={10} onPress={closeModal}>
                  <Feather name="x" size={20} color={PALETTE.textMuted} />
                </Pressable>
              </View>
              <View style={styles.sheetBody}>
                <Text style={styles.sheetHint}>
                  Firebase console → Project settings → Service accounts → Generate new private key.{'\n'}
                  Poora JSON yahan paste karo.
                </Text>
                <TextInput
                  value={saPasted}
                  onChangeText={setSaPasted}
                  placeholder={'{"type": "service_account", ...}'}
                  placeholderTextColor={PALETTE.textFaint}
                  multiline
                  style={[styles.textArea, { minHeight: 140 }]}
                  testID="input-sa-paste"
                />
                <GradientButton
                  label={saBusy ? 'Saving…' : '🔑 Add wake key'}
                  onPress={() => void submitAddSa()}
                  style={{ marginTop: 12 }}
                />
              </View>
            </View>
          </KeyboardAvoidingView>
        </Modal>

        {/* ═══════════ EDIT / RENAME MODAL ═══════════ */}
        <Modal
          visible={modal?.kind === 'edit'}
          transparent
          animationType="slide"
          onRequestClose={closeModal}
        >
          <Pressable style={styles.backdrop} onPress={closeModal} />
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.sheetWrap}
          >
            <View style={[styles.sheet, { paddingBottom: insets.bottom + 16 }]}>
              <View style={styles.sheetHandle} />
              <View style={styles.sheetHeader}>
                <Text style={styles.sheetTitle}>Rename Firebase</Text>
                <Pressable hitSlop={10} onPress={closeModal}>
                  <Feather name="x" size={20} color={PALETTE.textMuted} />
                </Pressable>
              </View>
              <View style={styles.sheetBody}>
                <TextInput
                  value={editLabel}
                  onChangeText={setEditLabel}
                  placeholder="Firebase name…"
                  placeholderTextColor={PALETTE.textFaint}
                  style={styles.singleInput}
                  autoFocus
                  maxLength={40}
                  returnKeyType="done"
                  onSubmitEditing={() => void submitRename()}
                  testID="input-rename"
                />
                <GradientButton
                  label={editBusy ? 'Saving…' : 'Save name'}
                  onPress={() => void submitRename()}
                  style={{ marginTop: 12 }}
                />
              </View>
            </View>
          </KeyboardAvoidingView>
        </Modal>

        <OtpConfirmDialog
          visible={delSlot !== null}
          onClose={() => { setDelSlot(null); setDelError(null); }}
          actionLabel="Remove"
          error={delError}
          onConfirm={(code) => { if (delSlot) void doRemove(delSlot, code); }}
          onResend={() => { if (delSlot) void askRemove(delSlot); }}
        />
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

  // Add Firebase top button — exact DrawerRow replica
  addBtn: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: PALETTE.card, borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 12, padding: 14, marginBottom: 20,
  },
  addBtnIconWrap: { width: 36, alignItems: 'center', justifyContent: 'center' },
  addBtnTitle: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  addBtnSub: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 2 },

  hint: { color: PALETTE.textMuted, fontSize: 12, marginTop: 8 },

  emptyBox: { alignItems: 'center', paddingVertical: 48, gap: 8 },
  emptyTitle: { color: PALETTE.textSoft, fontSize: 16, fontFamily: 'Inter_700Bold', marginTop: 8 },
  emptyHint: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_400Regular' },

  // Slot card
  slotCard: { padding: 14, marginBottom: 12 },
  slotCardActive: { borderColor: PALETTE.greenBright, borderWidth: 1.5 },

  slotNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  slotName: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold', flex: 1 },
  activeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: PALETTE.greenBright, borderRadius: 8,
    paddingHorizontal: 7, paddingVertical: 3,
  },
  activeBadgeText: { color: '#0b1c2c', fontSize: 10, fontFamily: 'Inter_700Bold' },

  slotProject: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular', marginBottom: 6 },
  slotMeta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 12 },
  slotMetaText: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular' },
  metaDot: { width: 3, height: 3, borderRadius: 1.5, backgroundColor: PALETTE.textFaint },

  actionRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },

  actionChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(82,169,255,0.1)',
    borderWidth: 1, borderColor: 'rgba(82,169,255,0.25)',
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6,
  },
  actionChipAmber: {
    backgroundColor: 'rgba(251,191,36,0.08)',
    borderColor: 'rgba(251,191,36,0.25)',
  },
  actionChipText: { color: PALETTE.primaryBright, fontSize: 12, fontFamily: 'Inter_700Bold' },

  trashBtn: {
    padding: 7, borderRadius: 8,
    backgroundColor: 'rgba(207,102,121,0.1)',
    borderWidth: 1, borderColor: 'rgba(207,102,121,0.2)',
  },
  enterBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: PALETTE.primary,
    borderRadius: 8, paddingHorizontal: 12, paddingVertical: 7,
  },
  enterBtnActive: { backgroundColor: PALETTE.green },
  enterBtnText: { color: '#ffffff', fontSize: 12, fontFamily: 'Inter_700Bold' },

  // Modal bottom sheet
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)' },
  sheetWrap: { justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: PALETTE.bg,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderTopWidth: 1, borderColor: PALETTE.borderSoft,
  },
  sheetHandle: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: PALETTE.borderSoft,
    alignSelf: 'center', marginTop: 10, marginBottom: 4,
  },
  sheetHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 14,
    borderBottomWidth: 1, borderBottomColor: PALETTE.borderSoft,
  },
  sheetTitle: { color: PALETTE.text, fontSize: 16, fontFamily: 'Inter_700Bold' },
  sheetSub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2 },
  sheetBody: { padding: 16 },
  sheetHint: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18, marginBottom: 8 },

  // Segment toggle (Upload / Paste)
  segWrap: {
    flexDirection: 'row', gap: 6,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12, padding: 4, margin: 16, marginBottom: 0,
    borderWidth: 1, borderColor: PALETTE.borderSoft,
  },
  segBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 9, borderRadius: 9,
  },
  segBtnActive: { backgroundColor: PALETTE.sky },
  segText: { color: PALETTE.textMuted, fontSize: 13, fontFamily: 'Inter_700Bold' },
  segTextActive: { color: '#ffffff' },

  // Upload tab — section cards
  uploadSection: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: PALETTE.borderSoft,
    borderRadius: 12, padding: 14, marginBottom: 12,
  },
  sectionLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 8 },
  sectionLabel: { flex: 1, color: PALETTE.textSoft, fontSize: 13, fontFamily: 'Inter_700Bold' },
  sectionHint: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', lineHeight: 16, marginBottom: 8 },
  requiredBadge: {
    backgroundColor: 'rgba(82,169,255,0.12)', borderWidth: 1, borderColor: 'rgba(82,169,255,0.3)',
    borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2,
  },
  requiredText: { color: PALETTE.primaryBright, fontSize: 10, fontFamily: 'Inter_700Bold' },
  uploadPickBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 10,
    paddingVertical: 11, borderStyle: 'dashed',
  },
  uploadPickText: { color: PALETTE.primaryBright, fontSize: 13, fontFamily: 'Inter_700Bold' },

  // File chosen state
  chosenBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: 'rgba(82,169,255,0.12)',
    borderWidth: 1, borderColor: 'rgba(82,169,255,0.3)',
    borderRadius: 10, paddingVertical: 10, paddingHorizontal: 12,
  },
  chosenText: { flex: 1, color: '#ffffff', fontSize: 13, fontFamily: 'Inter_700Bold' },
  chosenChange: { color: PALETTE.primaryBright, fontSize: 11, fontFamily: 'Inter_700Bold' },

  // Text inputs
  textArea: {
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10,
    color: '#ffffff', fontSize: 12, fontFamily: 'Inter_400Regular',
    marginTop: 8, minHeight: 180, textAlignVertical: 'top',
  },
  singleInput: {
    borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 13,
    color: '#ffffff', fontSize: 15, fontFamily: 'Inter_400Regular',
  },
});
