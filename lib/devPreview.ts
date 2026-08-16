// ═══ DEV PREVIEW ONLY (owner UI-tweaking phase, 2026-08-15) ═══
// Jab DEV_PREVIEW true ho to devices/SMS server ke bajaye ye FAKE data aata hai —
// login bypass ke saath milke preview me poora populated dashboard dikhta hai.
// ⚠️ RELEASE SAFETY: production APK me __DEV__ HAMESHA false hota hai (Expo/Metro
// bundler guarantee) — isliye preview mode release build me activate hona RUNTIME
// pe impossible hai; kisi source-edit reminder pe depend nahi karta.
// Preview phase khatam ho to DEV_PREVIEW_ENABLED = false kar do (belt-and-suspenders).

import type { ApiDevice, ApiMessage } from '@/lib/devices';

const DEV_PREVIEW_ENABLED = true; // 2026-08-15: owner UI-preview phase — login bypass ON (production APK banane se PEHLE false karna — __DEV__ guard release me waise bhi block karta hai)
export const DEV_PREVIEW = typeof __DEV__ !== 'undefined' && __DEV__ && DEV_PREVIEW_ENABLED;

const now = Date.now();
const MIN = 60 * 1000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

// 4 fake devices — online/offline/uninstalled mix, dual-sim coverage, battery
// present/missing mix — taaki har UI state preview me dikhe.
// Kisi pe deviceLabel PRESET nahi (owner rule 2026-08-15): label kabhi auto nahi
// hota — sirf tab aata hai jab user khud Label button se choose kare.
export const FAKE_DEVICES: ApiDevice[] = [
  {
    id: 'dev-fake-1', model: 'Redmi Note 12', label: 'Ramesh Kumar', sim: 2,
    simLabel: 'Jio', number: '+91 98765 43210', sim2Label: 'Airtel', sim2Number: '+91 98765 00001',
    online: true, slotId: 'slot1', upiPin: '2468', favorite: true,
    batteryLevel: 68, networkIp: '103.42.18.77',
    registeredAt: now - 5 * DAY, lastOnlineAt: now - 2 * MIN,
  },
  {
    id: 'dev-fake-2', model: 'Samsung Galaxy M14', label: 'Sunita Devi', sim: 1,
    simLabel: 'Vi', number: '+91 91234 56789',
    online: true, slotId: 'slot1',
    batteryLevel: 34, networkIp: '49.36.101.12',
    registeredAt: now - 3 * DAY, lastOnlineAt: now - 8 * MIN,
  },
  {
    id: 'dev-fake-3', model: 'Realme C55', label: 'Amit Singh', sim: 1,
    simLabel: 'Jio', number: '+91 99887 76655',
    online: false, slotId: 'slot2',
    batteryLevel: null, networkIp: 'N/A',
    registeredAt: now - 12 * DAY, lastOnlineAt: now - 2 * DAY,
  },
  {
    id: 'dev-fake-4', model: 'Poco M6 Pro', label: 'Vikram Yadav', sim: 2,
    simLabel: 'Airtel', number: '+91 90000 11111', sim2Label: 'BSNL', sim2Number: '+91 90000 22222',
    online: false, slotId: 'slot2', appUninstalled: true,
    batteryLevel: 12, networkIp: 'N/A',
    registeredAt: now - 20 * DAY, lastOnlineAt: now - 6 * DAY,
  },
];

// Fake SMS logs — bank OTP style (panel ka typical content), details screen
// populated dikhe isliye. Sirf online dono devices pe.
export const FAKE_MESSAGES: Record<string, ApiMessage[]> = {
  'dev-fake-1': [
    { id: 'm1', from: 'VK-HDFCBK', body: 'OTP for txn of Rs 2,499.00 at AMAZON is 482913. Do not share it with anyone.', time: '15-08-2026 | 06:32 am', type: 'inbox' },
    { id: 'm2', from: 'AX-ICICIB', body: 'Rs 5,000.00 debited from A/c XX4521 on 15-08-26. UPI Ref 622781450223.', time: '15-08-2026 | 06:15 am', type: 'inbox' },
    { id: 'm3', from: '+91 88777 66554', body: 'Bhai paisa bhej diya check kar lena', time: '14-08-2026 | 11:48 pm', type: 'inbox' },
    { id: 'm4', from: 'me', body: 'Haan mil gaya, thanks', time: '14-08-2026 | 11:52 pm', type: 'sent' },
  ],
  'dev-fake-2': [
    { id: 'm1', from: 'QP-SBIINB', body: 'Your OTP for SBI NetBanking login is 771204. Valid for 10 mins.', time: '15-08-2026 | 06:20 am', type: 'inbox' },
    { id: 'm2', from: 'JM-AIRTEL', body: 'Your recharge of Rs 299 is successful. Validity 28 days.', time: '14-08-2026 | 09:05 pm', type: 'inbox' },
  ],
};
