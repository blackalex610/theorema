import React, { useCallback, useEffect, useState } from 'react';
import AppNavbar from '../components/AppNavbar';
import { EmptyState, ErrorState, PageHeader, PageShell } from '../components/app/PageShell';
import { useSavedProblems } from '../context/SavedProblemsContext';
import {
  deleteSavedProblem,
  listSavedProblems,
  type SavedProblem,
  type SavedProblemSource,
} from '../services/savedProblems';
import { formatBgDateTime } from '../utils/datetime';

type Filter = 'all' | SavedProblemSource;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'Всички' },
  { value: 'exercise', label: 'От упражнения' },
  { value: 'nvo', label: 'От НВО' },
];

const originLine = (item: SavedProblem): string => {
  const origin = item.snapshot?.origin ?? {};
  if (item.snapshot?.kind === 'nvo') {
    return `От НВО тест • Задача ${origin.question_number ?? '?'}`;
  }
  if (origin.lesson_title) return `От урок ${origin.lesson_title}`;
  return origin.lesson_id ? `От урок ${origin.lesson_id}` : 'От упражнение';
};

const answerText = (value: string | string[] | null | undefined): string | null => {
  if (!value) return null;
  return Array.isArray(value) ? value.join('; ') : value;
};

const SavedProblemsPage: React.FC = () => {
  const { refresh } = useSavedProblems();
  const [items, setItems] = useState<SavedProblem[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(async (current: Filter, isCancelled: () => boolean) => {
    try {
      setLoading(true);
      setError(null);
      const loaded = await listSavedProblems(
        current === 'all' ? { limit: 100 } : { limit: 100, source: current }
      );
      if (!isCancelled()) setItems(loaded);
    } catch {
      if (!isCancelled()) setError('Грешка при зареждане на запазените задачи');
    } finally {
      if (!isCancelled()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    load(filter, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [filter, load]);

  const remove = useCallback(
    async (id: number) => {
      try {
        await deleteSavedProblem(id);
        setItems((current) => current.filter((item) => item.id !== id));
        await refresh();
      } catch {
        setError('Неуспешно премахване. Опитай отново.');
      }
    },
    [refresh]
  );

  return (
    <>
      <AppNavbar backTo="/dashboard" />
      <PageShell>
        <PageHeader
          title="Запазени задачи"
          description="Задачите, които си отбелязал по време на упражнения и НВО тестове."
        />

        <div className="mb-6 flex flex-wrap gap-2">
          {FILTERS.map((chip) => (
            <button
              key={chip.value}
              type="button"
              onClick={() => setFilter(chip.value)}
              aria-pressed={filter === chip.value}
              className={`rounded-full border px-3 py-1.5 text-caption font-semibold transition-colors ${
                filter === chip.value
                  ? 'border-brand-edge bg-brand-wash text-brand-ink'
                  : 'border-line text-ink-muted hover:border-line-strong hover:text-ink'
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {error && <ErrorState description={error} onRetry={() => setFilter(filter)} />}

        {!error && loading && <p className="text-body text-ink-muted">Зареждане…</p>}

        {!error && !loading && items.length === 0 && (
          <EmptyState
            title="Няма запазени задачи."
            description="Натисни отметката до задача в упражнение или НВО тест, за да я запазиш тук."
          />
        )}

        {!error && !loading && items.length > 0 && (
          <div className="space-y-3">
            {items.map((item) => {
              const snapshot = item.snapshot;
              const isOpen = openId === item.id;
              const mine = answerText(snapshot?.user_answer);
              const correct = answerText(snapshot?.correct_answer);

              return (
                <article
                  key={item.id}
                  className="rounded-xl border border-line bg-surface p-4 shadow-lift-1"
                >
                  <p className="mb-2 text-body text-ink">{snapshot?.question}</p>

                  <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-ink-muted">
                    <span>{originLine(item)}</span>
                    <span aria-hidden="true">•</span>
                    <span className="tnum">{formatBgDateTime(item.created_at)}</span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : item.id)}
                      className="rounded-lg border border-brand-edge px-3 py-1.5 text-caption font-semibold text-brand-ink transition-colors hover:bg-brand-wash"
                    >
                      {isOpen ? 'Скрий задачата' : 'Отвори задачата'}
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(item.id)}
                      className="rounded-lg border border-line px-3 py-1.5 text-caption font-semibold text-ink-muted transition-colors hover:border-danger-edge hover:text-danger"
                    >
                      Премахни
                    </button>
                  </div>

                  {isOpen && (
                    <div className="mt-4 space-y-3 border-t border-line pt-4">
                      {snapshot?.options && snapshot.options.length > 0 && (
                        <ul className="space-y-1">
                          {snapshot.options.map((option) => (
                            <li key={option.key} className="text-body text-ink">
                              <span className="font-semibold">{option.key})</span> {option.text}
                            </li>
                          ))}
                        </ul>
                      )}

                      {mine && (
                        <div>
                          <p className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
                            Твоят отговор
                          </p>
                          <p className="text-body text-ink">{mine}</p>
                        </div>
                      )}

                      {correct && (
                        <div>
                          <p className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
                            Верен отговор
                          </p>
                          <p className="text-body font-semibold text-ink">{correct}</p>
                        </div>
                      )}

                      {snapshot?.solution && (
                        <div>
                          <p className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
                            Решение
                          </p>
                          <p className="text-body text-ink-muted">{snapshot.solution}</p>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </PageShell>
    </>
  );
};

export default SavedProblemsPage;
