import React from 'react';
import { OPEN_SETTINGS_MODAL_EVENT } from '../context/SettingsContext';
import { trackEvent } from '../services/analytics';

interface UpgradePromptProps {
  feature?: string;
  message?: string;
  limit?: number;
  onClose?: () => void;
  inline?: boolean; // true = card inside page, false = modal overlay
}

const DEFAULT_MESSAGES: Record<string, string> = {
  ai_exercises: 'Достигнахте дневния лимит от 5 AI задачи.',
  ai_chat:      'Достигнахте дневния лимит от 10 AI съобщения.',
  ai_theory:    'Достигнахте дневния лимит от 12 AI теория генерации.',
  nvo_exams:    'Достигнахте дневния лимит от 1 НВО изпит.',
  image_scans:  'Достигнахте дневния лимит от 2 снимки.',
};

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  feature,
  message,
  onClose,
  inline = false,
}) => {
  const displayMessage =
    message ??
    (feature ? DEFAULT_MESSAGES[feature] : undefined) ??
    'Достигнахте дневния лимит.';

  const handleUpgrade = () => {
    trackEvent('premium_clicked', {
      feature: feature ?? null,
      placement: inline ? 'inline_prompt' : 'modal_prompt',
    });
    window.location.hash = 'upgrade';
    window.dispatchEvent(new CustomEvent(OPEN_SETTINGS_MODAL_EVENT));
    if (onClose) onClose();
  };

  const card = (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:border-amber-700/40 dark:bg-amber-900/20 p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">⚡</span>
          <div>
            <p className="font-bold text-amber-900 dark:text-amber-200 text-sm">Лимитът е достигнат</p>
            <p className="text-xs text-amber-700 dark:text-amber-300 mt-0.5">{displayMessage}</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-amber-400 hover:text-amber-600 dark:hover:text-amber-200 text-lg leading-none"
            aria-label="Затвори"
          >
            ×
          </button>
        )}
      </div>

      <div className="rounded-xl border border-amber-200 bg-white dark:border-amber-700/30 dark:bg-slate-900/60 p-3 flex flex-col gap-1.5">
        <p className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wider">Premium включва:</p>
        {[
          '✓ Неограничени AI задачи всеки ден',
          '✓ Неограничен AI чат',
          '✓ Неограничени НВО изпити',
          '✓ Неограничени снимки за проверка',
          '✓ Пълна история и аналитика',
        ].map((f) => (
          <p key={f} className="text-xs text-slate-600 dark:text-slate-300">{f}</p>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleUpgrade}
          className="flex-1 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2.5 text-sm font-bold text-white shadow hover:from-amber-600 hover:to-orange-600 transition-all"
        >
          Надгради до Premium →
        </button>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            По-късно
          </button>
        )}
      </div>

      <p className="text-[10px] text-center text-slate-400 dark:text-slate-500">
        Лимитите се нулират всяка полунощ. Безплатният план: 5 задачи · 10 чат · 1 НВО · 2 снимки на ден.
      </p>
    </div>
  );

  if (inline) return card;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-sm">{card}</div>
    </div>
  );
};

export default UpgradePrompt;
