import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './AuthContext';
import {
  deleteSavedProblem,
  listSavedRefs,
  refKey,
  saveProblem,
  type SavedProblemSnapshot,
  type SavedProblemSource,
} from '../services/savedProblems';

interface ToggleInput {
  source: SavedProblemSource;
  sourceRef: string;
  /** Called at toggle time so the snapshot captures the student's current answer. */
  buildSnapshot: () => SavedProblemSnapshot;
}

interface SavedProblemsContextValue {
  isSaved: (source: SavedProblemSource, sourceRef: string) => boolean;
  toggle: (input: ToggleInput) => Promise<void>;
  savedCount: number;
  error: string | null;
  clearError: () => void;
  refresh: () => Promise<void>;
}

const SavedProblemsContext = createContext<SavedProblemsContextValue | null>(null);

export const SavedProblemsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  // ref key -> saved row id. The id is what DELETE needs.
  const [refs, setRefs] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setRefs({});
      return;
    }
    try {
      setRefs(await listSavedRefs());
    } catch {
      // A failed refresh only means buttons render as unsaved; saving still works.
      setRefs({});
    }
  }, [isAuthenticated]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!isAuthenticated) {
        setRefs({});
        return;
      }
      try {
        const loaded = await listSavedRefs();
        if (!cancelled) setRefs(loaded);
      } catch {
        if (!cancelled) setRefs({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  const isSaved = useCallback(
    (source: SavedProblemSource, sourceRef: string) => refKey(source, sourceRef) in refs,
    [refs]
  );

  const toggle = useCallback(
    async ({ source, sourceRef, buildSnapshot }: ToggleInput) => {
      const key = refKey(source, sourceRef);
      const existingId = refs[key];
      setError(null);

      if (existingId !== undefined) {
        // Optimistic: drop it immediately, restore if the request fails.
        setRefs((current) => {
          const next = { ...current };
          delete next[key];
          return next;
        });
        try {
          await deleteSavedProblem(existingId);
        } catch {
          setRefs((current) => ({ ...current, [key]: existingId }));
          setError('Неуспешно премахване. Опитай отново.');
        }
        return;
      }

      try {
        const saved = await saveProblem({
          source,
          source_ref: sourceRef,
          snapshot: buildSnapshot(),
        });
        setRefs((current) => ({ ...current, [key]: saved.id }));
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
        setError(
          status === 409 && typeof detail === 'string'
            ? detail
            : 'Неуспешно запазване. Опитай отново.'
        );
      }
    },
    [refs]
  );

  const value = useMemo<SavedProblemsContextValue>(
    () => ({
      isSaved,
      toggle,
      savedCount: Object.keys(refs).length,
      error,
      clearError: () => setError(null),
      refresh,
    }),
    [isSaved, toggle, refs, error, refresh]
  );

  return <SavedProblemsContext.Provider value={value}>{children}</SavedProblemsContext.Provider>;
};

export function useSavedProblems(): SavedProblemsContextValue {
  const context = useContext(SavedProblemsContext);
  if (!context) {
    throw new Error('useSavedProblems must be used within a SavedProblemsProvider');
  }
  return context;
}
