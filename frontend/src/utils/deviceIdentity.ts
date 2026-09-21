import { withUserScope } from './userIdentity';

const DEVICE_ID_KEY = 'connect-device-id-v1';
const DESKTOP_ID_KEY = 'connect-desktop-id-v1';
const NICKNAME_KEY = 'connect-device-nickname-v1';

const mintId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `dev-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
};

/**
 * A stable per-user id for this browser.
 *
 * Falls back to a fresh id rather than throwing: a phone in private mode still
 * pairs, it just will not survive a reload.
 */
const stableId = (key: string): string => {
  const scoped = withUserScope(key);
  try {
    const existing = localStorage.getItem(scoped);
    if (existing) return existing;
    const minted = mintId();
    localStorage.setItem(scoped, minted);
    return minted;
  } catch {
    return mintId();
  }
};

export const getDeviceId = (): string => stableId(DEVICE_ID_KEY);
export const getDesktopId = (): string => stableId(DESKTOP_ID_KEY);

export const getNickname = (): string => {
  try {
    return localStorage.getItem(withUserScope(NICKNAME_KEY)) ?? '';
  } catch {
    return '';
  }
};

export const setNickname = (name: string): void => {
  try {
    localStorage.setItem(withUserScope(NICKNAME_KEY), name.trim());
  } catch {
    // Non-fatal: the nickname is a convenience, not state the protocol needs.
  }
};

// Order matters in both tables: a Chrome UA contains "Safari", an Edge UA
// contains "Chrome".
export const detectPlatform = (userAgent: string = navigator.userAgent): string => {
  if (/iPad/i.test(userAgent)) return 'iPad';
  if (/iPhone/i.test(userAgent)) return 'iPhone';
  if (/Android/i.test(userAgent)) return 'Android';
  if (/Macintosh|Mac OS X/i.test(userAgent)) return 'Mac';
  if (/Windows/i.test(userAgent)) return 'Windows';
  if (/Linux/i.test(userAgent)) return 'Linux';
  return 'Устройство';
};

const detectBrowser = (userAgent: string): string => {
  if (/Edg\//i.test(userAgent)) return 'Edge';
  if (/OPR\/|Opera/i.test(userAgent)) return 'Opera';
  if (/Chrome\//i.test(userAgent) && !/Chromium/i.test(userAgent)) return 'Chrome';
  if (/Firefox\//i.test(userAgent)) return 'Firefox';
  if (/Safari\//i.test(userAgent)) return 'Safari';
  return 'Браузър';
};

export const describeDevice = (userAgent: string = navigator.userAgent): string =>
  `${detectPlatform(userAgent)} · ${detectBrowser(userAgent)}`;

/** The nickname if the user set one, otherwise the derived name. */
export const getDisplayName = (): string => getNickname() || describeDevice();
