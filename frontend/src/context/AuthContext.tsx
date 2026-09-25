import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import apiClient from '../services/api';
import { hasValidSession } from '../utils/auth';

export type AuthUser = {
  id: number;
  name: string;
  email: string | null;
  picture: string | null;
  plan: string;
  isGuest: boolean;
  /** The account has not yet answered the age / consent step for the
   *  current version of the privacy policy and terms (see /consent). */
  consentRequired: boolean;
  ageGroup: AgeGroup | null;
};

export type AgeGroup = '14_plus' | 'under_14';

type RawUser = {
  id: number;
  name?: string | null;
  email?: string | null;
  picture?: string | null;
  plan?: string | null;
  is_guest?: boolean;
  consent_required?: boolean;
  age_group?: AgeGroup | null;
};

type SessionPayload = { access_token: string; user: RawUser };

type LinkGoogleConflict = {
  code: 'ACCOUNT_EXISTS';
  message: string;
  access_token: string;
  user: RawUser;
};

type AuthContextValue = {
  /** Derived from `user`, not a separate loading phase: hydration from
   *  localStorage is synchronous (read on the very first render), so there
   *  is no gap in which the wrong value could flash. */
  status: 'anonymous' | 'authenticated';
  user: AuthUser | null;
  userId: string | null;
  isAuthenticated: boolean;
  isGuest: boolean;
  signInWithGoogle: (credential: string) => Promise<void>;
  /** Upgrades the caller's guest account in place. On ACCOUNT_EXISTS (a
   *  different real account already owns this Google identity) it signs the
   *  caller into that existing account instead and rethrows so the UI can
   *  say the guest progress did not carry over. */
  linkGoogle: (credential: string) => Promise<void>;
  continueAsGuest: () => Promise<void>;
  signOut: () => void;
  refreshUser: () => Promise<void>;
  /** Records the age group and the matching consent (the student's own at
   *  14+, a parent's or guardian's under 14). */
  recordConsent: (ageGroup: AgeGroup, confirmed: boolean) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function normalizeUser(raw: RawUser): AuthUser {
  return {
    id: raw.id,
    name: raw.name || 'Ученик',
    email: raw.email ?? null,
    picture: raw.picture ?? null,
    plan: raw.plan || 'free',
    isGuest: Boolean(raw.is_guest),
    // A user cached before this field existed reads as "not required" until
    // refreshUser() fetches /auth/me on mount, which then asks if needed.
    consentRequired: Boolean(raw.consent_required),
    ageGroup: raw.age_group ?? null,
  };
}

function readStoredUser(): AuthUser | null {
  if (!hasValidSession()) return null;
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.id === undefined || parsed?.id === null) return null;
    return normalizeUser(parsed);
  } catch {
    return null;
  }
}

function persistSession(payload: SessionPayload): AuthUser {
  localStorage.setItem('token', payload.access_token);
  // Store the raw (snake_case) API shape, never the normalized one — this
  // used to store the normalized camelCase object, so readStoredUser's call
  // to normalizeUser() on the *next* load read raw.is_guest off a payload
  // that only had `isGuest`, silently got `undefined`, and every guest
  // became a false "real" user after a single reload.
  localStorage.setItem('user', JSON.stringify(payload.user));
  return normalizeUser(payload.user);
}

function clearStoredSession() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  // Scoped to the previous account; a new session should not see stale data.
  localStorage.removeItem('dashboard_cache_v1');
  localStorage.removeItem('xp_summary_cache');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser());

  const refreshUser = useCallback(async () => {
    if (!hasValidSession()) return;
    try {
      const { data } = await apiClient.get<RawUser>('/auth/me');
      // Same raw-shape rule as persistSession: store exactly what the API
      // returned, normalize only when reading it into React state.
      localStorage.setItem('user', JSON.stringify(data));
      setUser(normalizeUser(data));
    } catch {
      // A real 401 is handled by the shared response interceptor, which
      // dispatches auth:unauthorized (caught below). Any other failure here
      // (network blip) should not sign the user out.
    }
  }, []);

  useEffect(() => {
    // Reconcile the locally-cached user against the server once on mount —
    // this is what makes a plan change or the guest→real transition show up
    // without requiring a manual reload.
    void refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      clearStoredSession();
      setUser(null);
    };
    // Cross-tab sign-out: another tab clearing `token` should clear this one.
    const onStorage = (event: StorageEvent) => {
      if (event.key !== 'token') return;
      setUser(readStoredUser());
    };
    window.addEventListener('auth:unauthorized', onUnauthorized);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener('auth:unauthorized', onUnauthorized);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const signInWithGoogle = useCallback(async (credential: string) => {
    const { data } = await apiClient.post<SessionPayload>('/auth/google', { token: credential });
    setUser(persistSession(data));
  }, []);

  const linkGoogle = useCallback(async (credential: string) => {
    try {
      const { data } = await apiClient.post<SessionPayload>('/auth/link-google', { token: credential });
      setUser(persistSession(data));
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: LinkGoogleConflict } } })?.response?.data?.detail;
      if (detail?.code === 'ACCOUNT_EXISTS') {
        setUser(persistSession({ access_token: detail.access_token, user: detail.user }));
      }
      throw error;
    }
  }, []);

  const continueAsGuest = useCallback(async () => {
    const { data } = await apiClient.post<SessionPayload>('/auth/guest');
    setUser(persistSession(data));
  }, []);

  const recordConsent = useCallback(async (ageGroup: AgeGroup, confirmed: boolean) => {
    const { data } = await apiClient.post<{ user: RawUser }>('/auth/consent', {
      age_group: ageGroup,
      confirmed,
    });
    localStorage.setItem('user', JSON.stringify(data.user));
    setUser(normalizeUser(data.user));
  }, []);

  const signOut = useCallback(() => {
    clearStoredSession();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: user ? 'authenticated' : 'anonymous',
      user,
      userId: user ? String(user.id) : null,
      isAuthenticated: user !== null,
      isGuest: Boolean(user?.isGuest),
      signInWithGoogle,
      linkGoogle,
      continueAsGuest,
      signOut,
      refreshUser,
      recordConsent,
    }),
    [user, signInWithGoogle, linkGoogle, continueAsGuest, signOut, refreshUser, recordConsent]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
