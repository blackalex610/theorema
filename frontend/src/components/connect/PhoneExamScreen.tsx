import React from 'react';
import type { ActiveTestProblem } from '../../services/activeTest';

export type ProblemUpload = { image: string; status: 'empty' | 'sending' | 'sent' | 'failed' };

type Props = {
  problems: ActiveTestProblem[];
  uploads: Record<number, ProblemUpload>;
  error: string | null;
  onDismissError: () => void;
  onCapture: (problemId: number, file: File) => void;
};

const PhoneExamScreen: React.FC<Props> = ({
  problems,
  uploads,
  error,
  onDismissError,
  onCapture,
}) => {
  const inputRefs = React.useRef<Record<number, HTMLInputElement | null>>({});
  const sentCount = problems.filter((problem) => uploads[problem.id]?.status === 'sent').length;

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-ink">Задачи</h1>
        <span className="rounded-full bg-brand-wash px-3 py-1 text-caption font-semibold text-brand-ink">
          <span className="tnum">{sentCount}</span> от <span className="tnum">{problems.length}</span> изпратени
        </span>
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-3 flex items-start justify-between gap-2 rounded-2xl border border-danger-edge bg-danger-wash px-4 py-3 text-caption text-danger"
        >
          <span>{error}</span>
          <button type="button" onClick={onDismissError} aria-label="Затвори" className="shrink-0 font-bold">
            ✕
          </button>
        </div>
      ) : null}

      <div className="mt-4 space-y-4">
        {problems.map((problem) => {
          const upload = uploads[problem.id] ?? { image: '', status: 'empty' as const };
          const sent = upload.status === 'sent';
          const sending = upload.status === 'sending';

          return (
            <div key={problem.id} className="rounded-2xl border border-line bg-surface p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-lg font-bold text-ink">{problem.label}</p>
                {sent ? (
                  <span className="text-caption font-semibold text-brand-ink">✓ Изпратена</span>
                ) : null}
              </div>

              {upload.image ? (
                <img
                  src={upload.image}
                  alt={`Решение за ${problem.label}`}
                  className="mt-3 w-full rounded-xl border border-line object-cover"
                />
              ) : null}

              <button
                type="button"
                disabled={sending}
                onClick={() => inputRefs.current[problem.id]?.click()}
                className="mt-3 h-14 w-full rounded-2xl bg-brand px-4 text-base font-semibold text-white transition-transform active:scale-[0.99] disabled:opacity-60"
              >
                {sending ? 'Изпраща…' : sent ? 'Снимай отново' : 'Снимай решението'}
              </button>

              <input
                ref={(element) => {
                  inputRefs.current[problem.id] = element;
                }}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                aria-label={`Снимка на решението за ${problem.label}`}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onCapture(problem.id, file);
                  event.currentTarget.value = '';
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PhoneExamScreen;
