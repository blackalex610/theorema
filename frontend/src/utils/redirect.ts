/**
 * Only accept a same-origin, relative path — never an absolute URL or a
 * protocol-relative one (`//evil.com`). RequireAuth stores the path a visitor
 * was bounced from in router state; without this check, that value becomes
 * an open-redirect vector the moment it reaches a query string.
 */
export function safeRedirectTarget(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  if (!raw.startsWith('/') || raw.startsWith('//')) return null;
  return raw;
}
