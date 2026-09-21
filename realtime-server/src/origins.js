'use strict';

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

// Phones on the LAN reach the desktop by private IP during local testing.
const LOCAL_NETWORK_ORIGIN =
  /^https?:\/\/(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$/;

const buildOriginCheck = ({ corsOrigins = [], allowLocalNetwork = true } = {}) => {
  const configured = corsOrigins.filter(Boolean);
  const allowed = configured.length ? configured : DEFAULT_ALLOWED_ORIGINS;

  const isOriginAllowed = (origin) => {
    // Same-origin and non-browser clients send no Origin header.
    if (!origin) return true;
    if (allowed.includes(origin)) return true;
    return allowLocalNetwork && LOCAL_NETWORK_ORIGIN.test(origin);
  };

  const corsOriginCheck = (origin, callback) => {
    if (isOriginAllowed(origin)) return callback(null, true);
    console.warn(`❌ Blocked disallowed origin: ${origin}`);
    return callback(new Error('Origin not allowed'));
  };

  return { isOriginAllowed, corsOriginCheck, allowedOrigins: allowed };
};

module.exports = { buildOriginCheck, DEFAULT_ALLOWED_ORIGINS, LOCAL_NETWORK_ORIGIN };
