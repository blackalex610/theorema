import { useEffect, useMemo, useRef, useState } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import { CircleNotchIcon } from '@phosphor-icons/react';

// Google will never accept a private LAN IP as an authorised JS origin
// (only registered domains and the loopback addresses are valid), so a
// phone or another machine hitting the dev server by its 192.168.x.x /
// 10.x.x.x address can never complete Google sign-in there. Detecting that
// up front and disabling the button avoids an opaque "Google didn't
// respond" failure — guest login (which has no such restriction) is the
// intended path for that kind of testing.
const PRIVATE_LAN_HOSTNAME = /^(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})$/;

function isUnregisterableGoogleOrigin(): boolean {
  if (typeof window === 'undefined') return false;
  return PRIVATE_LAN_HOSTNAME.test(window.location.hostname);
}

/**
 * Google sign-in.
 *
 * Google renders its button inside an iframe that cannot be styled, so the
 * real control is laid over a button-shaped surface of ours at near-zero
 * opacity. The iframe stays the interactive, focusable element, which keeps
 * Google's own accessible markup intact; our layer is marked aria-hidden so it
 * is never announced twice.
 */
const GoogleAuthButton: React.FC<{
  label: string;
  loading: boolean;
  loadingLabel?: string;
  onSuccess: (response: CredentialResponse) => void;
  onError: () => void;
}> = ({ label, loading, loadingLabel = 'Свързване', onSuccess, onError }) => {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(360);
  const disabled = useMemo(() => isUnregisterableGoogleOrigin(), []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => setWidth(Math.max(el.offsetWidth, 200));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (disabled) {
    return (
      <div className="w-full">
        <div
          aria-disabled="true"
          className="flex h-12 w-full items-center justify-center gap-2.5 rounded-lg border border-line bg-surface text-body font-medium text-ink-faint opacity-60"
        >
          <GoogleGlyph />
          {label}
        </div>
        <p className="mt-2 text-caption text-ink-faint">
          Google не работи на този адрес (локална мрежа). Използвай „Продължи като гост“.
        </p>
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="group relative h-12 w-full">
      <style>{`
        .google-auth-overlay { opacity: 0.011; overflow: hidden; cursor: pointer; }
        .google-auth-overlay > div { width: 100% !important; height: 100% !important; display: flex !important; }
        .google-auth-overlay iframe { width: 100% !important; min-height: 46px !important; }
      `}</style>

      <div
        aria-hidden="true"
        className="flex h-12 w-full items-center justify-center gap-2.5 rounded-lg border border-line-strong bg-surface text-body font-medium text-ink transition-colors duration-200 group-hover:border-brand group-hover:text-brand-ink"
      >
        {loading ? (
          <>
            <CircleNotchIcon className="size-4 animate-spin" />
            {loadingLabel}
          </>
        ) : (
          <>
            <GoogleGlyph />
            {label}
          </>
        )}
      </div>

      {!loading && (
        <div className="google-auth-overlay absolute inset-0 z-10">
          <GoogleLogin
            onSuccess={onSuccess}
            onError={onError}
            theme="outline"
            size="large"
            shape="rectangular"
            width={String(width)}
            text="continue_with"
          />
        </div>
      )}
    </div>
  );
};

/** Google's mark is a trademark and has to be reproduced exactly, so it stays
 *  inline rather than being approximated with an icon-set glyph. */
const GoogleGlyph: React.FC = () => (
  <svg aria-hidden="true" viewBox="0 0 24 24" className="size-[1.15em]">
    <path
      fill="#4285F4"
      d="M23.52 12.27c0-.82-.07-1.6-.21-2.36H12v4.47h6.46a5.52 5.52 0 0 1-2.4 3.62v3.01h3.88c2.27-2.09 3.58-5.17 3.58-8.74Z"
    />
    <path
      fill="#34A853"
      d="M12 24c3.24 0 5.96-1.08 7.94-2.91l-3.88-3.01c-1.08.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.28v3.1A12 12 0 0 0 12 24Z"
    />
    <path
      fill="#FBBC05"
      d="M5.29 14.28a7.2 7.2 0 0 1 0-4.56v-3.1H1.28a12 12 0 0 0 0 10.76l4.01-3.1Z"
    />
    <path
      fill="#EA4335"
      d="M12 4.77c1.76 0 3.34.61 4.59 1.8l3.44-3.44C17.95 1.18 15.24 0 12 0A12 12 0 0 0 1.28 6.62l4.01 3.1C6.23 6.88 8.88 4.77 12 4.77Z"
    />
  </svg>
);

export default GoogleAuthButton;
