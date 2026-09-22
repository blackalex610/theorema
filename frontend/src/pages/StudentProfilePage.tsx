import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChartLineIcon, PrinterIcon } from '@phosphor-icons/react';

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
import { formatDate, scoreTone } from '../utils/classroomFormat';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { getStudentProfile, type StudentProfile } from '../services/classrooms';

const DIFFICULTY_LABEL: Record<string, string> = {
  easy: 'Лесно',
  medium: 'Средно',
  actual: 'Като на НВО',
  extra_hard: 'Много трудно',
  standard: 'Като на НВО',
  hard: 'Много трудно',
};

/**
 * One student, as their teacher sees them: the roster said how they scored,
 * this says on what — and whether they are moving.
 */
const StudentProfilePage: React.FC = () => {
  const { classroomId, studentId } = useParams<{ classroomId: string; studentId: string }>();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const load = () => setAttempt((n) => n + 1);

  useEffect(() => {
    if (!classroomId || !studentId) return;
    let cancelled = false;
    getStudentProfile(Number(classroomId), Number(studentId))
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status;
        setError(
          status === 404 ? 'Този ученик не е в класа ти.' : 'Профилът на ученика не се зареди.'
        );
      });
    return () => {
      cancelled = true;
    };
  }, [classroomId, studentId, attempt]);

  const classCrumb = { label: 'Клас', to: `/classrooms/${classroomId}` };

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

  if (!profile) {
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

  const scores = profile.attempts.map((a) => a.percentage_correct);
  const latest = scores[0] ?? null;
  const first = scores[scores.length - 1] ?? null;
  const change = scores.length >= 2 && latest !== null && first !== null ? latest - first : null;
  const average = scores.length ? Math.round(scores.reduce((s, v) => s + v, 0) / scores.length) : null;

  return (
    <>
      <AppNavbar />
      <PageShell>
        <PageHeader
          kicker="Ученик"
          title={profile.name}
          crumbs={[{ label: 'Класове', to: '/classrooms' }, classCrumb, { label: profile.name }]}
          description={`В класа от ${formatDate(profile.joined_at)}. Резултатите са от изпити, оценени на сървъра.`}
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={`/classrooms/${classroomId}/students/${studentId}/report`}>
                <PrinterIcon />
                Отчет за родителска среща
              </Link>
            </Button>
          }
        />

        <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Изпити" value={profile.attempts.length} />
          <StatTile
            label="Последен резултат"
            value={latest ?? '—'}
            suffix={latest === null ? undefined : '%'}
            tone="brand"
          />
          <StatTile label="Среден" value={average ?? '—'} suffix={average === null ? undefined : '%'} />
          <StatTile
            label="Промяна от първия"
            value={change === null ? '—' : `${change > 0 ? '+' : ''}${change}`}
            suffix={change === null ? undefined : ' т.'}
            tone={change !== null && change < 0 ? 'warn' : 'default'}
            hint={change === null ? 'Нужни са поне два изпита' : undefined}
          />
        </div>

        {profile.topics.length === 0 ? (
          <EmptyState
            icon={<ChartLineIcon />}
            title="Още няма решени изпити"
            description="Щом ученикът предаде първия си изпит, тук ще се появят темите, в които греши."
          />
        ) : (
          <div className="grid gap-10 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <section>
              <SectionHeading
                title="По теми"
                description="Най-слабите теми са отгоре. До процента стои броят верни от общо зададени."
              />
              <TopicHeatmap topics={profile.topics} minAsked={profile.min_asked_for_ranking} showStudents={false} />
            </section>

            <section>
              <SectionHeading title="Изпити" description="Най-новите отгоре." />
              <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
                {profile.attempts.map((attempt) => (
                  <li key={attempt.exam_id} className="flex items-center gap-3 px-4 py-3">
                    <span className="min-w-0 flex-1">
                      <span className="block text-caption text-ink">
                        {formatDate(attempt.created_at)}
                      </span>
                      <span className="text-micro text-ink-faint">
                        {DIFFICULTY_LABEL[attempt.difficulty] ?? attempt.difficulty} ·{' '}
                        {attempt.format === 'short' ? 'кратък' : 'цял изпит'}
                      </span>
                    </span>
                    <span className={`tnum text-body font-semibold ${scoreTone(attempt.percentage_correct)}`}>
                      {attempt.percentage_correct}%
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </PageShell>
    </>
  );
};

export default StudentProfilePage;
