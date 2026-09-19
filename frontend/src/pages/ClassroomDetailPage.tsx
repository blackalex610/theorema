import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { UsersThreeIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  StatTile,
} from '../components/app/PageShell';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  archiveClassroom,
  getClassroom,
  removeStudent,
  type ClassroomDetail,
  type RosterRow,
} from '../services/classrooms';

const formatDate = (iso: string | null) => {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('bg-BG', { day: '2-digit', month: '2-digit', year: '2-digit' });
};

/** Colour follows the number, so a teacher scanning a class sees trouble first. */
const scoreTone = (score: number | null) => {
  if (score === null) return 'text-ink-faint';
  if (score >= 70) return 'text-brand-ink';
  if (score >= 50) return 'text-warn';
  return 'text-danger';
};

const ClassroomDetailPage: React.FC = () => {
  const { classroomId } = useParams<{ classroomId: string }>();
  const [detail, setDetail] = useState<ClassroomDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyStudent, setBusyStudent] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!classroomId) return;
    setError(null);
    try {
      setDetail(await getClassroom(Number(classroomId)));
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(status === 404 ? 'Този клас не е намерен.' : 'Класът не се зареди.');
    }
  }, [classroomId]);

  useEffect(() => {
    load();
  }, [load]);

  const onRemove = async (row: RosterRow) => {
    if (!detail) return;
    setBusyStudent(row.student_id);
    try {
      await removeStudent(detail.id, row.student_id);
      await load();
    } finally {
      setBusyStudent(null);
    }
  };

  const onArchive = async () => {
    if (!detail) return;
    await archiveClassroom(detail.id);
    await load();
  };

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

  if (!detail) {
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

  const withScores = detail.roster.filter((row) => row.average_exam_score !== null);
  const classAverage = withScores.length
    ? Math.round(
        withScores.reduce((sum, row) => sum + (row.average_exam_score ?? 0), 0) / withScores.length
      )
    : null;
  const inactive = detail.roster.filter((row) => row.exams_taken === 0).length;

  return (
    <>
      <AppNavbar />
      <PageShell>
        <PageHeader
          kicker="Клас"
          title={detail.name}
          crumbs={[{ label: 'Класове', to: '/classrooms' }, { label: detail.name }]}
          description={
            detail.is_active
              ? 'Всички числа тук са изчислени на сървъра от реално предадени изпити.'
              : 'Този клас е архивиран и не приема нови ученици.'
          }
          actions={
            detail.is_active ? (
              <Button variant="outline" size="sm" onClick={onArchive}>
                Архивирай класа
              </Button>
            ) : undefined
          }
        />

        <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Ученици" value={detail.roster.length} />
          <StatTile
            label="Среден резултат"
            value={classAverage ?? '—'}
            suffix={classAverage === null ? undefined : '%'}
            tone="brand"
            hint={classAverage === null ? 'Още никой не е предал изпит' : undefined}
          />
          <StatTile label="Без нито един изпит" value={inactive} tone={inactive ? 'warn' : 'default'} />
          <StatTile
            label="Код за присъединяване"
            value={<span className="font-mono tracking-[0.15em]">{detail.join_code}</span>}
          />
        </div>

        {detail.roster.length === 0 ? (
          <EmptyState
            icon={<UsersThreeIcon />}
            title="Още никой не се е присъединил"
            description={`Дай кода ${detail.join_code} на учениците си — те го въвеждат в „Моите класове“.`}
          />
        ) : (
          /* The table scrolls inside its own container so the page itself
             never scrolls sideways on a phone. */
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[46rem] border-collapse text-left">
              <thead>
                <tr className="border-b border-line">
                  {['Ученик', 'Ниво', 'XP', 'Изпити', 'Среден', 'Най-добър', 'Последен', ''].map(
                    (heading) => (
                      <th
                        key={heading}
                        scope="col"
                        className="px-4 py-3 text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint"
                      >
                        {heading}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {detail.roster.map((row) => (
                  <tr key={row.student_id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <span className="block truncate font-medium text-ink">{row.name}</span>
                      {row.is_guest && (
                        <span className="text-micro text-ink-faint">гост профил</span>
                      )}
                    </td>
                    <td className="tnum px-4 py-3 text-ink-muted">{row.level}</td>
                    <td className="tnum px-4 py-3 text-ink-muted">{row.total_xp}</td>
                    <td className="tnum px-4 py-3 text-ink-muted">{row.exams_taken}</td>
                    <td className={`tnum px-4 py-3 font-semibold ${scoreTone(row.average_exam_score)}`}>
                      {row.average_exam_score === null ? '—' : `${row.average_exam_score}%`}
                    </td>
                    <td className="tnum px-4 py-3 text-ink-muted">
                      {row.best_exam_score === null ? '—' : `${row.best_exam_score}%`}
                    </td>
                    <td className="tnum px-4 py-3 text-caption text-ink-muted">
                      {formatDate(row.last_exam_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => onRemove(row)}
                        disabled={busyStudent === row.student_id}
                        className="rounded-lg px-2 py-1 text-caption font-medium text-ink-faint transition-colors hover:bg-sunken hover:text-danger disabled:opacity-50"
                      >
                        Премахни
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageShell>
    </>
  );
};

export default ClassroomDetailPage;
