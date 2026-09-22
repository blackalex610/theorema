import { CheckCircleIcon, ClockIcon } from '@phosphor-icons/react';

import type { AssignmentReport } from '../../services/assignments';
import { masteryTone } from '../../utils/topicDiagnostics';
import { formatDate, scoreTone } from '../../utils/classroomFormat';

const wrongTone: Record<string, string> = {
  danger: 'bg-danger',
  warn: 'bg-warn',
  ok: 'bg-brand',
  empty: 'bg-line-strong',
};

/**
 * What came back from one assignment.
 *
 * Two lists, in the order a teacher uses them: who has not handed in yet
 * (actionable before the deadline), then which questions the class got
 * wrong (actionable in the next lesson). The second list is only a sentence
 * anyone can say because the whole class sat one paper.
 */
const AssignmentReportView: React.FC<{ report: AssignmentReport }> = ({ report }) => {
  const missing = report.rows.filter((row) => !row.submitted);
  const done = report.rows.filter((row) => row.submitted);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section>
        <h4 className="mb-2 text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
          Ученици · {report.submitted_count} от {report.student_count} предали
        </h4>
        {report.rows.length === 0 ? (
          <p className="text-caption text-ink-muted">В класа още няма ученици.</p>
        ) : (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {[...missing, ...done].map((row) => (
              <li key={row.student_id} className="flex items-center gap-3 px-4 py-2.5">
                {row.submitted ? (
                  <CheckCircleIcon aria-hidden="true" weight="fill" className="size-4 shrink-0 text-brand" />
                ) : (
                  <ClockIcon aria-hidden="true" className="size-4 shrink-0 text-ink-faint" />
                )}
                <span className="min-w-0 flex-1 truncate text-caption text-ink">{row.name}</span>
                {row.submitted ? (
                  <span className="tnum text-right text-caption">
                    <span className={`font-semibold ${scoreTone(row.percentage_correct)}`}>
                      {row.percentage_correct}%
                    </span>
                    <span className="ml-2 text-ink-faint">{formatDate(row.submitted_at)}</span>
                  </span>
                ) : (
                  <span className="text-caption text-ink-faint">не е предал</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="mb-2 text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
          По задачи
        </h4>
        {report.questions.length === 0 ? (
          <p className="text-caption text-ink-muted">
            Щом първият ученик предаде, тук ще видиш коя задача колко души са сгрешили.
          </p>
        ) : (
          <ul className="space-y-2">
            {report.questions.map((question) => (
              <li
                key={question.question_number}
                className="grid grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-3"
              >
                <span className="tnum text-caption font-semibold text-ink">
                  №{question.question_number}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-micro text-ink-muted">
                    {question.topic_label}
                  </span>
                  <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-sunken">
                    <span
                      className={`block h-full rounded-full ${wrongTone[masteryTone(question.percent_correct)]}`}
                      style={{ width: `${Math.max(question.percent_correct, 2)}%` }}
                    />
                  </span>
                </span>
                <span className="tnum whitespace-nowrap text-right text-caption">
                  <span className={question.wrong ? 'font-semibold text-danger' : 'text-ink-faint'}>
                    {question.wrong} сгрешили
                  </span>
                  <span className="ml-1 text-ink-faint">/ {question.answered}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default AssignmentReportView;
