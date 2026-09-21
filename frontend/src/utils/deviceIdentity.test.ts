import { beforeEach, describe, expect, it } from 'vitest';
import {
  describeDevice,
  detectPlatform,
  getDesktopId,
  getDeviceId,
  getDisplayName,
  getNickname,
  setNickname,
} from './deviceIdentity';

const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const EDGE =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0';
const ANDROID =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';

describe('deviceIdentity', () => {
  beforeEach(() => localStorage.clear());

  it('names devices without confusing Chrome for Safari or Edge for Chrome', () => {
    expect(detectPlatform(IPHONE)).toBe('iPhone');
    expect(describeDevice(IPHONE)).toBe('iPhone · Safari');
    expect(describeDevice(EDGE)).toBe('Windows · Edge');
    expect(describeDevice(ANDROID)).toBe('Android · Chrome');
  });

  it('mints a stable device id that survives repeat calls', () => {
    const first = getDeviceId();
    expect(first).toBeTruthy();
    expect(getDeviceId()).toBe(first);
  });

  it('keeps device and desktop ids distinct', () => {
    expect(getDeviceId()).not.toBe(getDesktopId());
  });

  it('scopes ids per user, so switching account does not reuse a device id', () => {
    localStorage.setItem('user', JSON.stringify({ id: 1 }));
    const first = getDeviceId();
    localStorage.setItem('user', JSON.stringify({ id: 2 }));
    expect(getDeviceId()).not.toBe(first);
  });

  it('round-trips a nickname and falls back to empty', () => {
    expect(getNickname()).toBe('');
    setNickname('Телефонът на Иван');
    expect(getNickname()).toBe('Телефонът на Иван');
  });

  it('prefers the nickname for the display name, else the derived name', () => {
    expect(getDisplayName()).toBe(describeDevice());
    setNickname('Моят телефон');
    expect(getDisplayName()).toBe('Моят телефон');
  });
});
