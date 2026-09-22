import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import TopicHeatmap from '../components/app/TopicHeatmap';
import { ErrorState } from '../components/app/PageShell';
import { formatDate } from '../utils/classroomFormat';
import { ReportFigure, ReportSection, ReportShell } from '../components/report/ReportShell';
import { Skeleton } from '@/components/ui/skeleton';
import { listClassAssignments, type Assignment } from '../services/assignments';
import {
  getClassDiagnostics,
  getClassroom,
  type ClassDiagnostics,
  type ClassroomDetail,
} from '../services/classrooms';
import { formatDue } from '../utils/assignmentDates';

/**
 * The class on one printable page — for a subject meeting, the director, or
 * the teacher's own records at the end of term. Roster, topic picture and
 * what was set, in that order.
 */
const ClassReportPage: React.FC = () => {
  const { classroomId } = useParams<{ classroomId: string }>();
  const [detail, setDetail] = useState<ClassroomDetail | null>(null);
  const [diagnostics, setDiagnostics] = useState<ClassDiagnostics | null>(null);
  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!classroomId) return;
    const id = Number(classroomId);
    Promise.all([getClassroom(id), getClassDiagnostics(id), listClassAssignments(id)])
      .then(([d, diag, a]) => {
        setDetail(d);
        setDiagnostics(diag);
        setAssignments(a);
      })
      .catch(() => setFailed(true));
  }, [classroomId]);

  if (failed) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState description="Отчетът не се зареди." />
      </div>
    );
  }

  if (!detail || !diagnostics || !assignments) {
    return (
      <div className="mx-auto max-w-[52rem] space-y-4 p-6">
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const withScores = detail.roster.filter((r) => r.average_exam_score !== null);
  const classAverage = withScores.length
    ? Math.round(withScores.reduce((s, r) => s + (r.average_exam_score ?? 0), 0) / withScores.length)
    : null;
  const roster = [...detail.roster].sort((a, b) => a.name.localeCompare(b.name, 'bg'));

  return (
    <ReportShell
      title={detail.name}
      subtitle={`${detail.grade_level ? `${detail.grade_level}. клас · ` : ''}отчет за класа`}
    >
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ReportFigure label="Ученици" value={String(detail.roster.length)} />
        <ReportFigure
          label="С поне един изпит"
          value={String(diagnostics.students_with_data)}
        />
        <ReportFigure label="Предадени изпити" value={String(diagnostics.attempts)} />
        <ReportFigure label="Среден резултат" value={classAverage === null ? '—' : `${classAverage}%`} />
      </div>

      {diagnostics.weakest.length > 0 && (
        <ReportSection title="Най-слаби теми">
          <ol className="space-y-1.5">
            {diagnostics.weakest.map((topic, i) => (
              <li key={topic.key} className="flex items-baseline gap-3 text-body">
                <span className="tnum font-semibold text-ink-faint">{i + 1}.</span>
                <span className="flex-1 text-ink">
                  {topic.label}{' '}
                  <span className="text-caption text-ink-muted">· {topic.strand_label}</span>
                </span>
                <span className="tnum text-caption text-ink">
                  <span className="font-semibold">{topic.percent_correct}%</span>{' '}
                  <span className="text-ink-muted">
                    ({topic.correct}/{topic.asked}, {topic.students} уч.)
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </ReportSection>
      )}

      <ReportSection title="Ученици">
        <table className="w-full border-collapse text-left text-caption">
          <thead>
            <tr className="border-b border-line-strong">
              {['Ученик', 'Изпити', 'Среден', 'Най-добър', 'Последен изпит'].map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`py-2 font-semibold text-ink-muted ${i > 0 ? 'text-right' : ''}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roster.map((row) => (
              <tr key={row.student_id} className="border-b border-line">
                <td className="py-1.5 text-ink">{row.name}</td>
                <td className="tnum py-1.5 text-right text-ink-muted">{row.exams_taken}</td>
                <td className="tnum py-1.5 text-right font-semibold text-ink">
                  {row.average_exam_score === null ? '—' : `${row.average_exam_score}%`}
                </td>
                <td className="tnum py-1.5 text-right text-ink-muted">
                  {row.best_exam_score === null ? '—' : `${row.best_exam_score}%`}
                </td>
                <td className="tnum py-1.5 text-right text-ink-muted">{formatDate(row.last_exam_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ReportSection>

      {diagnostics.topics.length > 0 && (
        <ReportSection title="Всички теми">
          <TopicHeatmap topics={diagnostics.topics} minAsked={diagnostics.min_asked_for_ranking} />
        </ReportSection>
      )}

      {assignments.length > 0 && (
        <ReportSection title="Задания">
          <table className="w-full border-collapse text-left text-caption">
            <thead>
              <tr className="border-b border-line-strong">
                <th scope="col" className="py-2 font-semibold text-ink-muted">Задание</th>
                <th scope="col" className="py-2 font-semibold text-ink-muted">Срок</th>
                <th scope="col" className="py-2 text-right font-semibold text-ink-muted">Предали</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id} className="border-b border-line">
                  <td className="py-1.5 text-ink">{a.title}</td>
                  <td className="py-1.5 text-ink-muted">{formatDue(a.due_at)}</td>
                  <td className="tnum py-1.5 text-right text-ink">
                    {a.submitted_count} / {a.student_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>
      )}
    </ReportShell>
  );
};

export default ClassReportPage;
