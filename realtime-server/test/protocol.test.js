'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('crypto');
const { io: ioClient } = require('socket.io-client');

process.env.REALTIME_JWT_SECRET = 'test-secret';
process.env.ALLOW_LOCAL_NETWORK = 'true';

const { createApp } = require('../src/server');

const SECRET = 'test-secret';
const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
const signToken = (payload) => {
  const head = b64({ alg: 'HS256', typ: 'JWT' });
  const body = b64(payload);
  const sig = crypto.createHmac('sha256', SECRET).update(`${head}.${body}`).digest('base64url');
  return `${head}.${body}.${sig}`;
};

const withServer = async (fn) => {
  const { server, io, registry } = createApp();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const sockets = [];
  const connect = (userId) =>
    new Promise((resolve, reject) => {
      const socket = ioClient(url, {
        auth: { token: signToken({ sub: userId }) },
        transports: ['websocket'],
        reconnection: false,
      });
      sockets.push(socket);
      socket.on('connect', () => resolve(socket));
      socket.on('connect_error', reject);
    });

  try {
    await fn({ connect, registry, url });
  } finally {
    sockets.forEach((s) => s.close());
    io.close();
    await new Promise((resolve) => server.close(resolve));
  }
};

// Always time-bounded: an over-budget packet makes Socket.IO close the
// connection instead of acking, which would otherwise hang the whole file.
const emit = (socket, event, payload, timeoutMs = 5000) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout waiting for ack of ${event}`)), timeoutMs);
    socket.emit(event, payload, (response) => {
      clearTimeout(timer);
      resolve(response);
    });
  });

const once = (socket, event, timeoutMs = 3000) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout waiting for ${event}`)), timeoutMs);
    socket.once(event, (payload) => {
      clearTimeout(timer);
      resolve(payload);
    });
  });

/** Announce a phone, subscribe a desktop, and complete the confirm handshake. */
const linkPair = async (connect) => {
  const phone = await connect('u1');
  await emit(phone, 'presence:announce', {
    deviceId: 'dev-a', name: 'iPhone · Safari', platform: 'iPhone',
  });
  const desktop = await connect('u1');
  await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows · Chrome' });

  const incoming = once(phone, 'link:incoming');
  await emit(desktop, 'link:request', { deviceId: 'dev-a' });
  const request = await incoming;

  const phoneLinked = once(phone, 'link:established');
  const desktopLinked = once(desktop, 'link:established');
  await emit(phone, 'link:respond', { requestId: request.requestId, accept: true });
  await Promise.all([phoneLinked, desktopLinked]);

  return { phone, desktop, request };
};

test('a phone that announces appears in its owner desktop list', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', {
      deviceId: 'dev-a', name: 'iPhone · Safari', platform: 'iPhone',
    });

    const desktop = await connect('u1');
    const ack = await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows · Chrome' });
    assert.equal(ack.ok, true);
    assert.equal(ack.devices.length, 1);
    assert.equal(ack.devices[0].deviceId, 'dev-a');
  });
});

test('a desktop never sees another account devices', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });

    const stranger = await connect('u2');
    const ack = await emit(stranger, 'presence:subscribe', { desktopId: 'desk-x', name: 'Mac' });
    assert.deepEqual(ack.devices, []);

    const denied = await emit(stranger, 'link:request', { deviceId: 'dev-a' });
    assert.deepEqual(denied, { ok: false, reason: 'DEVICE_GONE' });
  });
});

test('presence:list is pushed to subscribed desktops as devices come and go', async () => {
  await withServer(async ({ connect }) => {
    const desktop = await connect('u1');
    await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows' });

    const arrival = once(desktop, 'presence:list');
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });
    assert.equal((await arrival).devices.length, 1);

    const departure = once(desktop, 'presence:list');
    await emit(phone, 'presence:withdraw', {});
    assert.equal((await departure).devices.length, 0);
  });
});

test('request, accept, link established on both sides', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });
    const desktop = await connect('u1');
    await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows · Chrome' });

    const incoming = once(phone, 'link:incoming');
    const ack = await emit(desktop, 'link:request', { deviceId: 'dev-a' });
    assert.equal(ack.ok, true);

    const request = await incoming;
    assert.equal(request.desktopName, 'Windows · Chrome');
    assert.equal(request.expiresInMs, 30000);

    const desktopLinked = once(desktop, 'link:established');
    const phoneLinked = once(phone, 'link:established');
    await emit(phone, 'link:respond', { requestId: request.requestId, accept: true });

    assert.equal((await desktopLinked).peer.deviceId, 'dev-a');
    assert.deepEqual((await phoneLinked).examProblems, []);
  });
});

test('declining tells the desktop and frees the device', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });
    const desktop = await connect('u1');
    await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows' });

    const incoming = once(phone, 'link:incoming');
    await emit(desktop, 'link:request', { deviceId: 'dev-a' });
    const { requestId } = await incoming;

    const rejected = once(desktop, 'link:rejected');
    await emit(phone, 'link:respond', { requestId, accept: false });
    assert.equal((await rejected).deviceId, 'dev-a');

    const refreshed = await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows' });
    assert.equal(refreshed.devices[0].busy, false);
  });
});

test('exam problems reach the phone, and a photo reaches the desktop', async () => {
  await withServer(async ({ connect }) => {
    const { phone, desktop } = await linkPair(connect);

    const problems = once(phone, 'exam:problems');
    await emit(desktop, 'exam:problems', {
      problems: [{ id: 17, label: 'Задача 17', type: 'open' }],
    });
    assert.equal((await problems).problems[0].label, 'Задача 17');

    const image = 'data:image/jpeg;base64,/9j/4AAQSkZJRg==';
    const arrived = once(desktop, 'answer:submit');
    const received = once(phone, 'answer:received');
    const ack = await emit(phone, 'answer:submit', { problemId: 17, image });
    assert.equal(ack.ok, true);

    const delivered = await arrived;
    assert.equal(delivered.problemId, 17);
    assert.equal(delivered.image, image);
    assert.equal((await received).problemId, 17);
  });
});

test('a phone linking mid-exam immediately receives the cached problems', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });
    const desktop = await connect('u1');
    await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows' });

    // Desktop publishes before any phone is linked; the value is held on the
    // desktop session and replayed when a link is formed.
    await emit(desktop, 'exam:problems', { problems: [{ id: 3, label: 'Задача 3', type: 'open' }] });

    const incoming = once(phone, 'link:incoming');
    await emit(desktop, 'link:request', { deviceId: 'dev-a' });
    const { requestId } = await incoming;
    const phoneLinked = once(phone, 'link:established');
    await emit(phone, 'link:respond', { requestId, accept: true });

    assert.equal((await phoneLinked).examProblems[0].id, 3);
  });
});

test('non-open questions are filtered out of the published problem list', async () => {
  await withServer(async ({ connect }) => {
    const { phone, desktop } = await linkPair(connect);

    const problems = once(phone, 'exam:problems');
    await emit(desktop, 'exam:problems', {
      problems: [
        { id: 1, label: 'Задача 1', type: 'choice' },
        { id: 2, label: 'Задача 2', type: 'open' },
        { id: 3, label: '', type: 'open' },
      ],
    });
    const delivered = await problems;
    assert.equal(delivered.problems.length, 1);
    assert.equal(delivered.problems[0].id, 2);
  });
});

test('an oversized photo is refused', async () => {
  await withServer(async ({ connect }) => {
    const { phone } = await linkPair(connect);

    // 11 MB of base64 decodes to ~8.25 MB, over MAX_IMAGE_BYTES but still
    // under maxHttpBufferSize — so the app-level check runs and acks cleanly
    // rather than the transport silently closing the socket.
    const huge = `data:image/jpeg;base64,${'A'.repeat(11 * 1024 * 1024)}`;
    assert.deepEqual(await emit(phone, 'answer:submit', { problemId: 1, image: huge }, 20000), {
      ok: false,
      reason: 'TOO_LARGE',
    });
  });
});

test('a non-image payload is refused', async () => {
  await withServer(async ({ connect }) => {
    const { phone } = await linkPair(connect);

    assert.deepEqual(
      await emit(phone, 'answer:submit', { problemId: 1, image: 'javascript:alert(1)' }),
      { ok: false, reason: 'INVALID_PAYLOAD' }
    );
  });
});

test('an unlinked phone cannot submit a photo', async () => {
  await withServer(async ({ connect }) => {
    const phone = await connect('u1');
    await emit(phone, 'presence:announce', { deviceId: 'dev-a', name: 'iPhone', platform: 'iPhone' });
    assert.deepEqual(
      await emit(phone, 'answer:submit', { problemId: 1, image: 'data:image/jpeg;base64,AA==' }),
      { ok: false, reason: 'NOT_LINKED' }
    );
  });
});

test('ending a link notifies both sides and frees the device', async () => {
  await withServer(async ({ connect }) => {
    const { phone, desktop } = await linkPair(connect);

    const phoneEnded = once(phone, 'link:ended');
    await emit(desktop, 'link:end', {});
    assert.equal((await phoneEnded).reason, 'peer-left');

    const refreshed = await emit(desktop, 'presence:subscribe', { desktopId: 'desk-1', name: 'Windows' });
    assert.equal(refreshed.devices[0].busy, false);
  });
});

test('a companion-scoped token cannot open a socket', async () => {
  await withServer(async ({ url }) => {
    const head = b64({ alg: 'HS256', typ: 'JWT' });
    const body = b64({ sub: '1', type: 'companion', scope: 'companion' });
    const sig = crypto.createHmac('sha256', SECRET).update(`${head}.${body}`).digest('base64url');

    const socket = ioClient(url, {
      auth: { token: `${head}.${body}.${sig}` },
      transports: ['websocket'],
      reconnection: false,
    });
    const error = await new Promise((resolve) => socket.on('connect_error', resolve));
    assert.match(error.message, /UNAUTHORIZED/);
    socket.close();
  });
});
