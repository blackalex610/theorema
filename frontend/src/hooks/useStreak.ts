import { useEffect, useState } from 'react';
import { withUserScope } from '../utils/userIdentity';

export interface StreakData {
  count: number;
  lastActiveDate: string | null;
  longestStreak: number;
}

const STREAK_KEY = 'app_streak_v1';

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function loadStreak(): StreakData {
  const streakKey = withUserScope(STREAK_KEY);
  try {
    const raw = localStorage.getItem(streakKey);
    if (raw) return JSON.parse(raw) as StreakData;
  } catch {
    // Unreadable or corrupt storage: start a fresh streak.
  }
  return { count: 0, lastActiveDate: null, longestStreak: 0 };
}

function computeStreak(prev: StreakData): StreakData {
  const today = todayStr();
  if (prev.lastActiveDate === today) return prev;
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
  const newCount = prev.lastActiveDate === yesterday ? prev.count + 1 : 1;
  return {
    count: newCount,
    lastActiveDate: today,
    longestStreak: Math.max(newCount, prev.longestStreak),
  };
}

export function useStreak(): StreakData {
  // Today's visit is counted while computing the initial state rather than
  // by a setState inside an effect, which rendered twice to show one value.
  const [streak] = useState<StreakData>(() => computeStreak(loadStreak()));

  useEffect(() => {
    try {
      localStorage.setItem(withUserScope(STREAK_KEY), JSON.stringify(streak));
    } catch {
      // Storage full or blocked (private mode): the streak just isn't saved.
    }
  }, [streak]);

  return streak;
}
