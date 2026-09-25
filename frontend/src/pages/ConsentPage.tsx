import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { WarningCircleIcon } from '@phosphor-icons/react';

import { useAuth, type AgeGroup } from '../context/AuthContext';
import { apiErrorMessage } from '../services/api';
import { safeRedirectTarget } from '../utils/redirect';

/**
 * The one-time age and consent step (backend: app/services/consent.py).
 *
 * Bulgaria's digital age of consent is 14. At 14 or over the student accepts
 * the documents themselves; under 14 a parent or guardian has to. RequireAuth
 * sends every signed-in account here until it has answered for the current
 * version of the privacy policy and terms, then this page sends it on to
 * wherever it was going.
 */
const ConsentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, recordConsent, signOut } = useAuth();
  const [ageGroup, setAgeGroup] = useState<AgeGroup | null>(user?.ageGroup ?? null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const from = safeRedirectTarget((location.state as { from?: string } | null)?.from);
  const next = from && !from.startsWith('/consent') ? from : '/dashboard';

  const chooseAge = (value: AgeGroup) => {
    setAgeGroup(value);
    // The checkbox means something different for each answer.
    setConfirmed(false);
    setError('');
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ageGroup || !confirmed) return;
    setBusy(true);
    setError('');
    try {
      await recordConsent(ageGroup, confirmed);
      navigate(next, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, 'Не успяхме да запазим отговора. Опитай пак след малко.'));
    } finally {
      setBusy(false);
    }
  };

  const documents = (
    <>
      <Link to="/terms" target="_blank" rel="noreferrer" className="text-brand-ink underline">
        Условията за ползване
      </Link>{' '}
      и{' '}
      <Link to="/privacy" target="_blank" rel="noreferrer" className="text-brand-ink underline">
        Политиката за поверителност
      </Link>
    </>
  );

  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-5" noValidate>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">Преди да започнеш</h1>
          <p className="text-sm text-ink-muted">
            Един въпрос, само веднъж. Така знаем, че данните ти се обработват със съгласие,
            както изисква законът.
          </p>
        </div>

        <fieldset className="space-y-2">
          <legend className="mb-2 font-medium">На колко години си?</legend>
          {(
            [
              ['14_plus', 'На 14 или повече години съм'],
              ['under_14', 'Под 14 години съм'],
            ] as const
          ).map(([value, label]) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 has-[:checked]:border-brand-ink"
            >
              <input
                type="radio"
                name="age_group"
                value={value}
                checked={ageGroup === value}
                onChange={() => chooseAge(value)}
              />
              {label}
            </label>
          ))}
        </fieldset>

        {ageGroup === '14_plus' && (
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span>Прочетох и приемам {documents}.</span>
          </label>
        )}

        {ageGroup === 'under_14' && (
          <div className="space-y-3 rounded-lg border p-4">
            <p className="font-medium">За родител или настойник</p>
            <p className="text-sm text-ink-muted">
              Под 14 години профилът може да се използва само със съгласието на родител или
              настойник. Моля, дай устройството на родителя си.
            </p>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                Аз съм родител или настойник на ученика. Прочетох {documents} и давам съгласие
                детето ми да използва Smart NVO, включително снимките на решенията му да се
                проверяват автоматично с изкуствен интелект.
              </span>
            </label>
          </div>
        )}

        {error && (
          <p role="alert" className="flex items-start gap-2 text-sm text-red-600">
            <WarningCircleIcon weight="fill" aria-hidden="true" className="mt-px size-4 shrink-0" />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={!ageGroup || !confirmed || busy}
          className="w-full rounded-lg border p-3 font-medium disabled:opacity-60"
        >
          {busy ? 'Момент…' : 'Продължи'}
        </button>

        <p className="text-center text-xs text-ink-muted">
          Не си ти?{' '}
          <button type="button" onClick={signOut} className="underline">
            Изход
          </button>
        </p>
      </form>
    </main>
  );
};

export default ConsentPage;
