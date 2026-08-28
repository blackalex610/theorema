/**
 * Resolves the API base URL once, shared by services/api.ts and
 * utils/errorLogger.ts (previously two copies of this exact logic that had
 * already drifted).
 */
export const resolveApiBaseUrl = (): string => {
  // The Vite dev proxy (vite.config.ts) serves /api on every hostname —
  // localhost, 127.0.0.1, and any LAN IP — identically, same-origin, so CORS
  // never enters into it. The old hostname === 'localhost' check returned
  // '/_/backend' (a path Vite does not proxy) for anything else, 404ing
  // every request opened via 127.0.0.1 or a phone on the LAN.
  if (import.meta.env.DEV) return '/api';

  const envBase = import.meta.env.VITE_API_URL;
  return envBase || '/_/backend';
};

export const API_BASE_URL = resolveApiBaseUrl();
