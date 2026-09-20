import React, { useState } from 'react';
import { useSavedProblems } from '../context/SavedProblemsContext';
import type { SavedProblemSnapshot, SavedProblemSource } from '../services/savedProblems';

interface SaveProblemButtonProps {
  source: SavedProblemSource;
  sourceRef: string;
  /** Called at click time so the snapshot captures the student's current answer. */
  buildSnapshot: () => SavedProblemSnapshot;
  className?: string;
}

const SaveProblemButton: React.FC<SaveProblemButtonProps> = ({
  source,
  sourceRef,
  buildSnapshot,
  className = '',
}) => {
  const { isSaved, toggle } = useSavedProblems();
  const [busy, setBusy] = useState(false);
  const saved = isSaved(source, sourceRef);
  const label = saved ? 'Премахни от запазените' : 'Запази задачата';

  const handleClick = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await toggle({ source, sourceRef, buildSnapshot });
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      aria-label={label}
      aria-pressed={saved}
      title={label}
      className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors disabled:opacity-50 ${
        saved
          ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-300'
          : 'border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600 dark:border-slate-700/60 dark:text-slate-500 dark:hover:text-slate-300'
      } ${className}`}
    >
      <svg
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill={saved ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  );
};

export default SaveProblemButton;
