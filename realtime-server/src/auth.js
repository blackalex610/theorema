'use strict';

const crypto = require('crypto');

/** Verify an HS256 JWT with the built-in crypto module (no extra dependency). */
const verifyJwtHs256 = (token, secret) => {
  if (!token || !secret) return null;
  const parts = String(token).split('.');
  if (parts.length !== 3) return null;
  const [headerPart, payloadPart, signaturePart] = parts;

  let header;
  try {
    header = JSON.parse(Buffer.from(headerPart, 'base64url').toString('utf8'));
  } catch {
    return null;
  }
  // Reject alg:none and algorithm-confusion attempts outright.
  if (!header || header.alg !== 'HS256') return null;

  const expected = crypto
    .createHmac('sha256', secret)
    .update(`${headerPart}.${payloadPart}`)
    .digest('base64url');
  const given = Buffer.from(signaturePart);
  const want = Buffer.from(expected);
  if (given.length !== want.length || !crypto.timingSafeEqual(given, want)) return null;

  let payload;
  try {
    payload = JSON.parse(Buffer.from(payloadPart, 'base64url').toString('utf8'));
  } catch {
    return null;
  }
  if (typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now()) return null;
  if (!payload.sub) return null;
  return payload;
};

/**
 * Every socket must present a valid backend user token before it can emit.
 *
 * SECURITY: the backend also mints a *companion* JWT (type:"companion",
 * scope:"companion") for the legacy phone-pairing flow, signed with the same
 * SECRET_KEY but via a route that requires no authentication at all
 * (POST /companion/pair). Both tokens carry a `sub` and verify with the same
 * signature check above, so without this guard a companion token — obtainable
 * by anyone — would be accepted here as full user identity.
 */
const createAuthMiddleware = (secret) => (socket, next) => {
  const token =
    socket.handshake.auth?.token ||
    String(socket.handshake.headers.authorization || '').replace(/^Bearer\s+/i, '');

  const payload = verifyJwtHs256(token, secret);
  if (!payload) {
    console.warn(`❌ Rejected unauthenticated socket ${socket.id}`);
    return next(new Error('UNAUTHORIZED'));
  }

  if (payload.type === 'companion' || payload.scope === 'companion') {
    console.warn(`❌ Rejected companion-scoped token on identity socket ${socket.id}`);
    return next(new Error('UNAUTHORIZED'));
  }

  // Authoritative identity — never read from an event payload again.
  socket.data.authUserId = String(payload.sub);
  return next();
};

module.exports = { verifyJwtHs256, createAuthMiddleware };
