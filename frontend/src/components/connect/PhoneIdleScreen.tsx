import React from 'react';

type Props = { deviceName: string; onDisconnect: () => void };

/**
 * The Kahoot screen: the phone is a controller, so there is deliberately
 * nothing to read here. Everything happens on the desktop.
 */
const PhoneIdleScreen: React.FC<Props> = ({ deviceName, onDisconnect }) => (
  <div className="text-center">
    <div className="mx-auto flex size-20 items-center justify-center rounded-full bg-brand-wash">
      <svg
        viewBox="0 0 24 24"
        className="size-10 text-brand"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        aria-hidden
      >
        <path d="M4 12.5l5 5L20 6.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
    <h1 className="mt-4 text-2xl font-bold text-ink">Свързан</h1>
    <p className="mt-1 text-caption text-ink-muted">{deviceName}</p>
    <p className="mt-6 text-base font-medium text-ink">Погледни екрана на компютъра.</p>
    <button
      type="button"
      onClick={onDisconnect}
      className="mt-8 h-12 w-full rounded-2xl border border-line-strong text-caption font-semibold text-ink transition-colors hover:bg-sunken"
    >
      Прекъсни
    </button>
  </div>
);

export default PhoneIdleScreen;
