'use strict';

require('dotenv').config();

const express = require('express');
const http = require('http');
const cors = require('cors');
const { Server } = require('socket.io');

const { buildOriginCheck } = require('./origins');
const { createAuthMiddleware } = require('./auth');
const { createRegistry } = require('./registry');
const { registerHandlers } = require('./handlers');

const JWT_SECRET = process.env.REALTIME_JWT_SECRET || process.env.SECRET_KEY || '';

if (!JWT_SECRET) {
  console.error(
    '❌ REALTIME_JWT_SECRET (or SECRET_KEY) is not set. It must match the backend ' +
    'SECRET_KEY. Exiting rather than running as a black hole that rejects every socket.'
  );
  process.exit(1);
}

const SWEEP_INTERVAL_MS = 5_000;

const createApp = () => {
  const { corsOriginCheck } = buildOriginCheck({
    corsOrigins: String(process.env.CORS_ORIGINS || '').split(',').map((v) => v.trim()),
    allowLocalNetwork: process.env.ALLOW_LOCAL_NETWORK !== 'false',
  });

  const app = express();
  app.use(cors({ origin: corsOriginCheck, credentials: true }));
  app.get('/health', (_req, res) => res.json({ ok: true, service: 'realtime-pairing' }));
  // Keep-alive endpoint — point an uptime monitor (e.g. UptimeRobot) at this
  // URL on a 5-minute interval so Render's free tier never spins down.
  app.get('/ping', (_req, res) => res.json({ ok: true, ts: Date.now() }));

  const server = http.createServer(app);
  const io = new Server(server, {
    cors: { origin: corsOriginCheck, credentials: true },
    // Must exceed MAX_IMAGE_BYTES *after* base64 expansion, or the app-level
    // TOO_LARGE check can never run: Socket.IO drops an over-budget packet by
    // closing the connection, so the phone would see a dead socket instead of
    // a useful error. 8 MB of image is ~10.7 MB of base64, hence 12 MB here.
    maxHttpBufferSize: 12 * 1024 * 1024,
  });

  io.use(createAuthMiddleware(JWT_SECRET));

  const registry = createRegistry();
  const { sweep } = registerHandlers({ io, registry });
  const sweepTimer = setInterval(sweep, SWEEP_INTERVAL_MS);
  sweepTimer.unref?.();
  io.on('close', () => clearInterval(sweepTimer));

  return { app, server, io, registry, sweep };
};

module.exports = { createApp };

if (require.main === module) {
  const PORT = Number(process.env.PORT || 3001);
  const { server } = createApp();
  server.listen(PORT, () => {
    console.log(`Realtime pairing server listening on http://127.0.0.1:${PORT}`);
  });
}
