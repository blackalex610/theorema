import { API_BASE_URL as API_URL } from '../config/api';

type LogLevel = 'info' | 'warning' | 'error';

type ErrorContext = {
  route?: string;
  user_id?: string;
  timestamp?: string;
  level?: LogLevel;
  source?: string;
  [key: string]: unknown;
};

const SENSITIVE_KEYS = [
  'password',
  'token',
  'access_token',
  'refresh_token',
  'authorization',
  'api_key',
  'secret',
  'cookie',
];

function getCurrentUserId(): string | undefined {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    return String(parsed?.id || parsed?.email || parsed?.sub || '');
  } catch {
    return undefined;
  }
}

function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeValue);
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEYS.includes(k.toLowerCase())) {
        out[k] = '[REDACTED]';
      } else {
        out[k] = sanitizeValue(v);
      }
    }
    return out;
  }
  if (typeof value === 'string') {
    const low = value.toLowerCase();
    if (low.includes('bearer ') || low.includes('api_key') || low.includes('password')) {
      return '[REDACTED]';
    }
    return value.slice(0, 4000);
  }
  return value;
}

function createPayload(error: unknown, context: ErrorContext = {}) {
  const err = error instanceof Error ? error : new Error(String(error ?? 'Unknown error'));
  const payload = {
    message: err.message || 'Unknown error',
    stack: err.stack || undefined,
    route: context.route || `${window.location.pathname}${window.location.search}`,
    user_id: context.user_id || getCurrentUserId(),
    timestamp: context.timestamp || new Date().toISOString(),
    level: context.level || 'error',
    context: sanitizeValue(context),
  };

  if (import.meta.env.DEV) {
    // Helpful local diagnostics; disabled in production build.
    // eslint-disable-next-line no-console
    console.error('[client-error-log]', payload);
  }

  return sanitizeValue(payload) as Record<string, unknown>;
}

function postLogNonBlocking(payload: Record<string, unknown>): void {
  try {
    const endpoint = `${API_URL}/log-error`;
    const body = JSON.stringify(payload);

    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(endpoint, blob);
      return;
    }

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {
      // Logging must never break UX.
    });
  } catch {
    // Logging must never break UX.
  }
}

export function logError(error: unknown, context: ErrorContext = {}): void {
  const payload = createPayload(error, context);
  postLogNonBlocking(payload);
}

export function installGlobalErrorHandlers(): void {
  window.addEventListener('error', (event) => {
    logError(event.error || event.message, {
      source: 'window.onerror',
      level: 'error',
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logError(event.reason, {
      source: 'window.unhandledrejection',
      level: 'error',
    });
  });
}

export function logApiFailure(error: unknown, extra: Record<string, unknown> = {}): void {
  logError(error, {
    source: 'api',
    level: 'warning',
    ...extra,
  });
}
