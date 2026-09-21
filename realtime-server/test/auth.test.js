'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('crypto');

const { buildOriginCheck } = require('../src/origins');
const { verifyJwtHs256, createAuthMiddleware } = require('../src/auth');

const SECRET = 'test-secret';

const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');

const signToken = (payload, { secret = SECRET, alg = 'HS256' } = {}) => {
  const head = b64({ alg, typ: 'JWT' });
  const body = b64(payload);
  const sig = crypto.createHmac('sha256', secret).update(`${head}.${body}`).digest('base64url');
  return `${head}.${body}.${sig}`;
};

test('origin check allows the configured list and private networks', () => {
  const { isOriginAllowed } = buildOriginCheck({
    corsOrigins: ['https://app.example.com'],
    allowLocalNetwork: true,
  });

  assert.equal(isOriginAllowed(undefined), true, 'non-browser clients send no Origin');
  assert.equal(isOriginAllowed('https://app.example.com'), true);
  assert.equal(isOriginAllowed('http://192.168.1.40:5173'), true);
  assert.equal(isOriginAllowed('https://evil.example.net'), false);
});

test('origin check can refuse private networks', () => {
  const { isOriginAllowed } = buildOriginCheck({
    corsOrigins: ['https://app.example.com'],
    allowLocalNetwork: false,
  });
  assert.equal(isOriginAllowed('http://192.168.1.40:5173'), false);
});

test('verifyJwtHs256 accepts a well-formed token and returns its payload', () => {
  const payload = verifyJwtHs256(signToken({ sub: '42' }), SECRET);
  assert.equal(payload.sub, '42');
});

test('verifyJwtHs256 rejects tampering, alg confusion, expiry and missing sub', () => {
  assert.equal(verifyJwtHs256(signToken({ sub: '42' }, { secret: 'wrong' }), SECRET), null);
  assert.equal(verifyJwtHs256(signToken({ sub: '42' }, { alg: 'none' }), SECRET), null);
  assert.equal(verifyJwtHs256(signToken({ sub: '42', exp: 1 }), SECRET), null);
  assert.equal(verifyJwtHs256(signToken({ nosub: true }), SECRET), null);
  assert.equal(verifyJwtHs256('not.a.jwt', SECRET), null);
  assert.equal(verifyJwtHs256('', SECRET), null);
});

const runMiddleware = (token) =>
  new Promise((resolve) => {
    const socket = { id: 's1', handshake: { auth: { token }, headers: {} }, data: {} };
    createAuthMiddleware(SECRET)(socket, (err) => resolve({ err, socket }));
  });

test('auth middleware sets authUserId from the verified token only', async () => {
  const { err, socket } = await runMiddleware(signToken({ sub: '42' }));
  assert.equal(err, undefined);
  assert.equal(socket.data.authUserId, '42');
});

test('auth middleware rejects companion-scoped tokens', async () => {
  // POST /companion/pair is unauthenticated and signs with the same secret, so
  // a companion token must never buy a real user identity here.
  const byType = await runMiddleware(signToken({ sub: '42', type: 'companion' }));
  assert.match(byType.err.message, /UNAUTHORIZED/);

  const byScope = await runMiddleware(signToken({ sub: '42', scope: 'companion' }));
  assert.match(byScope.err.message, /UNAUTHORIZED/);
});

test('auth middleware rejects a missing token', async () => {
  const { err } = await runMiddleware('');
  assert.match(err.message, /UNAUTHORIZED/);
});
