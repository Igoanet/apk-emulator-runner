import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { PanelModal } from '@/components/panel/ui';
import { PALETTE } from '@/constants/theme';

// ── V7 "Financial Dashboard" (GianPanel V7.O dialog_financial_report.xml +
// item_fin_bank_row.xml) ka dark-theme port. Structure exact wahi:
// hero card (TOTAL BANK BALANCE + ↓Debit/↑Credit pills + CREDIT AVAILABLE /
// CREDIT OUTSTANDING stats) → "Connected Banks" card (N Banks chip) →
// expandable bank rows (icon badge, name, "• A/c **0000", balance pill;
// tap → Total Debit / Total Credit / SMS Count + Parsed Bank SMS History) →
// summary + disclaimer.

export interface BankRow {
  name: string;
  accHint: string;      // e.g. "**2679"
  count: number;        // SMS count
  debit: number;
  credit: number;
  balance: number;      // latest available balance hint
  creditAvail: number;  // credit card available limit (0 = n/a)
  creditOut: number;    // credit card outstanding (0 = n/a)
  messages: string[];
}

// Fake preview data (DEV_PREVIEW) — numbers ab numeric hain taaki hero totals
// sach me compute hon, hardcoded string nahi.
const BANKS: BankRow[] = [
  {
    name: 'Axis Bank', accHint: '**2679', count: 18, debit: 533, credit: 0, balance: 926.48, creditAvail: 0, creditOut: 0,
    messages: [
      'Rs.1.00 Dr. from A/C XXXXXX2679 and Cr. to gauridmore02@okaxis. Ref:032294747829. AvlBal:Rs2455.00(2025-09-01 04:43:21). Not you? Call 18005700/5000-BOB',
      'Rs.10.00 Dr. from A/C XXXXXX2679 and Cr. to 9767286760@okbizaxis. Ref:524473405639. AvlBal:Rs2385.00(2025-09-01 04:55:12). Not you? Call 18005700/5000-BOB',
      'Rs.30.00 Dr. from A/C XXXXXX2679 and Cr. to gpay-11240310104@okbizaxis. Ref:758991315214. AvlBal:Rs3755.00(2025-09-04 06:43:42). Not you? Call 18005700/5000-BOB',
      'Rs.10.00 Dr. from A/C XXXXXX2679 and Cr. to gpay-1124607355@okbizaxis. Ref:172915050455. AvlBal:Rs2713.00(2025-09-14 03:46:22). Not you? Call 18005700/5000-BOB',
    ],
  },
  { name: 'Bank of Baroda', accHint: '**2679', count: 42, debit: 4120, credit: 6300, balance: 2455.00, creditAvail: 0, creditOut: 0, messages: ['Your request for deseeding of Aadhaar from your A/C XXX2679 is successful. If not initiated by you, call 18005700 - BOB'] },
  { name: 'Bank of Maharashtra', accHint: '**1190', count: 9, debit: 250, credit: 1000, balance: 1150, creditAvail: 0, creditOut: 0, messages: ['Rs.250 debited from A/C XX1190 on 28-07-2026. Avl bal Rs.1,150.'] },
  { name: 'HDFC Bank', accHint: '**4521', count: 61, debit: 8450, credit: 18240, balance: 18240, creditAvail: 52000, creditOut: 12650, messages: ['Rs.5000 credited to a/c XX4521 on 28-JUL. Avl bal Rs.18,240.'] },
  { name: 'ICICI Bank', accHint: '**901', count: 33, debit: 3368.99, credit: 12727.50, balance: 9358.51, creditAvail: 0, creditOut: 0, messages: ['ICICI Bank Acct XX901 debited with Rs.1,299.00 on 28-Jul-26.'] },
  { name: 'State Bank of India', accHint: '**7741', count: 58, debit: 1299, credit: 16000, balance: 14701, creditAvail: 0, creditOut: 0, messages: ['Your OTP for txn of Rs.12,000 is 448190. Valid 10 min. Do not share.'] },
];

// Indian grouping + 2 decimals jab fraction ho (V7 "₹0.00" format)
const inr = (n: number) => {
  const hasPaise = Math.round(n * 100) % 100 !== 0;
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: hasPaise ? 2 : 0, maximumFractionDigits: 2 })}`;
};
const inr2 = (n: number) => `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function FinancialReportDialog({ visible, onClose, label, phone }: { visible: boolean; onClose: () => void; label: string; phone: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  // Hero totals — V7 jaise: total balance = banks ke latest balance ka sum;
  // debit/credit chips = sab banks ke totals; credit avail/outstanding alag.
  const agg = useMemo(() => ({
    totalBal: BANKS.reduce((a, b) => a + b.balance, 0),
    totalDebit: BANKS.reduce((a, b) => a + b.debit, 0),
    totalCredit: BANKS.reduce((a, b) => a + b.credit, 0),
    creditAvail: BANKS.reduce((a, b) => a + b.creditAvail, 0),
    creditOut: BANKS.reduce((a, b) => a + b.creditOut, 0),
    sms: BANKS.reduce((a, b) => a + b.count, 0),
  }), []);

  const summary = `${BANKS.length} banks · ${agg.sms} SMS parsed\nBanks: ${BANKS.map((b) => b.name).join(', ')}\nTotal debit ${inr(agg.totalDebit)} · Total credit ${inr(agg.totalCredit)}`;

  return (
    <PanelModal visible={visible} onClose={onClose}>
      {/* Header — V7: "Financial Dashboard" + device chip */}
      <Text style={s.title}>Financial Dashboard</Text>
      <Text style={s.sub}>{`Device  ${label || phone}${label ? ' ✅' : ''}`}</Text>

      <ScrollView style={{ maxHeight: 420 }} showsVerticalScrollIndicator={false}>
        {/* ── HERO card (bg_fin_hero — teal gradient) ── */}
        <LinearGradient colors={['#0f766e', '#115e59', '#134e4a']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.hero}>
          <Text style={s.heroLabel}>TOTAL BANK BALANCE</Text>
          <Text style={s.heroTotal}>{inr2(agg.totalBal)}</Text>
          <View style={s.heroChips}>
            <View style={s.heroPill}><Text style={[s.heroPillText, { color: '#f87171' }]}>{`↓ Debit ${inr(agg.totalDebit)}`}</Text></View>
            <View style={s.heroPill}><Text style={[s.heroPillText, { color: '#34d399' }]}>{`↑ Credit ${inr(agg.totalCredit)}`}</Text></View>
          </View>
          <View style={s.heroDivider} />
          <View style={s.heroStats}>
            <View style={s.heroStat}>
              <Text style={s.heroStatLabel}>CREDIT AVAILABLE</Text>
              <Text style={s.heroStatVal}>{inr2(agg.creditAvail)}</Text>
            </View>
            <View style={s.heroVDivider} />
            <View style={s.heroStat}>
              <Text style={s.heroStatLabel}>CREDIT OUTSTANDING</Text>
              <Text style={s.heroStatVal}>{inr2(agg.creditOut)}</Text>
            </View>
          </View>
        </LinearGradient>

        {/* ── Connected Banks card ── */}
        <View style={s.banksCard}>
          <View style={s.banksHead}>
            <Text style={s.banksTitle}>Connected Banks</Text>
            <View style={s.banksCountChip}><Text style={s.banksCountText}>{`${BANKS.length} Banks`}</Text></View>
          </View>

          {BANKS.map((b) => {
            const open = expanded === b.name;
            return (
              <Pressable key={b.name} onPress={() => setExpanded(open ? null : b.name)} style={s.bankRow} testID={`fin-bank-${b.name}`}>
                <View style={s.bankTop}>
                  <View style={s.bankBadge}>
                    <Feather name="credit-card" size={16} color="#2dd4bf" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <Text style={s.bankName}>{b.name}</Text>
                    <Text style={s.bankAcc}>{`• A/c ${b.accHint}`}</Text>
                  </View>
                  <View style={s.balPill}><Text style={s.balPillText}>{inr2(b.balance)}</Text></View>
                </View>

                {open && (
                  <View style={s.bankDetails}>
                    <View style={s.bankDivider} />
                    <View style={s.bankCols}>
                      <View style={s.bankCol}>
                        <Text style={s.bankLabel}>Total Debit</Text>
                        <Text style={[s.bankColVal, { color: '#ef4444' }]}>{inr(b.debit)}</Text>
                      </View>
                      <View style={s.bankCol}>
                        <Text style={s.bankLabel}>Total Credit</Text>
                        <Text style={[s.bankColVal, { color: '#10b981' }]}>{inr(b.credit)}</Text>
                      </View>
                      <View style={s.bankCol}>
                        <Text style={s.bankLabel}>SMS Count</Text>
                        <Text style={[s.bankColVal, { color: '#3b82f6' }]}>{b.count}</Text>
                      </View>
                    </View>
                    <Text style={s.bankSmsHeader}>Parsed Bank SMS History</Text>
                    {b.messages.map((m, i) => (
                      <Text key={i} style={s.bankMsg}>· {m}</Text>
                    ))}
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>

        {/* Summary + disclaimer (V7 exact disclaimer text) */}
        <Text style={s.summaryText}>{summary}</Text>
        <Text style={s.disclaimer}>Approximate figures extracted from bank SMS — not an official statement.</Text>
      </ScrollView>
    </PanelModal>
  );
}

const s = StyleSheet.create({
  title: { color: PALETTE.text, fontSize: 18, fontFamily: 'Inter_700Bold' },
  sub: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2, marginBottom: 12 },

  // Hero — V7 bg_fin_hero (teal gradient)
  hero: { borderRadius: 16, padding: 20, borderWidth: 1, borderColor: 'rgba(45,212,191,0.25)' },
  heroLabel: { color: '#e2e8f0', fontSize: 11, fontFamily: 'Inter_700Bold', letterSpacing: 1.2, textAlign: 'center' },
  heroTotal: { color: '#ffffff', fontSize: 32, fontFamily: 'Inter_700Bold', textAlign: 'center', marginTop: 4 },
  heroChips: { flexDirection: 'row', justifyContent: 'center', gap: 12, marginTop: 12 },
  heroPill: { backgroundColor: 'rgba(255,255,255,0.10)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  heroPillText: { fontSize: 11, fontFamily: 'Inter_700Bold' },
  heroDivider: { height: 1, backgroundColor: 'rgba(255,255,255,0.20)', marginTop: 16, marginBottom: 14 },
  heroStats: { flexDirection: 'row', alignItems: 'center' },
  heroStat: { flex: 1, alignItems: 'center' },
  heroStatLabel: { color: '#cbd5e1', fontSize: 10, fontFamily: 'Inter_700Bold', letterSpacing: 0.8 },
  heroStatVal: { color: '#ffffff', fontSize: 15, fontFamily: 'Inter_700Bold', marginTop: 3 },
  heroVDivider: { width: 1, height: 28, backgroundColor: 'rgba(255,255,255,0.20)' },

  // Connected Banks card — V7 bg_fin_banks_container (dark me cardAlt)
  banksCard: { backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 16, padding: 14, marginTop: 14 },
  banksHead: { flexDirection: 'row', alignItems: 'center' },
  banksTitle: { flex: 1, color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  banksCountChip: { backgroundColor: 'rgba(45,212,191,0.12)', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3 },
  banksCountText: { color: '#2dd4bf', fontSize: 11, fontFamily: 'Inter_700Bold' },

  // Bank row — V7 item_fin_bank_row.xml (dark adapted)
  bankRow: { backgroundColor: PALETTE.bg, borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 14, padding: 12, marginTop: 10 },
  bankTop: { flexDirection: 'row', alignItems: 'center' },
  bankBadge: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(45,212,191,0.10)', borderWidth: 1, borderColor: 'rgba(45,212,191,0.25)', alignItems: 'center', justifyContent: 'center' },
  bankName: { color: PALETTE.text, fontSize: 15, fontFamily: 'Inter_700Bold' },
  bankAcc: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', marginTop: 2 },
  balPill: { backgroundColor: PALETTE.cardAlt, borderWidth: 1, borderColor: PALETTE.borderSoft, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5 },
  balPillText: { color: PALETTE.text, fontSize: 14, fontFamily: 'Inter_700Bold' },

  bankDetails: { marginTop: 12 },
  bankDivider: { height: 1, backgroundColor: PALETTE.borderSoft, marginBottom: 10 },
  bankCols: { flexDirection: 'row' },
  bankCol: { flex: 1 },
  bankLabel: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular' },
  bankColVal: { fontSize: 14, fontFamily: 'Inter_700Bold', marginTop: 2 },
  bankSmsHeader: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_700Bold', marginTop: 10 },
  bankMsg: { color: PALETTE.textMuted, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 6, lineHeight: 16 },

  summaryText: { color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Inter_400Regular', lineHeight: 18, marginTop: 12 },
  disclaimer: { color: PALETTE.textFaint, fontSize: 11, fontFamily: 'Inter_400Regular', marginTop: 6, marginBottom: 6 },
});
