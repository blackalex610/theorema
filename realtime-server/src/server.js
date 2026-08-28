require('dotenv').config();

const express = require('express');
const http = require('http');
const cors = require('cors');
const crypto = require('crypto');
const { Server } = require('socket.io');

const PORT = Number(process.env.PORT || 3001);
const app = express();

// ─── Origin allowlist ────────────────────────────────────────────────────────
// SECURITY: this used to be `origin: true` with `credentials: true`, which
// reflects *any* origin back — so any website a student visited could open an
// authenticated socket to the pairing server and read/inject room traffic.
const DEFAULT_ALLOWED_ORIGINS = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://localhost:5174',
  'http://127.0.0.1:5174',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
];

const ALLOWED_ORIGINS = String(process.env.CORS_ORIGINS || '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

const allowedOrigins = ALLOWED_ORIGINS.length ? ALLOWED_ORIGINS : DEFAULT_ALLOWED_ORIGINS;

// Phones on the LAN hit the desktop by private IP during local testing.
const LOCAL_NETWORK_ORIGIN = /^https?:\/\/(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$/;
const ALLOW_LOCAL_NETWORK = process.env.ALLOW_LOCAL_NETWORK !== 'false';

const isOriginAllowed = (origin) => {
  // Same-origin / non-browser clients send no Origin header.
  if (!origin) return true;
  if (allowedOrigins.includes(origin)) return true;
  return ALLOW_LOCAL_NETWORK && LOCAL_NETWORK_ORIGIN.test(origin);
};

const corsOriginCheck = (origin, callback) => {
  if (isOriginAllowed(origin)) return callback(null, true);
  console.warn(`❌ Blocked disallowed origin: ${origin}`);
  return callback(new Error('Origin not allowed'));
};

app.use(cors({ origin: corsOriginCheck, credentials: true }));

// ─── Handshake authentication ────────────────────────────────────────────────
// SECURITY: identity used to be a client-supplied string, so anyone could
// claim to be any user id and hijack or impersonate a pairing room. The socket
// now carries the same JWT the API uses, verified here before any event runs.
const JWT_SECRET = process.env.REALTIME_JWT_SECRET || process.env.SECRET_KEY || '';

if (!JWT_SECRET) {
  console.error(
    '❌ REALTIME_JWT_SECRET (or SECRET_KEY) is not set. It must match the backend ' +
    'SECRET_KEY. Exiting rather than running as a black hole that rejects every socket.'
  );
  process.exit(1);
}

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

app.get('/health', (_req, res) => {
  res.json({ ok: true, service: 'realtime-pairing' });
});

// Keep-alive endpoint — point an uptime monitor (e.g. UptimeRobot) at this
// URL on a 5-minute interval so Render's free tier never spins down.
app.get('/ping', (_req, res) => {
  res.json({ ok: true, ts: Date.now() });
});

const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: corsOriginCheck,
    credentials: true,
  },
  maxHttpBufferSize: 10 * 1024 * 1024, // 10 MB — matches MAX_IMAGE_BYTES ceiling
});

// Every socket must present a valid backend JWT before it can emit anything.
io.use((socket, next) => {
  const token =
    socket.handshake.auth?.token ||
    String(socket.handshake.headers.authorization || '').replace(/^Bearer\s+/i, '');

  const payload = verifyJwtHs256(token, JWT_SECRET);
  if (!payload) {
    console.warn(`❌ Rejected unauthenticated socket ${socket.id}`);
    return next(new Error('UNAUTHORIZED'));
  }

  // SECURITY: the backend also mints a *companion* JWT (type:"companion",
  // scope:"companion") for the phone-pairing flow, signed with the same
  // SECRET_KEY but via a route that requires no authentication at all
  // (POST /companion/pair). Both tokens carry a `sub` and verify with the
  // same signature check above, so without this guard a companion token —
  // obtainable by anyone — would be accepted here as full user identity.
  // Only a real backend user access token (no `type`/`scope` claim) may
  // authenticate a realtime identity socket.
  if (payload.type === 'companion' || payload.scope === 'companion') {
    console.warn(`❌ Rejected companion-scoped token on identity socket ${socket.id}`);
    return next(new Error('UNAUTHORIZED'));
  }

  // Authoritative identity — never read from the event payload again.
  socket.data.authUserId = String(payload.sub);
  return next();
});

const rooms = new Map();
// Pending room-close timers keyed by roomCode.  When the desktop disconnects
// we wait ROOM_GRACE_MS before actually tearing down the room so a brief
// page reload / network blip doesn't instantly kill every joined phone.
const roomCloseTimers = new Map();
const ROOM_GRACE_MS = 30_000;

const normalizeRoomCode = (value = '') => value.trim();
const normalizeUserId = (value = '') => String(value || '').trim();
const MAX_IMAGE_BYTES = 8 * 1024 * 1024; // Increased to 8MB for HEIC conversion overhead // Increased from 2MB to 4MB to handle JPEG conversion overhead

const normalizeActiveTestProblems = (value) => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      id: Number(item.id),
      label: String(item.label || '').trim(),
      type: item.type,
    }))
    .filter((item) => Number.isFinite(item.id) && item.label.length > 0 && item.type === 'open')
    .map((item) => ({ id: item.id, label: item.label, type: 'open' }));
};

const getPublicDevice = (device) => ({
  id: device.id,
  name: device.name,
  joinedAt: device.joinedAt,
  userAgent: device.userAgent,
});

const getRoomState = (roomCode) => {
  const room = rooms.get(roomCode);
  if (!room) return { devices: [] };
  return {
    roomCode,
    devices: Array.from(room.devices.values()).map(getPublicDevice),
  };
};

io.on('connection', (socket) => {
  socket.on('createRoom', ({ roomCode }, callback) => {
    const normalizedCode = normalizeRoomCode(roomCode);
    // Identity comes from the verified handshake JWT, not the event payload.
    const normalizedOwnerUserId = normalizeUserId(socket.data.authUserId);
    
    console.log(`🏠 createRoom request - code: "${normalizedCode}", userId: ${normalizedOwnerUserId}, socketId: ${socket.id}`);
    
    if (!/^\d{6}$/.test(normalizedCode)) {
      console.error(`❌ Invalid code format in createRoom - code: "${normalizedCode}"`);
      callback?.({ ok: false, reason: 'INVALID_CODE' });
      return;
    }
    if (!normalizedOwnerUserId) {
      console.error(`❌ Missing ownerUserId in createRoom`);
      callback?.({ ok: false, reason: 'UNAUTHORIZED' });
      return;
    }

    const existingRoom = rooms.get(normalizedCode);
    if (existingRoom && existingRoom.ownerUserId && existingRoom.ownerUserId !== normalizedOwnerUserId) {
      console.error(`❌ Account mismatch on createRoom - expected: ${existingRoom.ownerUserId}, got: ${normalizedOwnerUserId}`);
      callback?.({ ok: false, reason: 'ACCOUNT_MISMATCH', expectedUserId: existingRoom.ownerUserId });
      return;
    }
    if (existingRoom && existingRoom.desktopId && existingRoom.desktopId !== socket.id) {
      // Allow re-claim if there is a pending grace-period timer (desktop was
      // briefly disconnected and is now reconnecting with the same code).
      if (!roomCloseTimers.has(normalizedCode)) {
        console.error(`❌ Room already exists for code: "${normalizedCode}"`);
        callback?.({ ok: false, reason: 'ROOM_EXISTS' });
        return;
      }
      // Clear the pending close — desktop is back.
      clearTimeout(roomCloseTimers.get(normalizedCode));
      roomCloseTimers.delete(normalizedCode);
    }

    const room = existingRoom || {
      desktopId: socket.id,
      ownerUserId: normalizedOwnerUserId,
      devices: new Map(),
      nextDeviceNumber: 1,
      activeTestProblems: [],
    };

    room.desktopId = socket.id;
    room.ownerUserId = normalizedOwnerUserId;
    rooms.set(normalizedCode, room);
    socket.data.role = 'desktop';
    socket.data.roomCode = normalizedCode;
    socket.data.userId = normalizedOwnerUserId;
    socket.join(normalizedCode);

    console.log(`✅ Room created/claimed - code: "${normalizedCode}"`);

    callback?.({ ok: true, roomCode: normalizedCode, devices: getRoomState(normalizedCode).devices });
    socket.emit('roomState', getRoomState(normalizedCode));
  });

  socket.on('joinRoom', ({ roomCode }, callback) => {
    const normalizedCode = normalizeRoomCode(roomCode);
    // Identity comes from the verified handshake JWT, not the event payload.
    const normalizedRequesterUserId = normalizeUserId(socket.data.authUserId);
    
    console.log(`🔐 joinRoom request - code: "${normalizedCode}", userId: ${normalizedRequesterUserId}, socketId: ${socket.id}`);

    if (!/^\d{6}$/.test(normalizedCode)) {
      console.error(`❌ Invalid code format in joinRoom - code: "${normalizedCode}"`);
      callback?.({ ok: false, reason: 'INVALID_CODE' });
      return;
    }

    if (!normalizedRequesterUserId) {
      console.error(`❌ Missing requester userId in joinRoom`);
      callback?.({ ok: false, reason: 'UNAUTHORIZED' });
      return;
    }

    const room = rooms.get(normalizedCode);
    if (!room || !room.desktopId) {
      console.error(`❌ Room not found or no desktop - code: "${normalizedCode}", roomExists: ${!!room}, hasDesktop: ${room?.desktopId ? true : false}`);
      callback?.({ ok: false, reason: 'ROOM_NOT_FOUND' });
      return;
    }

    if (room.ownerUserId && room.ownerUserId !== normalizedRequesterUserId) {
      console.error(`❌ Account mismatch - expected: ${room.ownerUserId}, got: ${normalizedRequesterUserId}`);
      callback?.({ ok: false, reason: 'ACCOUNT_MISMATCH', expectedUserId: room.ownerUserId });
      return;
    }

    if (room.devices.size >= 1) {
      console.warn(`⚠️ Room full - code: "${normalizedCode}", devices: ${room.devices.size}`);
      callback?.({ ok: false, reason: 'ROOM_FULL' });
      return;
    }

    const device = {
      id: socket.id,
      name: `Phone ${room.nextDeviceNumber++}`,
      joinedAt: new Date().toISOString(),
      userAgent: socket.handshake.headers['user-agent'] || 'unknown',
    };

    room.devices.set(socket.id, device);
    socket.data.role = 'player';
    socket.data.roomCode = normalizedCode;
    socket.data.deviceId = device.id;
    socket.data.userId = normalizedRequesterUserId;
    socket.join(normalizedCode);

    console.log(`✅ Device joined room - code: "${normalizedCode}", deviceName: ${device.name}`);
    
    const payload = getPublicDevice(device);
    callback?.({ ok: true, roomCode: normalizedCode, device: payload });
    io.to(room.desktopId).emit('playerJoined', payload);
    io.to(room.desktopId).emit('roomState', getRoomState(normalizedCode));
    socket.emit('roomState', getRoomState(normalizedCode));
    if (room.activeTestProblems.length > 0) {
      socket.emit('activeTestData', { problems: room.activeTestProblems });
    }
  });

  socket.on('activeTestData', ({ problems }, callback) => {
    const roomCode = socket.data.roomCode;
    if (socket.data.role !== 'desktop' || !roomCode) {
      callback?.({ ok: false, reason: 'NOT_PAIRED' });
      return;
    }

    const room = rooms.get(roomCode);
    if (!room) {
      callback?.({ ok: false, reason: 'NOT_PAIRED' });
      return;
    }

    const normalizedProblems = normalizeActiveTestProblems(problems);
    if (!Array.isArray(problems)) {
      callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });
      return;
    }

    room.activeTestProblems = normalizedProblems;
    io.to(roomCode).emit('activeTestData', { problems: normalizedProblems });
    callback?.({ ok: true });
  });

  socket.on('sendImage', ({ dataUrl }, callback) => {
    const roomCode = socket.data.roomCode;
    console.log(`📷 sendImage received - roomCode: ${roomCode}, imageSize: ${dataUrl?.length ?? 0} bytes, format: ${dataUrl?.substring(0, 20)}`);
    
    if (socket.data.role !== 'player' || !roomCode || typeof dataUrl !== 'string' || !dataUrl.startsWith('data:image/')) {
      console.error(`❌ Invalid payload for sendImage - role: ${socket.data.role}, roomCode: ${roomCode}, format: ${dataUrl?.substring(0, 20)}`);
      callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });
      return;
    }

    const room = rooms.get(roomCode);
    if (!room || !room.desktopId) {
      console.error(`❌ Room not found for sendImage - roomCode: ${roomCode}`);
      callback?.({ ok: false, reason: 'NOT_PAIRED' });
      return;
    }

    const base64Payload = dataUrl.split(',')[1] || '';
    const approxBytes = Math.floor((base64Payload.length * 3) / 4);
    if (approxBytes > MAX_IMAGE_BYTES) {
      console.error(`❌ Image too large for sendImage - size: ${(approxBytes / 1024 / 1024).toFixed(2)} MB, max: ${(MAX_IMAGE_BYTES / 1024 / 1024).toFixed(2)} MB`);
      callback?.({ ok: false, reason: 'TOO_LARGE' });
      return;
    }

    const device = room.devices.get(socket.id);
    console.log(`✅ Forwarding quick photo to desktop - imageSize: ${(approxBytes / 1024).toFixed(2)} KB`);
    
    io.to(room.desktopId).emit('sendImage', {
      dataUrl,
      sentAt: new Date().toISOString(),
      deviceId: socket.id,
      deviceName: device?.name || 'Phone',
    });
    callback?.({ ok: true });
  });

  socket.on('submitAnswerImage', ({ problemId, image }, callback) => {
    const roomCode = socket.data.roomCode;
    console.log(`📸 submitAnswerImage received - roomCode: ${roomCode}, problemId: ${problemId}, imageSize: ${image?.length ?? 0} bytes`);
    
    if (
      socket.data.role !== 'player' ||
      !roomCode ||
      !Number.isFinite(Number(problemId)) ||
      typeof image !== 'string' ||
      !image.startsWith('data:image/')
    ) {
      console.error(`❌ Invalid payload for submitAnswerImage - role: ${socket.data.role}, roomCode: ${roomCode}, problemId: ${problemId}, imageFormat: ${image?.substring(0, 20)}`);
      callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });
      return;
    }

    const room = rooms.get(roomCode);
    if (!room || !room.desktopId) {
      console.error(`❌ Room not found or no desktop connected - roomCode: ${roomCode}`);
      callback?.({ ok: false, reason: 'NOT_PAIRED' });
      return;
    }

    const base64Payload = image.split(',')[1] || '';
    const approxBytes = Math.floor((base64Payload.length * 3) / 4);
    if (approxBytes > MAX_IMAGE_BYTES) {
      console.error(`❌ Image too large - size: ${(approxBytes / 1024 / 1024).toFixed(2)} MB, max: ${(MAX_IMAGE_BYTES / 1024 / 1024).toFixed(2)} MB`);
      callback?.({ ok: false, reason: 'TOO_LARGE' });
      return;
    }

    const normalizedProblemId = Number(problemId);
    const device = room.devices.get(socket.id);
    console.log(`✅ Forwarding answer image to desktop - problemId: ${normalizedProblemId}, imageSize: ${(approxBytes / 1024).toFixed(2)} KB`);
    
    io.to(room.desktopId).emit('submitAnswerImage', {
      problemId: normalizedProblemId,
      image,
      deviceId: socket.id,
      deviceName: device?.name || 'Phone',
      submittedAt: new Date().toISOString(),
    });

    socket.emit('answerReceived', { problemId: normalizedProblemId });
    callback?.({ ok: true });
  });

  socket.on('disconnect', () => {
    const roomCode = socket.data.roomCode;
    if (!roomCode) return;

    const room = rooms.get(roomCode);
    if (!room) return;

    if (socket.data.role === 'desktop') {
      // Don't tear down the room immediately — give the desktop ROOM_GRACE_MS
      // to reconnect (e.g. page reload, brief network drop) before we evict
      // all joined phones.
      if (roomCloseTimers.has(roomCode)) {
        clearTimeout(roomCloseTimers.get(roomCode));
      }
      const timer = setTimeout(() => {
        roomCloseTimers.delete(roomCode);
        const liveRoom = rooms.get(roomCode);
        if (liveRoom && liveRoom.desktopId === socket.id) {
          io.to(roomCode).emit('roomClosed', { roomCode });
          rooms.delete(roomCode);
        }
      }, ROOM_GRACE_MS);
      roomCloseTimers.set(roomCode, timer);
      return;
    }

    if (socket.data.role === 'player') {
      room.devices.delete(socket.id);
      if (room.desktopId) {
        io.to(room.desktopId).emit('playerLeft', { id: socket.id });
        io.to(room.desktopId).emit('roomState', getRoomState(roomCode));
      }
    }
  });
});

server.listen(PORT, () => {
  console.log(`Realtime pairing server listening on http://127.0.0.1:${PORT}`);
});