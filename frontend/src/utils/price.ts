import type { BillingPrice } from '../hooks/usePlan';

const INTERVALS: Record<string, string> = { month: 'месец', year: 'година', week: 'седмица' };

/** "4,99 € / месец" from a Stripe price, or null if it can't be shown. */
export function formatPrice(price: BillingPrice | null | undefined): string | null {
  if (!price || price.amount == null || !price.currency) return null;
  const amount = new Intl.NumberFormat('bg-BG', {
    style: 'currency',
    currency: price.currency.toUpperCase(),
  }).format(price.amount / 100);
  const interval = price.interval ? INTERVALS[price.interval] ?? price.interval : null;
  return interval ? `${amount} / ${interval}` : amount;
}
