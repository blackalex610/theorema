import { useEffect, useState } from 'react';
import { ChartBarIcon, TargetIcon } from '@phosphor-icons/react';

import { EmptyState, ErrorState, StatTile } from '../app/PageShell';
import TopicHeatmap from '../app/TopicHeatmap';
import { Skeleton } from '@/components/ui/skeleton';
import { getClassDiagnostics, type ClassDiagnostics } from '../../services/classrooms';

/**
 * "What do I reteach on Monday" — the question the roster cannot answer.
 *
 * The weakest-topics strip comes first because it is the answer; the full
 * table underneath is there so a teacher can check the answer rather than
 * take it on faith. Every percentage carries its sample size for the same
 * reason.
 */
const ClassDiagnosticsPanel: React.FC<{ classroomId: number }> = ({ classroomId }) => {
  const [data, setData] = useState<ClassDiagnostics | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Cancelled on change so a slow response for the previous class can
    // never overwrite the one now on screen.
    let cancelled = false;
    getClassDiagnostics(classroomId)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setFailed(false);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [classroomId, attempt]);

  if (failed) {
    return (
      <ErrorState
        description="Анализът на класа не се зареди."
        onRetry={() => setAttempt((n) => n + 1)}
      />
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (data.topics.length === 0) {
    return (
      <EmptyState
        icon={<ChartBarIcon />}
        title="Още няма предадени изпити"
        description={
          data.student_count === 0
            ? 'Щом учениците се присъединят и решат изпит, тук ще виждаш по кои теми се затрудняват.'
            : 'Класът още не е решавал изпити. Задай един от раздела „Задания“.'
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Ученици с данни"
          value={data.students_with_data}
          hint={`от ${data.student_count} в класа`}
        />
        <StatTile label="Предадени изпити" value={data.attempts} />
        <StatTile
          label="Обхванати теми"
          value={data.topics.length}
          tone="brand"
        />
      </div>

      {data.weakest.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <TargetIcon aria-hidden="true" className="size-4 text-danger" />
            <h3 className="font-display text-title font-semibold text-ink">
              Върху това си струва да се работи
            </h3>
          </div>
          {/* Ranked only among topics asked often enough to mean something —
              the server excludes small samples and unidentified questions. */}
          <p className="mb-3 text-caption text-ink-muted">
            Подредени по най-нисък резултат, само за теми с поне{' '}
            {data.min_asked_for_ranking} решени задачи.
          </p>
          <ol className="grid gap-2 sm:grid-cols-2">
            {data.weakest.map((topic, index) => (
              <li
                key={topic.key}
                /* min-w-0: a grid item defaults to min-width:auto, so a long
                   topic name would widen the column past a phone screen
                   instead of truncating. */
                className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3"
              >
                <span className="tnum text-caption font-semibold text-ink-faint">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body font-medium text-ink">
                    {topic.label}
                  </span>
                  <span className="text-micro text-ink-faint">{topic.strand_label}</span>
                </span>
                <span className="tnum shrink-0 text-right">
                  <span className="block text-body font-semibold text-danger">
                    {topic.percent_correct}%
                  </span>
                  <span className="text-micro text-ink-faint">
                    {topic.correct}/{topic.asked}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section>
        <h3 className="mb-1 font-display text-title font-semibold text-ink">Всички теми</h3>
        <p className="mb-4 text-caption text-ink-muted">
          Процентът е от всички зададени задачи по темата в класа. До него стои броят
          верни от общо зададени.
        </p>
        <TopicHeatmap topics={data.topics} minAsked={data.min_asked_for_ranking} />
      </section>
    </div>
  );
};

export default ClassDiagnosticsPanel;
