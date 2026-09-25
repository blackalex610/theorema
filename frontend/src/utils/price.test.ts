import { describe, expect, it } from 'vitest';
import { formatPrice } from './price';

describe('formatPrice', () => {
  it('formats a monthly euro price the Bulgarian way', () => {
    const text = formatPrice({ amount: 499, currency: 'eur', interval: 'month' });
    expect(text).toMatch(/^4,99\s€ \/ месец$/);
  });

  it('is null when there is nothing trustworthy to show', () => {
    expect(formatPrice(null)).toBeNull();
    expect(formatPrice({ amount: null, currency: 'eur', interval: 'month' })).toBeNull();
  });
});
