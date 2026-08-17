// Financial SMS parser — panel app ka "Financial Dashboard" isi se real data
// banata hai. HAR DEVICE ka apna SMS log parse hota hai (koi hardcoded/demo
// numbers nahi — owner rule: dashboard me sirf device ke asli SMS se aaye figures).
//
// Kya nikalta hai (Indian bank/UPI SMS formats):
//   - bank ka naam (sender ID suffix jaise AX-HDFCBK, ya content signature jaise
//     "Not you? Call 18005700/5000-BOB")
//   - account last-4 (A/C XXXXXX2679, Acct XX901, card XX4521)
//   - debit/credit amounts ("Rs.1.00 Dr. from A/C", "debited with Rs.1,299.00",
//     "INR 500 credited")
//   - latest available balance ("AvlBal:Rs2455.00", "Avl bal Rs.1,150")
//   - credit card available limit / total outstanding
// OTP-only messages amounts me COUNT nahi hote (OTP ka amount transaction nahi hai).

export interface FinSms {
  from: string;
  body: string;
  time: string; // 'DD-MM-YYYY | hh:mm am'
  type?: string; // 'inbox' | 'sent' — sirf inbox (bank alerts incoming hote hain)
}

export interface ParsedBank {
  name: string;
  accHint: string; // "**2679" ya '' (account detect nahi hua)
  count: number; // is bank+account ke kitne SMS parse hue
  debit: number; // total debited
  credit: number; // total credited
  balance: number; // SABSE NAYA available-balance hint (0 = kabhi mila hi nahi)
  creditAvail: number; // credit card available limit (0 = n/a)
  creditOut: number; // credit card total outstanding (0 = n/a)
  messages: string[]; // parse hue raw SMS bodies (history view ke liye)
}

// ── Bank identification ------------------------------------------------------

// Sender ID suffix → bank name (Indian DLT sender format: XX-BANKCD).
const SENDER_BANKS: Record<string, string> = {
  HDFCBK: 'HDFC Bank', ICICIB: 'ICICI Bank', AXISBK: 'Axis Bank',
  SBINBK: 'State Bank of India', SBIINB: 'State Bank of India', SBIUPI: 'State Bank of India',
  BOBTXN: 'Bank of Baroda', BARODA: 'Bank of Baroda', BOBSMS: 'Bank of Baroda',
  KOTAKB: 'Kotak Mahindra Bank', PNBHTX: 'Punjab National Bank', PNBSMS: 'Punjab National Bank',
  CANBNK: 'Canara Bank', UNIONB: 'Union Bank of India', UBISMS: 'Union Bank of India',
  IDFCFB: 'IDFC First Bank', YESBNK: 'Yes Bank', INDUSB: 'IndusInd Bank',
  FEDBNK: 'Federal Bank', MAHABK: 'Bank of Maharashtra', MAHSMS: 'Bank of Maharashtra',
  CENTBK: 'Central Bank of India', IOBANK: 'Indian Overseas Bank', IOBTXN: 'Indian Overseas Bank',
  BOITXN: 'Bank of India', BOINDS: 'Bank of India', UCOBNK: 'UCO Bank',
  INDBNK: 'Indian Bank', INDBTB: 'Indian Bank', PYTMPT: 'Paytm Payments Bank', PAYTMB: 'Paytm Payments Bank',
  AIRTEL: 'Airtel Payments Bank', AIRPAY: 'Airtel Payments Bank',
  KARBNK: 'Karnataka Bank', KVBank: 'Karur Vysya Bank', SCBANK: 'Standard Chartered',
  CITIBK: 'Citibank', HSBCBK: 'HSBC', RBLBNK: 'RBL Bank', BANDHN: 'Bandhan Bank',
  AUSFBK: 'AU Small Finance Bank', IDBIBK: 'IDBI Bank', DBSBNK: 'DBS Bank',
  SARBNK: 'Saraswat Bank', JIOPAY: 'Jio Payments Bank', FINOPB: 'Fino Payments Bank',
};

// Content signatures — jab sender generic ho (VM-*, numeric) par body me bank likha ho.
const CONTENT_BANKS: [RegExp, string][] = [
  [/bank of baroda|\bBOB\b|1800\s?5700/i, 'Bank of Baroda'],
  [/hdfc/i, 'HDFC Bank'], [/icici/i, 'ICICI Bank'], [/axis/i, 'Axis Bank'],
  [/state bank of india|\bSBI\b/i, 'State Bank of India'],
  [/kotak/i, 'Kotak Mahindra Bank'], [/punjab national|\bPNB\b/i, 'Punjab National Bank'],
  [/canara/i, 'Canara Bank'], [/union bank|\bUBI\b/i, 'Union Bank of India'],
  [/idfc first/i, 'IDFC First Bank'], [/yes bank/i, 'Yes Bank'], [/indusind/i, 'IndusInd Bank'],
  [/federal bank/i, 'Federal Bank'], [/bank of maharashtra|mahabank/i, 'Bank of Maharashtra'],
  [/central bank of india/i, 'Central Bank of India'], [/indian overseas|\bIOB\b/i, 'Indian Overseas Bank'],
  [/bank of india|\bBOI\b/i, 'Bank of India'], [/uco bank/i, 'UCO Bank'],
  [/indian bank/i, 'Indian Bank'], [/paytm payments/i, 'Paytm Payments Bank'],
  [/airtel payments/i, 'Airtel Payments Bank'], [/idbi/i, 'IDBI Bank'],
  [/karnataka bank/i, 'Karnataka Bank'], [/rbl bank|\bRBL\b/i, 'RBL Bank'],
  [/bandhan/i, 'Bandhan Bank'], [/au small finance/i, 'AU Small Finance Bank'],
  [/standard chartered/i, 'Standard Chartered'], [/citibank|citi bank/i, 'Citibank'],
  [/dbs bank|\bDBS\b/i, 'DBS Bank'], [/hsbc/i, 'HSBC'],
];

// ── Amount patterns ----------------------------------------------------------

const NUM = '([\\d,]+(?:\\.\\d{1,2})?)';
const AMT = `(?:Rs\\.?|INR|₹)\\s?${NUM}`;

// Debit: keyword ke baad amount, ya amount ke baad "Dr."/debited marker.
const DEBIT_RES = [
  new RegExp(`(?:debited(?:\\s+with)?|debit(?:ed)?\\s+(?:from|by)|withdrawn|spent|paid)\\D{0,25}?${AMT}`, 'i'),
  new RegExp(`${AMT}\\s*(?:Dr\\.?\\s+from|debited)`, 'i'),
];
const CREDIT_RES = [
  new RegExp(`(?:credited(?:\\s+to|\\s+with)?|credit(?:ed)?\\s+(?:to|by)|deposited|received)\\D{0,25}?${AMT}`, 'i'),
  new RegExp(`${AMT}\\s*(?:Cr\\.?\\s+to|credited)`, 'i'),
];
// Available balance — SMS ke end me hota hai; SABSE NAYA SMS ka balance valid hai.
const BALANCE_RES = [
  new RegExp(`(?:Avl\\s?Bal|AvlBal|Avail(?:able)?\\s+Bal(?:ance)?|A\\/c\\s+Bal)\\s*:?\\s*-?\\s*(?:Rs\\.?|INR|₹)?\\s?${NUM}`, 'i'),
  new RegExp(`${AMT}\\s*(?:is\\s+)?(?:your\\s+)?(?:available|avl)\\.?\\s*bal`, 'i'),
];
// Credit card stats.
const CREDIT_AVAIL_RE = new RegExp(`(?:available\\s+(?:credit\\s+)?limit|avl\\.?\\s+(?:credit\\s+)?limit)\\D{0,15}?(?:Rs\\.?|INR|₹)?\\s?${NUM}`, 'i');
const CREDIT_OUT_RE = new RegExp(`(?:total\\s+outstanding|outstanding\\s+(?:amount|balance|bal))\\D{0,15}?(?:Rs\\.?|INR|₹)?\\s?${NUM}`, 'i');
// Account last-4: A/C XXXXXX2679, Acct XX901, card ending 4521.
const ACCOUNT_RES = [
  /(?:A\/C|A\/c|Acct?|Account)\s*(?:no\.?|number)?\s*[:.]?\s*[Xx*#]{0,8}(\d{4})\b/,
  /(?:card|a\/c)\s*(?:ending|ends?|no)?\s*[Xx*#]{0,8}(\d{4})\b/i,
];

const OTP_RE = /\bOTP\b|one[-\s]?time\s+password|verification\s+code/i;
const FIN_SIGNAL_RE = /debited|credited|\bDr\.?\b|\bCr\.?\b|Avl\s?Bal|AvlBal|available\s+bal|outstanding|credit\s+limit|withdrawn|deposited/i;

function parseNum(s: string): number {
  const n = Number(s.replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

function firstMatch(res: RegExp[], text: string): RegExpMatchArray | null {
  for (const re of res) {
    const m = text.match(re);
    if (m) return m;
  }
  return null;
}

function bankName(from: string, body: string): string | null {
  // Sender suffix: "AX-HDFCBK" / "VK-ICICIB" → code after last '-'.
  const suffix = (from.split('-').pop() ?? '').trim().toUpperCase();
  if (suffix && SENDER_BANKS[suffix]) return SENDER_BANKS[suffix];
  for (const [re, name] of CONTENT_BANKS) {
    if (re.test(body) || re.test(from)) return name;
  }
  // Unknown lekin bank-like sender suffix (*BK/*BNK/*BANK) — pretty-print karo.
  if (/(BK|BNK|BANK)$/.test(suffix) && suffix.length >= 4) {
    return suffix.replace(/(BK|BNK|BANK)$/, '').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) + ' Bank';
  }
  return null;
}

function accHintOf(body: string): string {
  const m = firstMatch(ACCOUNT_RES, body);
  return m ? `**${m[1]}` : '';
}

// 'DD-MM-YYYY | hh:mm am' → comparable ms epoch. Parse fail pe 0 (order fallback).
function timeMs(time: string): number {
  const m = time.match(/(\d{2})-(\d{2})-(\d{4})\s*\|\s*(\d{1,2}):(\d{2})\s*(am|pm)/i);
  if (!m) return 0;
  let h = Number(m[4]);
  const pm = m[6].toLowerCase() === 'pm';
  if (pm && h < 12) h += 12;
  if (!pm && h === 12) h = 0;
  return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]), h, Number(m[5])).getTime();
}

// ── Main entry ---------------------------------------------------------------

export function parseFinancialSms(list: FinSms[]): ParsedBank[] {
  const groups = new Map<string, ParsedBank & { balAt: number; creditAt: number; idx: number }>();
  let order = 0;

  for (const sms of list) {
    if (sms.type === 'sent') continue; // bank alerts inbox me aate hain
    const body = sms.body ?? '';
    if (!body) continue;
    // Financial signal hona chahiye (warna Ekart/OTP/promotional SMS bhi bank ban jayenge).
    if (!FIN_SIGNAL_RE.test(body)) continue;
    // OTP-only message — amount transaction nahi hai, skip.
    if (OTP_RE.test(body) && !/(?:debited|credited|Avl\s?Bal|AvlBal|outstanding)/i.test(body)) continue;

    const name = bankName(sms.from ?? '', body);
    const accHint = accHintOf(body);
    // Bank identify hi nahi hua AUR account hint bhi nahi — financial signal
    // akela kaafi nahi (UPI app SMS bhi "credited" bolte hain bina bank ke).
    if (!name && !accHint) continue;

    const debitM = firstMatch(DEBIT_RES, body);
    const creditM = firstMatch(CREDIT_RES, body);
    const balM = firstMatch(BALANCE_RES, body);
    const availM = body.match(CREDIT_AVAIL_RE);
    const outM = body.match(CREDIT_OUT_RE);
    // Kuch bhi extract nahi hua (sirf signal word tha) — useless row mat banao.
    if (!debitM && !creditM && !balM && !availM && !outM) continue;

    const key = `${name ?? 'Unknown Bank'}|${accHint}`;
    let g = groups.get(key);
    if (!g) {
      g = {
        name: name ?? 'Unknown Bank', accHint, count: 0,
        debit: 0, credit: 0, balance: 0, creditAvail: 0, creditOut: 0,
        messages: [], balAt: -1, creditAt: -1, idx: order++,
      };
      groups.set(key, g);
    }
    g.count++;
    g.messages.push(body);
    if (debitM) g.debit += parseNum(debitM[1]);
    if (creditM) g.credit += parseNum(creditM[1]);

    // Latest-balance-wins: time parse ho to newest, warna baad wala SMS (list order).
    const t = timeMs(sms.time ?? '');
    const cmp = t > 0 ? t : order; // unparseable time — list order se compare
    if (balM && cmp >= g.balAt) {
      g.balance = parseNum(balM[1]);
      g.balAt = cmp;
    }
    if (availM || outM) {
      if (cmp >= g.creditAt) {
        if (availM) g.creditAvail = parseNum(availM[1]);
        if (outM) g.creditOut = parseNum(outM[1]);
        g.creditAt = cmp;
      }
    }
  }

  return [...groups.values()]
    .sort((a, b) => a.idx - b.idx) // pehli baar jis order me dikhe
    .map(({ balAt: _b, creditAt: _c, idx: _i, ...rest }) => rest);
}
