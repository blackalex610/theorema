'use strict';

// Order matters in both tables: a Chrome UA contains "Safari", and an Edge UA
// contains "Chrome". Most specific match first.
const detectPlatform = (userAgent = '') => {
  const ua = String(userAgent);
  if (/iPad/i.test(ua)) return 'iPad';
  if (/iPhone/i.test(ua)) return 'iPhone';
  if (/Android/i.test(ua)) return 'Android';
  if (/Macintosh|Mac OS X/i.test(ua)) return 'Mac';
  if (/Windows/i.test(ua)) return 'Windows';
  if (/Linux/i.test(ua)) return 'Linux';
  return 'Устройство';
};

const detectBrowser = (userAgent = '') => {
  const ua = String(userAgent);
  if (/Edg\//i.test(ua)) return 'Edge';
  if (/OPR\/|Opera/i.test(ua)) return 'Opera';
  if (/Chrome\//i.test(ua) && !/Chromium/i.test(ua)) return 'Chrome';
  if (/Firefox\//i.test(ua)) return 'Firefox';
  if (/Safari\//i.test(ua)) return 'Safari';
  return 'Браузър';
};

const describeDevice = (userAgent = '') =>
  `${detectPlatform(userAgent)} · ${detectBrowser(userAgent)}`;

module.exports = { describeDevice, detectPlatform, detectBrowser };
