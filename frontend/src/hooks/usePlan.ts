import { useState, useEffect, useCallback } from 'react';
import apiClient from '../services/api';

export interface UsageCounter {
  used: number;
  limit: number;
  remaining: number;
}

export interface PlanStatus {
  plan: 'free' | 'premium';
  is_premium: boolean;
  days_since_signup: number;
  usage: {
    ai_exercises: UsageCounter;
    ai_chat: UsageCounter;
    ai_theory: UsageCounter;
    nvo_exams: UsageCounter;
    image_scans: UsageCounter;
  };
}

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
  }, [refresh]);

  const upgrade = async () => {
    await apiClient.post('/plan/upgrade');
    await refresh();
  };

  return { status, loading, refresh, upgrade };
}
