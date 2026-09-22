import { Link } from 'react-router-dom';

import type { RosterRow } from '../../services/classrooms';
import { formatDate, scoreTone } from '../../utils/classroomFormat';

/**
 * The class roster. Each name opens that student's topic profile — the
 * roster says how a child scored, the profile says on what.
 */
const ClassRosterTable: React.FC<{
  classroomId: number;
  rows: RosterRow[];
  busyStudent: number | null;
  onRemove: (row: RosterRow) => void;
}> = ({ classroomId, rows, busyStudent, onRemove }) => (
  /* The table scrolls inside its own container so the page itself never
     scrolls sideways on a phone. */
  <div className="overflow-x-auto rounded-xl border border-line bg-surface">
    <table className="w-full min-w-[46rem] border-collapse text-left">
      <thead>
        <tr className="border-b border-line">
          {['Ученик', 'Ниво', 'XP', 'Изпити', 'Среден', 'Най-добър', 'Последен', ''].map(
            (heading) => (
              <th
                key={heading || 'actions'}
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
        {rows.map((row) => (
          <tr key={row.student_id} className="border-b border-line last:border-0">
            <td className="px-4 py-3">
              <Link
                to={`/classrooms/${classroomId}/students/${row.student_id}`}
                className="block truncate font-medium text-ink underline-offset-4 hover:text-brand-ink hover:underline"
              >
                {row.name}
              </Link>
              {row.is_guest && <span className="text-micro text-ink-faint">гост профил</span>}
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
                aria-label={`Премахни ${row.name} от класа`}
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
);

export default ClassRosterTable;
