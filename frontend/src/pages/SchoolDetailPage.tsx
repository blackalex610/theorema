import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShieldCheckIcon, UsersThreeIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  SectionHeading,
  StatTile,
} from '../components/app/PageShell';
import TopicHeatmap from '../components/app/TopicHeatmap';
import { scoreTone } from '../utils/classroomFormat';
import ReadinessBar from '../components/school/ReadinessBar';
import { Skeleton } from '@/components/ui/skeleton';
import { getSchoolOverview, type SchoolOverview } from '../services/schools';
import { masteryTone } from '../utils/topicDiagnostics';

const barFill: Record<string, string> = {
  danger: 'bg-danger',
  warn: 'bg-warn',
  ok: 'bg-brand',
  empty: 'bg-line-strong',
};

/**
 * What a director opens: is the building ready for НВО, which class is
 * behind, on what, and how many seats is this.
 *
 * There is no student anywhere on this page, by construction — the API
 * returns counts, bands and percentages only. A child consented to one
 * teacher, not to the building. The note under the header says so, because
 * a director will ask.
 */
const SchoolDetailPage: React.FC = () => {
  const { schoolId } = useParams<{ schoolId: string }>();
  const [overview, setOverview] = useState<SchoolOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const load = () => setAttempt((n) => n + 1);

  useEffect(() => {
    if (!schoolId) return;
    let cancelled = false;
    getSchoolOverview(Number(schoolId))
      .then((result) => {
        if (cancelled) return;
        setOverview(result);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status;
        setError(status === 404 ? 'Това училище не е намерено.' : 'Училището не се зареди.');
      });
    return () => {
      cancelled = true;
    };
  }, [schoolId, attempt]);

  if (error) {
    return (
      <>
        <AppNavbar />
        <PageShell>
          <ErrorState description={error} onRetry={load} />
        </PageShell>
      </>
    );
  }

  if (!overview) {
    return (
      <>
        <AppNavbar />
        <PageShell>
          <Skeleton className="h-10 w-64" />
          <Skeleton className="mt-6 h-64 w-full" />
        </PageShell>
      </>
    );
  }

  return (
    <>
      <AppNavbar />
      <PageShell>
        <PageHeader
          kicker="Училище"
          title={overview.name}
          crumbs={[{ label: 'Училища', to: '/schools' }, { label: overview.name }]}
          description={overview.city ?? undefined}
        />

        <div className="mb-8 flex items-start gap-3 rounded-xl border border-line bg-surface p-4 text-caption text-ink-muted">
          <ShieldCheckIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-brand" />
          <p>
            Тук виждаш средни резултати по класове, випуски и теми — никога имена на ученици.
            Учениците са дали съгласие да ги вижда техният учител, не цялото училище. Учителите
            сами включват класовете си с кода{' '}
            <span className="font-mono font-semibold tracking-[0.15em] text-brand-ink">
              {overview.join_code}
            </span>
            .
          </p>
        </div>

        <div className="mb-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Класове" value={overview.class_count} />
          <StatTile label="Учители" value={overview.teacher_count} />
          <StatTile
            label="Ученици"
            value={overview.seats_used}
            tone="brand"
            hint="Всяко дете се брои веднъж"
          />
          <StatTile
            label="С поне един изпит"
            value={overview.students_with_data}
            tone={
              overview.seats_used && overview.students_with_data < overview.seats_used / 2
                ? 'warn'
                : 'default'
            }
          />
        </div>

        {overview.class_count === 0 ? (
          <EmptyState
            icon={<UsersThreeIcon />}
            title="Още няма включени класове"
            description={`Дай кода ${overview.join_code} на учителите. След като се присъединят, всеки включва своите класове от страницата на класа.`}
          />
        ) : (
          <div className="space-y-12">
            <section>
              <SectionHeading
                title="Готовност за НВО"
                description="Колко ученици в коя степен са, по последния им изпит."
              />
              <div className="rounded-xl border border-line bg-surface p-5">
                <ReadinessBar bands={overview.readiness} />
              </div>
            </section>

            <section>
              <SectionHeading
                title="Класове"
                description="Средно от последния изпит на всеки ученик в класа."
              />
              <div className="overflow-x-auto rounded-xl border border-line bg-surface">
                <table className="w-full min-w-[40rem] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-line">
                      {['Клас', 'Учител', 'Ученици', 'С изпит', 'Среден резултат'].map((h) => (
                        <th
                          key={h}
                          scope="col"
                          className="px-4 py-3 text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {overview.classes.map((row) => (
                      <tr key={row.classroom_id} className="border-b border-line last:border-0">
                        <td className="px-4 py-3">
                          <span className="block font-medium text-ink">{row.name}</span>
                          {row.grade_level && (
                            <span className="text-micro text-ink-faint">{row.grade_level}. клас</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-caption text-ink-muted">{row.teacher_name}</td>
                        <td className="tnum px-4 py-3 text-ink-muted">{row.students}</td>
                        <td className="tnum px-4 py-3 text-ink-muted">{row.students_with_data}</td>
                        <td className="px-4 py-3">
                          {row.average_latest_score === null ? (
                            <span className="text-caption text-ink-faint">—</span>
                          ) : (
                            <span className="flex items-center gap-3">
                              <span className="block h-2 w-28 overflow-hidden rounded-full bg-sunken">
                                <span
                                  className={`block h-full rounded-full ${barFill[masteryTone(row.average_latest_score)]}`}
                                  style={{ width: `${Math.max(row.average_latest_score, 2)}%` }}
                                />
                              </span>
                              <span
                                className={`tnum text-caption font-semibold ${scoreTone(row.average_latest_score)}`}
                              >
                                {row.average_latest_score}%
                              </span>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {overview.grades.length > 1 && (
                <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-caption text-ink-muted">
                  {overview.grades.map((g) => (
                    <li key={String(g.grade_level)}>
                      <span className="font-semibold text-ink">
                        {g.grade_level ? `${g.grade_level}. клас` : 'Без посочен клас'}
                      </span>
                      : {g.classes} {g.classes === 1 ? 'паралелка' : 'паралелки'}, {g.students}{' '}
                      ученици
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {overview.topics.length > 0 && (
              <section>
                <SectionHeading
                  title="Теми в цялото училище"
                  description="Най-слабите отгоре. До процента стои броят верни от общо зададени."
                />
                {overview.weakest.length > 0 && (
                  <p className="mb-4 text-caption text-ink-muted">
                    Най-голям проблем:{' '}
                    {overview.weakest.slice(0, 3).map((t, i) => (
                      <span key={t.key}>
                        {i > 0 && ', '}
                        <span className="font-semibold text-ink">{t.label}</span>{' '}
                        <span className="tnum">({t.percent_correct}%)</span>
                      </span>
                    ))}
                    .
                  </p>
                )}
                <TopicHeatmap
                  topics={overview.topics}
                  minAsked={overview.min_asked_for_ranking}
                />
              </section>
            )}
          </div>
        )}
      </PageShell>
    </>
  );
};

export default SchoolDetailPage;
