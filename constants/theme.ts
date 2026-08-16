// Dark "premium navy" palette — converted to match the Premium APK's UI style
// (com.igoan.premiumbomber): near-black base, deep navy brand, blue/teal accents.
// Evidence: premium APK values/colors.xml + RN bundle string table
//   colorPrimary #023c69 (deep navy) · bg/statusBar #0d0d0d
//   surfaces #151718 / #202425 / #26292b · accent blue #52a9ff · teal #80cbc4
//   text #ffffff / muted #9ba1a6 / faint #707070 · error #cf6679 · success #1d873b
export const PALETTE = {
  bg: '#0f141b',
  bgAlt: '#080808',
  card: '#1f2937',
  cardEnd: '#202425',
  cardAlt: '#263244',
  border: '#2f3d50',
  borderSoft: '#3a4a61',
  fieldBorder: '#3a3f42',
  text: '#ffffff',
  textSoft: '#f3f3f4',
  textMuted: '#9ba1a6',
  textFaint: '#707070',
  textDim: '#52575a',
  textCbd: '#bcbcbc',
  textE2: '#dfdfdf',
  primary: '#023c69',
  primaryDark: '#012a4a',
  primaryBright: '#52a9ff',
  teal: '#80cbc4',
  violet: '#52a9ff',
  green: '#1d873b',
  greenBright: '#2ea043',
  greenBg: 'rgba(29,135,59,0.15)',
  red: '#cf6679',
  redSoft: '#e08595',
  redDark: '#5c2a33',
  redBg: 'rgba(207,102,121,0.12)',
  amber: '#fbbf24',
  sky: '#52a9ff',
  emerald: '#80cbc4',
  // gradient stops — flat-ish dark navy gradients (premium minimal look)
  headerGrad: ['#023c69', '#012a4a'] as const,
  btnGrad: ['#2f80d8', '#1a5fae'] as const,
  cardGrad: ['#1f2937', '#263244'] as const,
} as const;

export const RADIUS = 12;
