import { useState, useEffect, useCallback } from 'react';
import apiClient from '../services/api';

export interface UsageCounter {
  used: number;
  limit: number;
  remaining: number;
}

export interface BillingPrice {
  /** In the currency's minor unit (cents), as Stripe reports it. */
  amount: number | null;
  currency: string | null;
  interval: string | null;
}

export interface BillingInfo {
  enabled: boolean;
  can_subscribe: boolean;
  can_manage: boolean;
  price: BillingPrice | null;
  premium_until: string | null;
  status: string | null;
}

export interface PlanStatus {
  plan: 'free' | 'premium';
  is_premium: boolean;
  days_since_signup: number;
  billing?: BillingInfo;
  usage: {
    ai_exercises: UsageCounter;
    ai_chat: UsageCounter;
    ai_theory: UsageCounter;
    nvo_exams: UsageCounter;
    image_scans: UsageCounter;
  };
}

export const PLAN_CHANGED_EVENT = 'plan:changed';

const DEFAULT_STATUS: PlanStatus = {
  plan: 'free',
  is_premium: false,
  days_since_signup: 0,
  usage: {
    ai_exercises: { used: 0, limit: 5, remaining: 5 },
    ai_chat:      { used: 0, limit: 10, remaining: 10 },
    ai_theory:    { used: 0, limit: 12, remaining: 12 },
    nvo_exams:    { used: 0, limit: 1,  remaining: 1  },
    image_scans:  { used: 0, limit: 2,  remaining: 2  },
  },
};

export function usePlan() {
  const [status, setStatus] = useState<PlanStatus>(DEFAULT_STATUS);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    setLoading(true);
    try {
      const res = await apiClient.get<PlanStatus>('/plan/status');
      setStatus(res.data);
    } catch {
      // silently ignore — might be unauthenticated
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Several components each hold their own copy; when one learns the plan
    // changed (e.g. returning from Stripe Checkout) they all re-read it.
    const onChanged = () => void refresh();
    window.addEventListener(PLAN_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(PLAN_CHANGED_EVENT, onChanged);
  }, [refresh]);

  /** Opens Stripe Checkout. The plan changes only once Stripe's webhook
   *  confirms payment; the browser then returns to /dashboard?upgrade=success. */
  const upgrade = async () => {
    const { data } = await apiClient.post<{ checkout_url: string }>('/plan/upgrade');
    window.location.assign(data.checkout_url);
  };

  /** Stripe's customer portal: card, invoices, cancellation. */
  const manageSubscription = async () => {
    const { data } = await apiClient.post<{ portal_url: string }>('/plan/portal');
    window.location.assign(data.portal_url);
  };

  return { status, loading, refresh, upgrade, manageSubscription };
}
