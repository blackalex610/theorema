import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { PrinterIcon, UsersThreeIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  StatTile,
} from '../components/app/PageShell';
import ClassAssignmentsPanel from '../components/classroom/ClassAssignmentsPanel';
import ClassDiagnosticsPanel from '../components/classroom/ClassDiagnosticsPanel';
import ClassRosterTable from '../components/classroom/ClassRosterTable';
import SchoolAttachControl from '../components/classroom/SchoolAttachControl';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  archiveClassroom,
  getClassroom,
  removeStudent,
  type ClassroomDetail,
  type RosterRow,
} from '../services/classrooms';

const TABS = ['roster', 'topics', 'assignments'] as const;
type Tab = (typeof TABS)[number];

/**
 * One class, three questions a teacher asks of it:
 * who is in it (roster), what are they getting wrong (topics), and what
 * did I set them (assignments). The tab lives in the URL so a link, a
 * refresh or the back button lands on the same view.
 */
const ClassroomDetailPage: React.FC = () => {
  const { classroomId } = useParams<{ classroomId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get('tab');
  const tab: Tab = (TABS as readonly string[]).includes(requested ?? '')
    ? (requested as Tab)
    : 'roster';

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

  const onTab = (value: string) => {
    setSearchParams(
      (params) => {
        if (value === 'roster') params.delete('tab');
        else params.set('tab', value);
        return params;
      },
      { replace: true }
    );
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
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to={`/classrooms/${detail.id}/report`}>
                  <PrinterIcon />
                  Отчет за печат
                </Link>
              </Button>
              {detail.is_active && (
                <Button variant="outline" size="sm" onClick={onArchive}>
                  Архивирай класа
                </Button>
              )}
            </div>
          }
        />

        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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

        <div className="mb-8">
          <SchoolAttachControl
            classroomId={detail.id}
            schoolId={detail.school_id}
            onChange={load}
          />
        </div>

        <Tabs value={tab} onValueChange={onTab}>
          <TabsList>
            <TabsTrigger value="roster">Ученици</TabsTrigger>
            <TabsTrigger value="topics">Пропуски по теми</TabsTrigger>
            <TabsTrigger value="assignments">Задания</TabsTrigger>
          </TabsList>

          <TabsContent value="roster">
            {detail.roster.length === 0 ? (
              <EmptyState
                icon={<UsersThreeIcon />}
                title="Още никой не се е присъединил"
                description={`Дай кода ${detail.join_code} на учениците си — те го въвеждат в „Моите класове“.`}
              />
            ) : (
              <ClassRosterTable
                classroomId={detail.id}
                rows={detail.roster}
                busyStudent={busyStudent}
                onRemove={onRemove}
              />
            )}
          </TabsContent>

          <TabsContent value="topics">
            <ClassDiagnosticsPanel classroomId={detail.id} />
          </TabsContent>

          <TabsContent value="assignments">
            <ClassAssignmentsPanel classroomId={detail.id} studentCount={detail.roster.length} />
          </TabsContent>
        </Tabs>
      </PageShell>
    </>
  );
};

export default ClassroomDetailPage;
