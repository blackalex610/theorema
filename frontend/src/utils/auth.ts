/**
 * Client-side session helpers.
 *
 * These are a UX guard only — they decide what to render, never what a user is
 * allowed to do. Every protected resource is enforced server-side; a tampered
 * localStorage token gets a 401 from the API regardless of what this returns.
 */

interface JwtPayload {
  exp?: number;
  sub?: string;
}

/** Decode a JWT payload without verifying it (verification is the server's job). */
function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return localStorage.getItem('token');
}

/**
 * True when a structurally valid, unexpired token is stored.
 *
 * Expired tokens are cleared eagerly so the user lands on /login instead of
 * seeing a protected page flash and then 401 out of every request on it.
 */
export function hasValidSession(): boolean {
  const token = getToken();
  if (!token) return false;

  const payload = decodeJwtPayload(token);
  if (!payload) {
    localStorage.removeItem('token');
    return false;
  }

  if (typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now()) {
    localStorage.removeItem('token');
    return false;
  }

  return true;
}
