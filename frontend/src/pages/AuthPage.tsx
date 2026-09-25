import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { CredentialResponse } from '@react-oauth/google';
import { WarningCircleIcon } from '@phosphor-icons/react';

import GoogleAuthButton from '../components/auth/GoogleAuthButton';
import { useAuth } from '../context/AuthContext';
import { trackEvent } from '../services/analytics';
import { apiErrorDetail } from '../services/api';
import { safeRedirectTarget } from '../utils/redirect';

/**
 * What to tell the student when signing in fails: the server's own message
 * when it sends one ({code, message} — those are written in Bulgarian, e.g.
 * the rate limiter's), otherwise the fallback. Never the Error's own
 * message: for a failed request that is axios' English "Request failed with
 * status code 429".
 */
function signInErrorMessage(error: unknown, fallback: string): string {
  const detail = apiErrorDetail(error);
  const message = typeof detail === 'object' && detail !== null ? (detail as { message?: unknown }).message : null;
  return typeof message === 'string' && message.trim() ? message : fallback;
}

/**
 * The entire signed-out experience: two buttons, both real.
 *
 * Styling is deliberately absent — see PRODUCTION_ROADMAP.md — this page's
 * job right now is correctness (real sessions, real redirects), not looks.
 */
const AuthPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { status, isGuest, signInWithGoogle, linkGoogle, continueAsGuest } = useAuth();
  const [busy, setBusy] = useState<null | 'google' | 'guest'>(null);
  const [error, setError] = useState('');

  const next = safeRedirectTarget((location.state as { from?: string } | null)?.from) ?? '/dashboard';

  // A signed-in real (non-guest) user never needs to see this page. A guest
  // DOES stay here — this is also where they upgrade to a real account via
  // the Google button below (linkGoogle instead of signInWithGoogle).
  useEffect(() => {
    if (status === 'authenticated' && !isGuest) navigate(next, { replace: true });
  }, [status, isGuest, next, navigate]);

  const onGuest = async () => {
    setBusy('guest');
    setError('');
    try {
      await continueAsGuest();
      trackEvent('login', { method: 'guest' });
      navigate(next, { replace: true });
    } catch (e) {
      setError(signInErrorMessage(e, 'Влизането като гост не успя. Опитай пак след малко.'));
    } finally {
      setBusy(null);
    }
  };

  const onGoogle = async (response: CredentialResponse) => {
    if (!response.credential) return;
    setBusy('google');
    setError('');
    try {
      if (isGuest) {
        await linkGoogle(response.credential);
      } else {
        await signInWithGoogle(response.credential);
      }
      trackEvent('login', { method: 'google' });
      navigate(next, { replace: true });
    } catch (e) {
      const conflict = (e as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail;
      if (conflict?.code === 'ACCOUNT_EXISTS') {
        // linkGoogle already signed the caller into the existing account.
        setError('Вече има профил с този Google акаунт — влязохте в него. Прогресът като гост не се пренесе.');
        navigate(next, { replace: true });
      } else {
        setError(signInErrorMessage(e, 'Входът не мина. Опитай отново след малко.'));
      }
    } finally {
      setBusy(null);
    }
  };

  if (status === 'authenticated' && !isGuest) return null;

  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold">Smart NVO</h1>

        {isGuest ? (
          <p className="text-sm text-ink-muted">Влез с Google, за да запазиш прогреса си.</p>
        ) : null}

        {!isGuest && (
          <button
            type="button"
            onClick={onGuest}
            disabled={busy !== null}
            className="w-full rounded-lg border p-3 disabled:opacity-60"
          >
            {busy === 'guest' ? 'Момент…' : 'Продължи като гост'}
          </button>
        )}

        <GoogleAuthButton
          label={isGuest ? 'Запази прогреса си с Google' : 'Влез с Google'}
          loading={busy === 'google'}
          onSuccess={onGoogle}
          onError={() => setError('Google не отговори. Провери връзката и опитай пак.')}
        />

        {error && (
          <p role="alert" className="flex items-start gap-2 text-sm text-red-600">
            <WarningCircleIcon weight="fill" aria-hidden="true" className="mt-px size-4 shrink-0" />
            {error}
          </p>
        )}

        {/* Consent happens here, so the documents have to be here too — and
            Bulgaria's digital age of consent is 14, which covers most of the
            5th and 6th graders this product is aimed at. */}
        <p className="pt-2 text-xs leading-relaxed text-ink-muted">
          С влизането приемаш{' '}
          <Link to="/terms" className="text-brand-ink underline">
            Условията за ползване
          </Link>{' '}
          и{' '}
          <Link to="/privacy" className="text-brand-ink underline">
            Политиката за поверителност
          </Link>
          . Ако си на по-малко от 14 години, след входа ще помолим родител или настойник да
          потвърди съгласието си.
        </p>
      </div>
    </main>
  );
};

export default AuthPage;
