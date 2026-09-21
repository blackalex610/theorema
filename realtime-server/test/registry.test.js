'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { createRegistry } = require('../src/registry');

// Deterministic ids keep assertions readable.
const makeRegistry = () => {
  let n = 0;
  return createRegistry({ newId: () => `id-${++n}` });
};

const announcePhone = (registry, overrides = {}) =>
  registry.announce({
    userId: 'u1',
    deviceId: 'dev-a',
    socketId: 'sock-phone',
    name: 'iPhone · Safari',
    platform: 'iPhone',
    userAgent: 'ua',
    at: 1000,
    ...overrides,
  });

test('announce then listDevices returns the device as free', () => {
  const registry = makeRegistry();
  announcePhone(registry);

  const devices = registry.listDevices('u1');
  assert.equal(devices.length, 1);
  assert.equal(devices[0].deviceId, 'dev-a');
  assert.equal(devices[0].name, 'iPhone · Safari');
  assert.equal(devices[0].busy, false);
});

test('re-announcing the same deviceId replaces rather than duplicates', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  announcePhone(registry, { socketId: 'sock-phone-2', at: 5000 });

  const devices = registry.listDevices('u1');
  assert.equal(devices.length, 1);
  // announcedAt is preserved across a reconnect so the desktop list does not
  // flicker back to "seen just now" every time the phone's screen wakes.
  assert.equal(devices[0].announcedAt, 1000);
  assert.equal(registry.getEntry('u1', 'dev-a').socketId, 'sock-phone-2');
});

test('devices are isolated per account', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  announcePhone(registry, { userId: 'u2', deviceId: 'dev-b', socketId: 'sock-other' });

  assert.equal(registry.listDevices('u1').length, 1);
  assert.equal(registry.listDevices('u2').length, 1);
  assert.equal(registry.listDevices('u1')[0].deviceId, 'dev-a');
  assert.equal(registry.getEntry('u1', 'dev-b'), undefined);
});

test('withdraw removes the device from its account list', () => {
  const registry = makeRegistry();
  announcePhone(registry);

  assert.equal(registry.withdraw({ userId: 'u1', deviceId: 'dev-a' }), true);
  assert.equal(registry.listDevices('u1').length, 0);
  assert.equal(registry.withdraw({ userId: 'u1', deviceId: 'dev-a' }), false);
});

test('removeSocketPresence finds the device by socket id', () => {
  const registry = makeRegistry();
  announcePhone(registry);

  assert.deepEqual(registry.removeSocketPresence('sock-phone'), {
    userId: 'u1',
    deviceId: 'dev-a',
  });
  assert.equal(registry.listDevices('u1').length, 0);
  assert.equal(registry.removeSocketPresence('sock-phone'), null);
});

test('createRequest marks the device busy and resolveRequest(accept) links it', () => {
  const registry = makeRegistry();
  announcePhone(registry);

  const created = registry.createRequest({
    userId: 'u1',
    desktopId: 'desk-1',
    desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a',
    at: 2000,
  });
  assert.equal(created.ok, true);
  assert.equal(created.request.expiresAt, 32000);
  assert.equal(registry.listDevices('u1')[0].busy, true);

  const resolved = registry.resolveRequest(created.request.requestId, true, 2500);
  assert.equal(resolved.ok, true);
  assert.equal(resolved.accepted, true);
  assert.equal(resolved.link.phoneDeviceId, 'dev-a');
  assert.equal(resolved.link.phoneSocketId, 'sock-phone');
  assert.equal(resolved.link.desktopSocketId, 'sock-desk');
  // Still busy — now because it is linked, not because a request is pending.
  assert.equal(registry.listDevices('u1')[0].busy, true);
});

test('resolveRequest(decline) frees the device without creating a link', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });

  const resolved = registry.resolveRequest(created.request.requestId, false, 2500);
  assert.equal(resolved.ok, true);
  assert.equal(resolved.accepted, false);
  assert.equal(registry.listDevices('u1')[0].busy, false);
  assert.equal(registry.getLinkByPhoneDeviceId('dev-a'), undefined);
});

test('a second request for a busy device is refused', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });

  const second = registry.createRequest({
    userId: 'u1', desktopId: 'desk-2', desktopSocketId: 'sock-desk-2',
    phoneDeviceId: 'dev-a', at: 2100,
  });
  assert.deepEqual(second, { ok: false, reason: 'DEVICE_BUSY' });
});

test('a desktop that is already linked cannot request another device', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  announcePhone(registry, { deviceId: 'dev-b', socketId: 'sock-phone-b' });

  const first = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  registry.resolveRequest(first.request.requestId, true, 2100);

  const second = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-b', at: 2200,
  });
  assert.deepEqual(second, { ok: false, reason: 'ALREADY_LINKED' });
});

test('requesting an unknown device reports DEVICE_GONE', () => {
  const registry = makeRegistry();
  const result = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'nope', at: 2000,
  });
  assert.deepEqual(result, { ok: false, reason: 'DEVICE_GONE' });
});

test('a device belonging to another account cannot be requested', () => {
  const registry = makeRegistry();
  announcePhone(registry, { userId: 'u2', deviceId: 'dev-victim', socketId: 'sock-victim' });

  const result = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-victim', at: 2000,
  });
  assert.deepEqual(result, { ok: false, reason: 'DEVICE_GONE' });
});

test('sweepRequests expires pending requests and frees the device', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });

  assert.deepEqual(registry.sweepRequests(31999), []);
  const expired = registry.sweepRequests(32000);
  assert.equal(expired.length, 1);
  assert.equal(expired[0].requestId, created.request.requestId);
  assert.equal(registry.listDevices('u1')[0].busy, false);
  assert.deepEqual(registry.resolveRequest(created.request.requestId, true, 33000), {
    ok: false,
    reason: 'REQUEST_UNKNOWN',
  });
});

test('phone disconnect holds the link and a re-announce reattaches it', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  const { link } = registry.resolveRequest(created.request.requestId, true, 2100);

  const gone = registry.markSocketGone('sock-phone', 3000);
  assert.equal(gone.side, 'phone');
  assert.equal(gone.link.phoneGraceUntil, 33000);
  // Presence disappears immediately even though the link is held.
  registry.removeSocketPresence('sock-phone');
  assert.equal(registry.listDevices('u1').length, 0);

  announcePhone(registry, { socketId: 'sock-phone-2', at: 4000 });
  const reattached = registry.reattachPhone({
    userId: 'u1', deviceId: 'dev-a', socketId: 'sock-phone-2',
  });
  assert.equal(reattached.linkId, link.linkId);
  assert.equal(reattached.phoneSocketId, 'sock-phone-2');
  assert.equal(reattached.phoneGraceUntil, null);
  assert.deepEqual(registry.sweepGrace(99999), []);
});

test('desktop disconnect past the grace window ends the link', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  registry.resolveRequest(created.request.requestId, true, 2100);

  registry.markSocketGone('sock-desk', 3000);
  assert.deepEqual(registry.sweepGrace(32999), []);

  const ended = registry.sweepGrace(33000);
  assert.equal(ended.length, 1);
  assert.equal(ended[0].side, 'desktop');
  assert.equal(registry.getLinkByPhoneDeviceId('dev-a'), undefined);
  assert.equal(registry.listDevices('u1')[0].busy, false);
});

test('reattachDesktop restores a link inside the grace window', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  registry.resolveRequest(created.request.requestId, true, 2100);
  registry.markSocketGone('sock-desk', 3000);

  const link = registry.reattachDesktop({
    userId: 'u1', desktopId: 'desk-1', socketId: 'sock-desk-2',
  });
  assert.equal(link.desktopSocketId, 'sock-desk-2');
  assert.equal(link.desktopGraceUntil, null);
  assert.deepEqual(registry.sweepGrace(99999), []);
});

test('reattachDesktop refuses a desktopId belonging to another account', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  registry.resolveRequest(created.request.requestId, true, 2100);
  registry.markSocketGone('sock-desk', 3000);

  assert.equal(
    registry.reattachDesktop({ userId: 'u2', desktopId: 'desk-1', socketId: 'sock-evil' }),
    null
  );
});

test('setExamProblems is stored on the link and endLink clears every index', () => {
  const registry = makeRegistry();
  announcePhone(registry);
  const created = registry.createRequest({
    userId: 'u1', desktopId: 'desk-1', desktopSocketId: 'sock-desk',
    phoneDeviceId: 'dev-a', at: 2000,
  });
  const { link } = registry.resolveRequest(created.request.requestId, true, 2100);

  registry.setExamProblems(link.linkId, [{ id: 17, label: 'Задача 17', type: 'open' }]);
  assert.equal(registry.getLinkByDesktopId('desk-1').examProblems[0].id, 17);

  assert.equal(registry.endLink(link.linkId).linkId, link.linkId);
  assert.equal(registry.getLinkByDesktopId('desk-1'), undefined);
  assert.equal(registry.getLinkByPhoneDeviceId('dev-a'), undefined);
  assert.equal(registry.getLinkBySocketId('sock-desk'), undefined);
  assert.equal(registry.listDevices('u1')[0].busy, false);
  assert.equal(registry.endLink(link.linkId), null);
});
