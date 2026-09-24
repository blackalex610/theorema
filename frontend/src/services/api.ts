import axios from 'axios';
import { logApiFailure } from '../utils/errorLogger';
import { hasValidSession } from '../utils/auth';
import { API_BASE_URL } from '../config/api';

export { API_BASE_URL };

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 12000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const failedUrl: string = error?.config?.url || '';
    if (!failedUrl.includes('/log-error')) {
      logApiFailure(error, {
        route: typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : undefined,
        method: error?.config?.method,
        url: failedUrl,
        status: error?.response?.status,
      });
    }

    if (error.response?.status === 401) {
      // Skip the auth bootstrap calls themselves — a 401 from /auth/google or
      // /auth/guest means "that credential didn't work", not "your session
      // expired", and those pages handle their own error state.
      const isAuthBootstrap = /\/auth\/(google|guest|link-google)$/.test(failedUrl);
      // Only react when the client believed the session was still good. A
      // token that was already expired client-side has nothing left to
      // "yank" — hasValidSession() already cleared it — so a background poll
      // hitting this after the fact should not force-navigate someone away
      // from what they're doing (e.g. mid-exam).
      if (!isAuthBootstrap && hasValidSession()) {
        // A full page reload here (the old behavior) destroys React state —
        // in particular the in-progress NVO exam answers. AuthContext listens
        // for this event and clears the session without reloading; RequireAuth
        // then does a client-side redirect that preserves everything else.
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.dispatchEvent(new Event('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

type ApiErrorLike = { response?: { status?: number; data?: { detail?: unknown } } };

const asApiError = (error: unknown): ApiErrorLike | undefined =>
  typeof error === 'object' && error !== null ? (error as ApiErrorLike) : undefined;

/** The `detail` field of an API error response, if the error has one. */
export function apiErrorDetail(error: unknown): unknown {
  return asApiError(error)?.response?.data?.detail;
}

/**
 * A human-readable message for an API error: the server's `detail` when it is
 * a string, its `detail.message` when it is an object (plan limits, rate
 * limits), otherwise `fallback`. Rendering `detail` directly used to put an
 * object into JSX whenever the server sent a structured error.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = apiErrorDetail(error);
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (typeof detail === 'object' && detail !== null) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) return message;
  }
  return fallback;
}

// Emit a custom event when a plan limit is hit so any component can react
export function isLimitError(error: unknown): boolean {
  const detail = apiErrorDetail(error) as { code?: unknown } | undefined;
  return asApiError(error)?.response?.status === 429 && detail?.code === 'LIMIT_REACHED';
}

export function getLimitErrorDetail(error: unknown): { feature: string; message: string } | null {
  if (!isLimitError(error)) return null;
  const detail = apiErrorDetail(error) as { feature: string; message: string };
  return { feature: detail.feature, message: detail.message };
}

export default apiClient;
