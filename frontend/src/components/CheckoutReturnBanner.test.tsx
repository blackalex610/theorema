import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CheckoutReturnBanner from './CheckoutReturnBanner';

const plan = vi.hoisted(() => ({ isPremium: false, refresh: vi.fn() }));
vi.mock('../hooks/usePlan', () => ({
  PLAN_CHANGED_EVENT: 'plan:changed',
  usePlan: () => ({ status: { is_premium: plan.isPremium }, refresh: plan.refresh }),
}));

const renderAt = (search: string) =>
  render(
    <MemoryRouter initialEntries={[`/dashboard${search}`]}>
      <CheckoutReturnBanner />
    </MemoryRouter>
  );

describe('CheckoutReturnBanner', () => {
  beforeEach(() => {
    plan.isPremium = false;
    plan.refresh.mockReset();
  });

  it('renders nothing on an ordinary visit', () => {
    renderAt('');
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('waits for the webhook instead of trusting the success URL', () => {
    vi.useFakeTimers();
    renderAt('?upgrade=success');
    expect(screen.getByRole('status')).toHaveTextContent('активираме Premium');
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(plan.refresh).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('confirms once the server reports Premium', () => {
    plan.isPremium = true;
    renderAt('?upgrade=success');
    expect(screen.getByRole('status')).toHaveTextContent('Premium е активен');
  });

  it('says nothing was charged after a cancelled checkout', () => {
    renderAt('?upgrade=cancelled');
    expect(screen.getByRole('status')).toHaveTextContent('Нищо не е таксувано');
  });
});
