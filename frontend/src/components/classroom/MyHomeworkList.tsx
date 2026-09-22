import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircleIcon, ClipboardTextIcon } from '@phosphor-icons/react';

import { SectionHeading } from '../app/PageShell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { listMyAssignments, type StudentAssignment } from '../../services/assignments';
import { formatDue, isOverdue } from '../../utils/assignmentDates';

/**
 * Homework from the student's teachers.
 *
 * Renders nothing at all for someone with no assignments — most people who
 * see the dashboard are not in a class, and an empty "homework" box would be
 * noise to them. Opening a paper goes through /nvo/practice?assignment=<id>,
 * which never spends the student's own daily exam.
 */
const MyHomeworkList: React.FC<{ className?: string; limit?: number }> = ({
  className,
  limit,
}) => {
  const [items, setItems] = useState<StudentAssignment[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMyAssignments()
      .then((list) => {
        if (!cancelled) setItems(list);
      })
      // Best-effort: the page this sits on has its own job, and a failure
      // here should not put an error banner on top of it.
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!items || items.length === 0) return null;

  // Unfinished work first, then by newest; closed ones last.
  const ordered = [...items].sort((a, b) => {
    const rank = (x: StudentAssignment) => (!x.is_open ? 2 : x.submitted ? 1 : 0);
    return rank(a) - rank(b) || b.created_at.localeCompare(a.created_at);
  });
  const shown = limit ? ordered.slice(0, limit) : ordered;
  const pending = items.filter((i) => i.is_open && !i.submitted).length;

  return (
    <section className={className}>
      <SectionHeading
        title="Задания от учителя"
        description={
          pending > 0
            ? pending === 1
              ? '1 задание чака да го решиш.'
              : `${pending} задания чакат да ги решиш.`
            : 'Всичко е предадено.'
        }
      />
      <ul className="grid gap-3 sm:grid-cols-2">
        {shown.map((item) => {
          const overdue = item.is_open && !item.submitted && isOverdue(item.due_at);
          return (
            <li
              key={item.id}
              className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-surface p-4"
            >
              {item.submitted ? (
                <CheckCircleIcon aria-hidden="true" weight="fill" className="size-5 shrink-0 text-brand" />
              ) : (
                <ClipboardTextIcon aria-hidden="true" className="size-5 shrink-0 text-ink-faint" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-body font-semibold text-ink">{item.title}</p>
                <p className="truncate text-caption text-ink-muted">
                  {item.class_name} · {formatDue(item.due_at)}
                </p>
              </div>
              {item.submitted ? (
                <Badge variant="brand">Предадено</Badge>
              ) : !item.is_open ? (
                <Badge variant="neutral">Приключено</Badge>
              ) : (
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {overdue && <Badge variant="warn">Изтекъл срок</Badge>}
                  <Button asChild size="sm">
                    <Link to={`/nvo/practice?assignment=${item.id}`}>Реши</Link>
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default MyHomeworkList;
