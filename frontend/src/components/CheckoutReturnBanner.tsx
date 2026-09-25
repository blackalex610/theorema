import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { PLAN_CHANGED_EVENT, usePlan } from '../hooks/usePlan';

const POLL_MS = 2000;
const MAX_POLLS = 10;

/**
 * Shown on the dashboard after Stripe Checkout sends the browser back
 * (?upgrade=success or ?upgrade=cancelled).
 *
 * Coming back to the success URL proves nothing — anyone can visit it — so
 * Premium is only switched on by Stripe's webhook, usually a second or two
 * later. Until the server reports it, this polls the plan and says so.
 */
export default function CheckoutReturnBanner() {
  const [params, setParams] = useSearchParams();
  const outcome = params.get('upgrade');
  const { status, refresh } = usePlan();
  const [polls, setPolls] = useState(0);

  const waiting = outcome === 'success' && !status.is_premium && polls < MAX_POLLS;

  useEffect(() => {
    if (!waiting) return;
    const timer = window.setTimeout(() => {
      setPolls((n) => n + 1);
      void refresh();
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [waiting, polls, refresh]);

  useEffect(() => {
    if (outcome === 'success' && status.is_premium) {
      window.dispatchEvent(new Event(PLAN_CHANGED_EVENT));
    }
  }, [outcome, status.is_premium]);

  if (outcome !== 'success' && outcome !== 'cancelled') return null;

  const dismiss = () => {
    const next = new URLSearchParams(params);
    next.delete('upgrade');
    setParams(next, { replace: true });
  };

  let message: string;
  if (outcome === 'cancelled') message = 'Плащането е отказано. Нищо не е таксувано.';
  else if (status.is_premium) message = 'Premium е активен ⚡ Благодарим ти!';
  else if (waiting) message = 'Плащането е прието — активираме Premium…';
  else message = 'Плащането е прието. Ако Premium не се появи до минута, опресни страницата.';

  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-auto mb-4 flex max-w-5xl items-center justify-between gap-3 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-200"
    >
      <span>{message}</span>
      <button type="button" onClick={dismiss} className="shrink-0 underline" aria-label="Скрий съобщението">
        OK
      </button>
    </div>
  );
}
