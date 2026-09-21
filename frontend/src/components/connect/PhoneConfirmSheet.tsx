import React from 'react';

type Props = {
  desktopName: string;
  expiresAt: number;
  onAccept: () => void;
  onDecline: () => void;
};

const PhoneConfirmSheet: React.FC<Props> = ({ desktopName, expiresAt, onAccept, onDecline }) => {
  const [left, setLeft] = React.useState(() =>
    Math.max(0, Math.round((expiresAt - Date.now()) / 1000))
  );

  React.useEffect(() => {
    const timer = window.setInterval(
      () => setLeft(Math.max(0, Math.round((expiresAt - Date.now()) / 1000))),
      1000
    );
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  return (
    <div role="dialog" aria-modal="true" aria-label="Заявка за свързване" className="text-center">
      <h1 className="text-2xl font-bold text-ink">Заявка за свързване</h1>
      <p className="mt-3 text-base text-ink">
        <span className="font-semibold">{desktopName}</span> иска да се свърже с този телефон.
      </p>
      <p className="mt-2 text-caption text-ink-muted">
        Остават <span className="tnum">{left}</span> с
      </p>

      <div className="mt-6 space-y-3">
        <button
          type="button"
          onClick={onAccept}
          className="h-14 w-full rounded-2xl bg-brand text-base font-semibold text-white transition-transform active:scale-[0.99]"
        >
          Приеми
        </button>
        <button
          type="button"
          onClick={onDecline}
          className="h-14 w-full rounded-2xl border border-line-strong text-base font-semibold text-ink transition-colors hover:bg-sunken"
        >
          Откажи
        </button>
      </div>
    </div>
  );
};

export default PhoneConfirmSheet;
