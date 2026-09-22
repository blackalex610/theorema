import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import TopicHeatmap from '../components/app/TopicHeatmap';
import { ErrorState } from '../components/app/PageShell';
import { formatDate } from '../utils/classroomFormat';
import { ReportFigure, ReportSection, ReportShell } from '../components/report/ReportShell';
import { Skeleton } from '@/components/ui/skeleton';
import {
  getClassroom,
  getStudentProfile,
  type ClassroomDetail,
  type StudentProfile,
} from '../services/classrooms';

/**
 * One page for a parents' evening.
 *
 * Written for a parent, not a teacher: the headline is "what to practise",
 * in plain Bulgarian topic names, before any table. It shows one child's own
 * results only — no class ranking, no other children — and leaves ruled
 * space for the teacher's handwritten note, because that is what actually
 * gets read across the desk.
 */
const StudentReportPage: React.FC = () => {
  const { classroomId, studentId } = useParams<{ classroomId: string; studentId: string }>();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [classroom, setClassroom] = useState<ClassroomDetail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!classroomId || !studentId) return;
    Promise.all([
      getStudentProfile(Number(classroomId), Number(studentId)),
      getClassroom(Number(classroomId)),
    ])
      .then(([p, c]) => {
        setProfile(p);
        setClassroom(c);
      })
      .catch(() => setFailed(true));
  }, [classroomId, studentId]);

  if (failed) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState description="Отчетът не се зареди." />
      </div>
    );
  }

  if (!profile || !classroom) {
    return (
      <div className="mx-auto max-w-[52rem] space-y-4 p-6">
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const scores = profile.attempts.map((a) => a.percentage_correct);
  const latest = scores[0];
  const first = scores[scores.length - 1];
  const average = scores.length ? Math.round(scores.reduce((s, v) => s + v, 0) / scores.length) : null;
  const change = scores.length >= 2 ? latest - first : null;
  const focus = profile.weakest.slice(0, 3);

  return (
    <ReportShell
      title={profile.name}
      subtitle={`${classroom.name}${classroom.grade_level ? ` · ${classroom.grade_level}. клас` : ''} · отчет за напредъка`}
    >
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <ReportFigure label="Решени изпити" value={String(profile.attempts.length)} />
        <ReportFigure label="Последен" value={latest === undefined ? '—' : `${latest}%`} />
        <ReportFigure label="Среден" value={average === null ? '—' : `${average}%`} />
        <ReportFigure
          label="Промяна"
          value={change === null ? '—' : `${change > 0 ? '+' : ''}${change} т.`}
          hint={change === null ? 'след два изпита' : 'от първия до последния'}
        />
      </div>

      {profile.attempts.length === 0 ? (
        <p className="text-body text-ink-muted">Ученикът още не е решавал изпит в платформата.</p>
      ) : (
        <>
          <ReportSection title="Върху какво да се упражнява">
            {focus.length === 0 ? (
              <p className="text-body text-ink-muted">
                Още няма достатъчно решени задачи по една тема, за да се направи извод.
              </p>
            ) : (
              <ol className="space-y-2">
                {focus.map((topic, i) => (
                  <li key={topic.key} className="flex items-baseline gap-3 text-body">
                    <span className="tnum font-semibold text-ink-faint">{i + 1}.</span>
                    <span className="flex-1 text-ink">
                      <span className="font-semibold">{topic.label}</span>{' '}
                      <span className="text-ink-muted">({topic.strand_label.toLowerCase()})</span>
                    </span>
                    <span className="tnum text-caption text-ink-muted">
                      {topic.correct} от {topic.asked} верни
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </ReportSection>

          <ReportSection title="Резултати по теми">
            <TopicHeatmap
              topics={profile.topics}
              minAsked={profile.min_asked_for_ranking}
              showStudents={false}
            />
          </ReportSection>

          <ReportSection title="Изпити">
            <table className="w-full border-collapse text-left text-caption">
              <thead>
                <tr className="border-b border-line-strong">
                  <th scope="col" className="py-2 font-semibold text-ink-muted">Дата</th>
                  <th scope="col" className="py-2 font-semibold text-ink-muted">Формат</th>
                  <th scope="col" className="py-2 text-right font-semibold text-ink-muted">Резултат</th>
                </tr>
              </thead>
              <tbody>
                {profile.attempts.map((attempt) => (
                  <tr key={attempt.exam_id} className="border-b border-line">
                    <td className="tnum py-2 text-ink">{formatDate(attempt.created_at)}</td>
                    <td className="py-2 text-ink-muted">
                      {attempt.format === 'short' ? 'Кратък вариант' : 'Цял изпит'}
                    </td>
                    <td className="tnum py-2 text-right font-semibold text-ink">
                      {attempt.percentage_correct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ReportSection>
        </>
      )}

      <ReportSection title="Бележка на учителя">
        <div className="space-y-7 pt-2" aria-hidden="true">
          {[0, 1, 2, 3].map((line) => (
            <div key={line} className="border-b border-line-strong" />
          ))}
        </div>
      </ReportSection>
    </ReportShell>
  );
};

export default StudentReportPage;
