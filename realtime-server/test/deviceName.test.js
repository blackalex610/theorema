'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { describeDevice, detectPlatform } = require('../src/deviceName');

const IPHONE_SAFARI =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const ANDROID_CHROME =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';
const WINDOWS_EDGE =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0';

test('detectPlatform recognises the common platforms', () => {
  assert.equal(detectPlatform(IPHONE_SAFARI), 'iPhone');
  assert.equal(detectPlatform(ANDROID_CHROME), 'Android');
  assert.equal(detectPlatform(WINDOWS_EDGE), 'Windows');
  assert.equal(detectPlatform(''), 'Устройство');
});

test('describeDevice does not mistake Chrome for Safari or Edge for Chrome', () => {
  assert.equal(describeDevice(IPHONE_SAFARI), 'iPhone · Safari');
  assert.equal(describeDevice(ANDROID_CHROME), 'Android · Chrome');
  assert.equal(describeDevice(WINDOWS_EDGE), 'Windows · Edge');
});
