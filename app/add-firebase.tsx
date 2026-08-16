import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { ScreenShell } from '@/components/panel/ScreenShell';
import { GradientButton, GradientCard, GradientHeader, useToast } from '@/components/panel/ui';
import { ensureDevSession, panelAuthHeaders } from '@/lib/panelSession';
import { setActiveSlot } from '@/lib/activeSlot';
import { PALETTE } from '@/constants/theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_BASE } from '@/lib/apiBase';

// Cross-platform file read (user bug 2026-08-15): WEB preview pe legacy
// FileSystem.readAsStringAsync blob: URI padh nahi pata ("file padh nahi paya"
// toast ka root cause) — web pe picker asset.file (browser File) deta hai,
// usse .text() se padho. Native (APK) pe FileSystem theek kaam karta hai.
const readAssetText = async (asset: { uri: string; file?: { text: () => Promise<string> } }): Promise<string> => {
  if (asset.file && typeof asset.file.text === 'function') return asset.file.text();
  return FileSystem.readAsStringAsync(asset.uri);
};

// Add Firebase — dedicated page (owner rule 2026-08-13): sirf google-services.json
// file upload YA paste. Bot ab build pe panel auto-link nahi karta — naya slot
// hamesha yahin se manually aata hai.
export default function AddFirebaseScreen() {
  const [toast, showToast] = useToast();
  const [pasted, setPasted] = useState('');
  const [busy, setBusy] = useState(false);
  // Owner ask (2026-08-15): Upload YA Paste — ek waqt me sirf EK tareeka dikhe.
  // Upload choose → file picker wala section; Paste choose → textarea wala.
  const [mode, setMode] = useState<'upload' | 'paste'>('upload');
  const insets = useSafeAreaInsets();
  // FCM wake-key (optional) — service-account.json; iske bina ping sirf zinda
  // device pe kaam karta hai, iske saath soya device bhi jaagta hai.
  const [saJson, setSaJson] = useState<unknown>(null);
  const [saName, setSaName] = useState('');
  // Owner ask (2026-08-15): Firebase add hone pe page PE HI "connected successfully"
  // prompt dikhe — seedha /main pe jump nahi. User khud decide kare aage kya kare.
  const [success, setSuccess] = useState<{ title: string; detail?: string } | null>(null);
  // Owner rule (2026-08-15): service-account.json SIRF tab lagta hai jab
  // google-services.json pehle upload ho chuka ho. Isliye last uploaded GS raw
  // yaad rakhte hain — SA choose karte hi usi slot pe wake-key auto-update.
  const [lastGsRaw, setLastGsRaw] = useState<string | null>(null);
  // Owner ask (2026-08-15): PASTE flow me GS upload ke baad SA JSON bhi text
  // me poocha jaye (file flow me file picker already hai) — OPTIONAL, isliye
  // Skip button ke saath.
  // saPromptFor = us GS ka raw jiske upload ke baad SA prompt khula — prompt
  // isi slot se bound rahega (beech me naya GS upload ho to bhi retarget nahi).
  const [saPromptFor, setSaPromptFor] = useState<string | null>(null);
  const [saPasted, setSaPasted] = useState('');
  // Owner ask (2026-08-15): upload mode 2-step — file choose hote hi AUTO-UPLOAD
  // nahi; pehle green "✓ selected" state dikhti hai, phir card ke SABSE NEECHE
  // wale Upload button se submit hota hai.
  const [gsFileRaw, setGsFileRaw] = useState<string | null>(null);
  const [gsFileName, setGsFileName] = useState('');

  // Returns true sirf confirmed success pe — callers isi pe UI state band karein
  // (code-review: SA prompt fail pe open rakhna hai taaki retry ho sake).
  const upload = async (raw: string, saOverride?: unknown, askSaAfter = false): Promise<boolean> => {
    if (busy) return false;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      showToast('Valid google-services.json nahi hai — poora JSON dobara copy karo');
      return false;
    }
    const sa = saOverride !== undefined ? saOverride : saJson;
    setBusy(true);
    try {
      // Dev preview (bypass login) me token missing ho sakta hai — upload se pehle
      // dev-session ensure karo; production me token already hota hai (no-op).
      await ensureDevSession(API_BASE);
      const r = await fetch(`${API_BASE}/api/panel/slots/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...panelAuthHeaders() },
        body: JSON.stringify({ json: parsed, ...(sa ? { serviceAccount: sa } : {}) }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        showToast(
          data?.error === 'duplicate_firebase_url'
            ? 'Ye Firebase pehle se ek slot me added hai'
            : data?.error === 'max_slots_reached'
              ? 'Slots full (10/10) — pehle koi purana slot delete karo'
              : `Upload fail: ${data?.error ?? r.status}`,
        );
        return false;
      }
      // Owner rule (2026-08-13): naya Firebase add hote hi usi pe AUTO-SWITCH —
      // user ko Switch Firebase page pe jaake manually select nahi karna padta.
      const s = data.slot;
      if (!s?.id) {
        showToast('Upload ka response ajeeb aaya — Slots page refresh karke check karo');
        return false;
      }
      await setActiveSlot({ id: s.id, label: s.label, projectId: s.projectId, databaseUrl: s.databaseUrl });
      setLastGsRaw(raw); // GS uploaded — ab service-account unlock
      // Page pe hi success prompt — navigate mat karo, user khud decide kare.
      setSuccess(
        data.updated === 'service_account'
          ? { title: 'Wake key connected successfully ✓', detail: `${s.label ?? 'Slot'} — ab ping soye device ko bhi jagayega` }
          : { title: 'Firebase connected successfully ✓', detail: `${s.label ?? 'Slot'} added — panel ab isi Firebase pe switch ho gaya` },
      );
      setPasted('');
      setSaJson(null);
      setSaName('');
      // Paste flow: GS upload ke baad SA text prompt dikhao (optional — skip allowed).
      // File flow me SA file button already card me hai, prompt ki zaroorat nahi.
      if (askSaAfter) { setSaPasted(''); setSaPromptFor(raw); }
      return true;
    } catch {
      showToast('Upload fail ho gaya — internet/API check karo');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const pickFile = async () => {
    if (busy) return;
    // SA prompt pending — naya GS upload prompt ko retarget/confuse karega
    // (code-review FAIL fix): pehle SA step poora/skip karwana zaroori.
    if (saPromptFor !== null) {
      showToast('Pehle neeche service-account wala step poora karo ya Skip dabao');
      return;
    }
    try {
      const res = await DocumentPicker.getDocumentAsync({ type: 'application/json', copyToCacheDirectory: true });
      if (res.canceled || !res.assets?.[0]) return;
      const content = await readAssetText(res.assets[0]);
      JSON.parse(content); // invalid JSON ko green state tak pahunchne hi mat do
      // STAGE karo (upload NAHI) — green ✓ dikhega, submit neeche wale
      // Upload button se hoga (owner 2-step rule).
      setGsFileRaw(content);
      setGsFileName(res.assets[0].name ?? 'google-services.json');
    } catch {
      showToast('File padh nahi paya ya valid JSON nahi hai — dobara choose karo');
    }
  };

  // Card ke SABSE NEECHE wala Upload button — staged google-services (+ staged
  // wake-key, agar choose ki ho) submit karta hai. GS nahi par SA staged hai aur
  // is session me GS pehle upload ho chuka hai → usi slot pe wake-key update.
  const submitStaged = async () => {
    if (busy) return;
    if (saPromptFor !== null) {
      showToast('Pehle neeche service-account wala step poora karo ya Skip dabao');
      return;
    }
    if (gsFileRaw) {
      const ok = await upload(gsFileRaw, saJson ?? undefined);
      if (ok) { setGsFileRaw(null); setGsFileName(''); }
      return;
    }
    if (lastGsRaw && saJson) {
      await upload(lastGsRaw, saJson); // same slot pe wake-key update
      return;
    }
    showToast('Pehle google-services.json choose karo — phir Upload dabao');
  };

  // service-account.json choose — GATED (owner rule 2026-08-15): sirf tab
  // chalta hai jab google-services.json is session me upload ho chuka ho.
  // SA choose karte hi last uploaded GS ke saath auto-update bhej dete hain —
  // server same slot pe sirf wake-key update karta hai (updated: service_account).
  const pickSaFile = async () => {
    if (busy) return;
    // Gate: GS is session me upload ho chuka ho (lastGsRaw) YA abhi staged ho
    if (!lastGsRaw && !gsFileRaw) {
      showToast('Pehle google-services.json choose/upload karo — service-account baad me lagega');
      return;
    }
    try {
      const res = await DocumentPicker.getDocumentAsync({ type: 'application/json', copyToCacheDirectory: true });
      if (res.canceled || !res.assets?.[0]) return;
      const content = await readAssetText(res.assets[0]);
      const parsed = JSON.parse(content) as { client_email?: unknown; private_key?: unknown };
      if (typeof parsed?.client_email !== 'string' || typeof parsed?.private_key !== 'string') {
        showToast('Ye service-account.json nahi hai — Firebase console → Service accounts se download karo');
        return;
      }
      // STAGE karo (auto-upload NAHI) — green ✓ dikhega, submit neeche wale
      // Upload button se hoga (GS ke saath ya us slot pe wake-key update).
      setSaJson(parsed);
      setSaName(res.assets[0].name ?? 'service-account.json');
    } catch {
      showToast('File padh nahi paya — valid service-account.json choose karo');
    }
  };

  // Paste flow ka SA submit — pasted TEXT ko validate karke same slot pe
  // wake-key update bhejo. Skip = optional hai, prompt band.
  const submitSaPasted = async () => {
    if (busy || !saPromptFor) return;
    let parsed: { client_email?: unknown; private_key?: unknown };
    try {
      parsed = JSON.parse(saPasted);
    } catch {
      showToast('Valid service-account.json nahi hai — poora JSON dobara paste karo');
      return;
    }
    if (typeof parsed?.client_email !== 'string' || typeof parsed?.private_key !== 'string') {
      showToast('Ye service-account.json nahi hai — Firebase console → Service accounts se download karo');
      return;
    }
    // Prompt SIRF confirmed success pe band — fail pe card + pasted key wapas
    // dikhti rahegi taaki user fix karke retry kar sake (code-review FAIL fix).
    const ok = await upload(saPromptFor, parsed);
    if (ok) { setSaPromptFor(null); setSaPasted(''); }
  };

  return (
    <ScreenShell>
      <View style={{ flex: 1 }}>
        {/* paddingTop = safe-area inset — warna header phone ke notch/status bar
            ke peeche clip hota tha (title "Add Fireba..." kat ke dikhta tha) */}
        <GradientHeader style={{ ...styles.header, paddingTop: insets.top + 10 }}>
          <Pressable hitSlop={10} onPress={() => router.back()} testID="addfb-back" style={styles.backBtn}>
            <Feather name="arrow-left" size={20} color="#ffffff" />
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={styles.headerTitle} numberOfLines={1}>Add Firebase</Text>
            <Text style={styles.headerSub} numberOfLines={1}>google-services.json upload ya paste karo</Text>
          </View>
        </GradientHeader>

        <ScrollView contentContainerStyle={styles.body}>
          {/* Mode toggle — Upload ya Paste, dono ek saath NAHI dikhte */}
          <View style={styles.segWrap} testID="addfb-mode-toggle">
            <Pressable
              onPress={() => setMode('upload')}
              testID="btn-mode-upload"
              style={[styles.segBtn, mode === 'upload' && styles.segBtnActive]}
            >
              <Feather name="upload" size={14} color={mode === 'upload' ? '#ffffff' : PALETTE.textMuted} />
              <Text style={[styles.segText, mode === 'upload' && styles.segTextActive]}>Upload file</Text>
            </Pressable>
            <Pressable
              onPress={() => setMode('paste')}
              testID="btn-mode-paste"
              style={[styles.segBtn, mode === 'paste' && styles.segBtnActive]}
            >
              <Feather name="clipboard" size={14} color={mode === 'paste' ? '#ffffff' : PALETTE.textMuted} />
              <Text style={[styles.segText, mode === 'paste' && styles.segTextActive]}>Paste JSON</Text>
            </Pressable>
          </View>

          {mode === 'upload' && (
          <GradientCard style={styles.card}>
            <Text style={styles.sectionLabel}>JSON file se</Text>
            <Text style={styles.hint}>
              Firebase console se download ki hui google-services.json choose karo — select hote hi green ✓ dikhega, phir sabse neeche Upload dabao.
            </Text>
            {gsFileRaw ? (
              <Pressable
                onPress={() => void pickFile()}
                testID="btn-pick-json"
                style={({ pressed }) => [styles.chosenBtn, { marginTop: 12 }, pressed && { opacity: 0.85 }]}
              >
                <Feather name="check-circle" size={15} color="#ffffff" />
                <Text style={styles.chosenText} numberOfLines={1}>{gsFileName} — ready</Text>
              </Pressable>
            ) : (
              <GradientButton
                label={busy ? 'Uploading…' : '📄 Choose google-services.json'}
                onPress={() => void pickFile()}
                testID="btn-pick-json"
                style={{ marginTop: 12 }}
              />
            )}
            <Text style={styles.hint}>
              Ping se SOYE device ko jagane ke liye (optional): Firebase console → Project settings → Service accounts → Generate new private key.
              {(lastGsRaw || gsFileRaw) ? '' : ' Pehle google-services.json choose karo — tabhi ye khulega.'}
            </Text>
            <View style={!lastGsRaw && !gsFileRaw && styles.locked}>
              {saJson && saName ? (
                <Pressable
                  onPress={() => void pickSaFile()}
                  testID="btn-pick-sa"
                  style={({ pressed }) => [styles.chosenBtn, { marginTop: 8 }, pressed && { opacity: 0.85 }]}
                >
                  <Feather name="check-circle" size={15} color="#ffffff" />
                  <Text style={styles.chosenText} numberOfLines={1}>{saName} — ready</Text>
                </Pressable>
              ) : (
                <GradientButton
                  label={(lastGsRaw || gsFileRaw) ? '🔑 service-account.json (optional — ping wake)' : '🔒 service-account.json (google-services pehle)'}
                  onPress={() => void pickSaFile()}
                  testID="btn-pick-sa"
                  style={{ marginTop: 8 }}
                />
              )}
            </View>
            <GradientButton
              label={busy ? 'Uploading…' : '⬆️ Upload'}
              onPress={() => void submitStaged()}
              testID="btn-upload-staged"
              style={{ marginTop: 14 }}
            />
          </GradientCard>
          )}

          {mode === 'paste' && (
          <GradientCard style={styles.card}>
            <Text style={styles.sectionLabel}>Paste JSON</Text>
            <TextInput
              value={pasted}
              onChangeText={setPasted}
              placeholder='{"project_info": {...}} — poora google-services.json yahan paste karo'
              placeholderTextColor={PALETTE.textFaint}
              multiline
              style={[styles.input, styles.pasteArea]}
              testID="input-paste-json"
            />
            <GradientButton
              label={busy ? 'Uploading…' : 'Upload pasted JSON'}
              onPress={() => {
                // SA prompt pending — naya GS upload pending prompt + typed key
                // ko silently replace kar deta tha (code-review FAIL fix).
                if (saPromptFor !== null) {
                  showToast('Pehle neeche service-account wala step poora karo ya Skip dabao');
                  return;
                }
                void upload(pasted, undefined, true);
              }}
              testID="btn-upload-pasted"
              style={{ marginTop: 10 }}
            />
          </GradientCard>
          )}

          {/* Paste flow SA prompt — GS upload ke BAAD dikhta hai (optional) */}
          {saPromptFor !== null && (
            <GradientCard style={styles.card}>
              <Text style={styles.sectionLabel}>Service account JSON (optional)</Text>
              <Text style={styles.hint}>
                Ping se soye device ko jagane ke liye — Firebase console → Project settings → Service accounts → Generate new private key. Poora JSON yahan paste karo, ya Skip kar do.
              </Text>
              <TextInput
                value={saPasted}
                onChangeText={setSaPasted}
                placeholder='{"type": "service_account", ...} — poora service-account.json yahan paste karo'
                placeholderTextColor={PALETTE.textFaint}
                multiline
                style={[styles.input, styles.pasteArea]}
                testID="input-paste-sa"
              />
              <GradientButton
                label={busy ? 'Uploading…' : '🔑 Upload wake key'}
                onPress={() => void submitSaPasted()}
                testID="btn-upload-sa-pasted"
                style={{ marginTop: 10 }}
              />
              <Pressable
                onPress={() => { setSaPromptFor(null); setSaPasted(''); }}
                testID="btn-skip-sa"
                hitSlop={8}
                style={{ marginTop: 12, alignSelf: 'center' }}
              >
                <Text style={styles.skipText}>Skip — baad me laga lunga</Text>
              </Pressable>
            </GradientCard>
          )}

          <Text style={styles.note}>
            Max 10 slots · duplicate Firebase URL blocked hota hai. Naye devices sabse naye slot pe connect hote hain.
          </Text>
        </ScrollView>

        {/* Success OVERLAY (owner ask 2026-08-15): page ko replace mat karo —
            form ke UPAR translucent backdrop + centered panel. Backdrop ka bg
            transparent rakha hai taaki neeche ka page dikhta rahe (black void
            nahi). User tab tak yahin rakhta hai jab tak khud "Open devices" ya
            "Add another" na dabaye */}
        {success && (
          <View style={styles.successOverlay} testID="addfb-success">
            <GradientCard style={styles.successPanel}>
              <View style={styles.successIconBig}>
                <Feather name="check" size={34} color="#ffffff" />
              </View>
              <Text style={styles.successTitleBig}>{success.title}</Text>
              {success.detail ? <Text style={[styles.successDetail, { fontSize: 14, marginTop: 10 }]}>{success.detail}</Text> : null}
              <GradientButton
                label="Open devices →"
                onPress={() => router.replace('/main')}
                testID="btn-success-open-devices"
                style={{ marginTop: 28, alignSelf: 'stretch' }}
              />
              {/* Add another — NAYA slot flow: lastGsRaw bhi clear, warna SA
                  purane slot pe lag jaata (code-review edge case) */}
              <Pressable onPress={() => { setSuccess(null); setLastGsRaw(null); setSaJson(null); setSaName(''); setSaPromptFor(null); setSaPasted(''); setGsFileRaw(null); setGsFileName(''); }} testID="btn-success-add-another" hitSlop={8} style={{ marginTop: 16 }}>
                <Text style={styles.addAnother}>Add another Firebase</Text>
              </Pressable>
            </GradientCard>
          </View>
        )}
        {toast}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 14 },
  backBtn: { padding: 4 },
  headerTitle: { color: '#ffffff', fontSize: 18, fontWeight: '700' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  body: { padding: 16 },
  // Mode toggle (Upload / Paste) — segmented control
  segWrap: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    borderRadius: 12,
    padding: 4,
    marginBottom: 12,
    gap: 6,
  },
  segBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 9,
  },
  segBtnActive: { backgroundColor: PALETTE.sky },
  segText: { color: PALETTE.textMuted, fontSize: 13, fontWeight: '700' },
  segTextActive: { color: '#ffffff' },
  card: { padding: 14, marginBottom: 12 },
  sectionLabel: { color: PALETTE.textFaint, fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  hint: { color: PALETTE.textFaint, fontSize: 12, lineHeight: 18, marginTop: 8 },
  // SA button locked state — google-services upload se pehle dim
  locked: { opacity: 0.45 },
  // File choose hone ke baad GREEN selected state (owner ask 2026-08-15)
  chosenBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    backgroundColor: PALETTE.green,
    borderRadius: 14,
    paddingVertical: 13,
    paddingHorizontal: 14,
  },
  chosenText: { color: '#ffffff', fontSize: 14, fontWeight: '700', flexShrink: 1 },
  input: {
    borderWidth: 1,
    borderColor: PALETTE.borderSoft,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#ffffff',
    fontSize: 13,
    marginTop: 10,
  },
  pasteArea: { minHeight: 280, textAlignVertical: 'top' },
  note: { color: PALETTE.textFaint, fontSize: 12, lineHeight: 18, textAlign: 'center', marginTop: 4 },
  // Success overlay (owner ask 2026-08-15) — page replace nahi hota; form ke upar
  // TRANSLUCENT backdrop (neeche ka page halka dikhta rahe, black void nahi) +
  // center me app ka normal GradientCard panel
  successOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(7, 11, 17, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  successPanel: {
    width: '100%',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 32,
    borderColor: PALETTE.green,
  },
  successIconBig: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: PALETTE.green,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
    // halki green ring — panel ke green border ke saath match
    borderWidth: 6,
    borderColor: PALETTE.greenBg,
  },
  successTitleBig: { color: PALETTE.textSoft, fontSize: 22, fontWeight: '800', textAlign: 'center' },
  successDetail: { color: PALETTE.textMuted, fontSize: 12.5, lineHeight: 18, textAlign: 'center', marginTop: 6 },
  addAnother: { color: PALETTE.sky, fontSize: 13, fontWeight: '600' },
  skipText: { color: PALETTE.textMuted, fontSize: 13, fontWeight: '600' },
});
