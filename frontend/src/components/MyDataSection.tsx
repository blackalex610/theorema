import React from 'react';

import { useAuth } from '../context/AuthContext';
import { deleteMyAccount, downloadMyData } from '../services/userData';

/**
 * GDPR Art. 15/20 (export) and Art. 17 (erasure), as two buttons.
 *
 * The endpoints existed before this did, which in practice meant the rights
 * did not: nobody exercises a data right by composing an HTTP DELETE. The
 * deletion path deliberately requires typing a confirmation word rather than
 * a single click — it erases the account and every row attached to it with
 * no undo, so a mis-tap must not be enough to trigger it.
 */

const CONFIRM_WORD = 'ИЗТРИЙ';

const MyDataSection: React.FC = () => {
  const { signOut } = useAuth();
  const [busy, setBusy] = React.useState<null | 'export' | 'delete'>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [confirmText, setConfirmText] = React.useState('');

  const onExport = async () => {
    setBusy('export');
    setError(null);
    try {
      await downloadMyData();
    } catch {
      setError('Изтеглянето не стана. Опитай пак след малко.');
    } finally {
      setBusy(null);
    }
  };

  const onDelete = async () => {
    setBusy('delete');
    setError(null);
    try {
      await deleteMyAccount();
      // The token is dead server-side now; drop the local session too so the
      // app doesn't keep rendering a signed-in shell for an account that no
      // longer exists.
      signOut();
    } catch {
      setError('Изтриването не стана. Опитай пак след малко.');
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Изтегли данните ми
        </p>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
          Сваля файл с всичко, което пазим за теб: профил, напредък, точки, резултати от
          пробни изпити и подадени доклади.
        </p>
        <button
          type="button"
          onClick={onExport}
          disabled={busy !== null}
          className="mt-3 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {busy === 'export' ? 'Подготвяне…' : 'Изтегли данните ми'}
        </button>
      </div>

      <div className="rounded-2xl border border-red-200 bg-red-50/60 p-4 dark:border-red-900/50 dark:bg-red-950/20">
        <p className="text-sm font-semibold text-red-900 dark:text-red-200">Изтрий профила</p>
        <p className="mt-1 text-xs text-red-800/80 dark:text-red-300/80">
          Премахва профила и целия напредък — окончателно и без връщане назад.
        </p>

        {!confirmOpen ? (
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={busy !== null}
            className="mt-3 rounded-xl border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-100 disabled:opacity-60 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
          >
            Изтрий профила
          </button>
        ) : (
          <div className="mt-3 space-y-2">
            <label className="block text-xs font-medium text-red-900 dark:text-red-200">
              Напиши <strong>{CONFIRM_WORD}</strong>, за да потвърдиш:
              <input
                type="text"
                value={confirmText}
                onChange={(event) => setConfirmText(event.target.value)}
                autoComplete="off"
                className="mt-1 w-full rounded-lg border border-red-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-red-500 focus:ring-2 focus:ring-red-200 dark:border-red-800 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onDelete}
                disabled={confirmText.trim() !== CONFIRM_WORD || busy !== null}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === 'delete' ? 'Изтриване…' : 'Изтрий окончателно'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmOpen(false);
                  setConfirmText('');
                }}
                disabled={busy !== null}
                className="rounded-xl px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-60 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Отказ
              </button>
            </div>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs font-medium text-red-700 dark:text-red-300">
          {error}
        </p>
      )}

      <p className="text-[11px] text-slate-500 dark:text-slate-400">
        Повече за това какви данни пазим и защо:{' '}
        <a href="/privacy" target="_blank" rel="noreferrer" className="underline">
          Политика за поверителност
        </a>
        .
      </p>
    </div>
  );
};

export default MyDataSection;
