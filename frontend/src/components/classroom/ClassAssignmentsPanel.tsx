import { useCallback, useEffect, useState } from 'react';
import { CaretDownIcon, ClipboardTextIcon, PlusIcon } from '@phosphor-icons/react';

import { EmptyState, ErrorState, SectionHeading } from '../app/PageShell';
import AssignmentReportView from './AssignmentReportView';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { getLimitErrorDetail } from '../../services/api';
import {
  closeAssignment,
  createAssignment,
  getAssignmentReport,
  listClassAssignments,
  reopenAssignment,
  type Assignment,
  type AssignmentReport,
} from '../../services/assignments';
import { dueDateToIso, formatDue, isOverdue } from '../../utils/assignmentDates';

/** Same words the student sees on the exam page's difficulty picker. */
const DIFFICULTIES = [
  { value: 'actual', label: 'Като на НВО' },
  { value: 'easy', label: 'Лесно' },
  { value: 'medium', label: 'Средно' },
  { value: 'extra_hard', label: 'Много трудно' },
] as const;

const FORMATS = [
  { value: 'full', label: 'Цял изпит' },
  { value: 'short', label: 'Кратък вариант' },
] as const;

const selectClass =
  'h-10 w-full rounded-lg border border-line bg-surface px-3 text-body text-ink focus-visible:outline-2 focus-visible:outline-brand';

/**
 * Setting homework and reading it back.
 *
 * One paper per assignment, sat by the whole class — the form says so,
 * because it is the thing that makes the per-question report meaningful and
 * it is also the thing a teacher needs to know before setting it as a test
 * (students sitting side by side have the same questions).
 */
const ClassAssignmentsPanel: React.FC<{ classroomId: number; studentCount: number }> = ({
  classroomId,
  studentCount,
}) => {
  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [failed, setFailed] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDay, setDueDay] = useState('');
  const [difficulty, setDifficulty] = useState<string>('actual');
  const [format, setFormat] = useState<string>('full');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [openId, setOpenId] = useState<number | null>(null);
  const [reports, setReports] = useState<Record<number, AssignmentReport>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      setAssignments(await listClassAssignments(classroomId));
    } catch {
      setFailed(true);
    }
  }, [classroomId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleReport = async (assignment: Assignment) => {
    if (openId === assignment.id) {
      setOpenId(null);
      return;
    }
    setOpenId(assignment.id);
    // Always refetch: the point of opening it is to see who has handed in since.
    try {
      const report = await getAssignmentReport(assignment.id);
      setReports((prev) => ({ ...prev, [assignment.id]: report }));
    } catch {
      setOpenId(null);
    }
  };

  const onCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const report = await createAssignment({
        classroomId,
        title: title.trim(),
        dueAt: dueDateToIso(dueDay),
        difficulty,
        format,
      });
      setReports((prev) => ({ ...prev, [report.id]: report }));
      setTitle('');
      setDueDay('');
      setShowForm(false);
      await load();
      setOpenId(report.id);
    } catch (error) {
      // Generating the paper spends the teacher's own daily exam; say so in
      // the server's words rather than a generic failure.
      const limit = getLimitErrorDetail(error);
      setCreateError(
        limit?.message ?? 'Заданието не можа да се създаде. Опитай отново след малко.'
      );
    } finally {
      setCreating(false);
    }
  };

  const onToggleOpen = async (assignment: Assignment) => {
    setBusyId(assignment.id);
    try {
      const report = assignment.is_open
        ? await closeAssignment(assignment.id)
        : await reopenAssignment(assignment.id);
      setReports((prev) => ({ ...prev, [assignment.id]: report }));
      await load();
    } finally {
      setBusyId(null);
    }
  };

  if (failed) {
    return <ErrorState description="Заданията не се заредиха." onRetry={load} />;
  }

  if (!assignments) {
    return <Skeleton className="h-48 w-full" />;
  }

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Задания"
        description="Целият клас решава един и същ вариант — затова виждаш коя задача колко души са сгрешили."
        action={
          !showForm && (
            <Button size="sm" onClick={() => setShowForm(true)}>
              <PlusIcon />
              Ново задание
            </Button>
          )
        }
      />

      {showForm && (
        <form
          onSubmit={onCreate}
          className="space-y-4 rounded-xl border border-line bg-surface p-5 shadow-lift-1"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="assignment-title">Заглавие</Label>
              <Input
                id="assignment-title"
                value={title}
                maxLength={160}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Пробен НВО — октомври"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-due">Срок</Label>
              <Input
                id="assignment-due"
                type="date"
                value={dueDay}
                onChange={(e) => setDueDay(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-difficulty">Трудност</Label>
              <select
                id="assignment-difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className={selectClass}
              >
                {DIFFICULTIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="assignment-format">Формат</Label>
              <select
                id="assignment-format"
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className={selectClass}
              >
                {FORMATS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p className="text-caption text-ink-muted">
            Генерирането на варианта използва твоя дневен изпит. Учениците не харчат своя, когато го
            решават.
          </p>

          {createError && (
            <p role="alert" className="text-caption text-danger">
              {createError}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={creating || !title.trim()}>
              {creating ? 'Генериране на варианта…' : 'Задай на класа'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
              Отказ
            </Button>
          </div>
        </form>
      )}

      {assignments.length === 0 && !showForm ? (
        <EmptyState
          icon={<ClipboardTextIcon />}
          title="Още няма задания"
          description={
            studentCount === 0
              ? 'Първо нека учениците се присъединят с кода на класа, после им задай изпит.'
              : 'Задай един вариант на целия клас и виж кои задачи ги затрудняват.'
          }
          action={
            <Button size="sm" onClick={() => setShowForm(true)}>
              <PlusIcon />
              Ново задание
            </Button>
          }
        />
      ) : (
        <ul className="space-y-3">
          {assignments.map((assignment) => {
            const expanded = openId === assignment.id;
            const overdue = assignment.is_open && isOverdue(assignment.due_at);
            const report = reports[assignment.id];
            return (
              <li
                key={assignment.id}
                className="overflow-hidden rounded-xl border border-line bg-surface"
              >
                <button
                  type="button"
                  onClick={() => toggleReport(assignment)}
                  aria-expanded={expanded}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-sunken"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-body font-medium text-ink">
                      {assignment.title}
                    </span>
                    <span className="text-caption text-ink-muted">
                      {formatDue(assignment.due_at)}
                    </span>
                  </span>
                  {!assignment.is_open ? (
                    <Badge variant="neutral">Приключено</Badge>
                  ) : overdue ? (
                    <Badge variant="warn">Изтекъл срок</Badge>
                  ) : (
                    <Badge variant="brand">Активно</Badge>
                  )}
                  <span className="tnum shrink-0 text-caption text-ink-muted">
                    {assignment.submitted_count}/{assignment.student_count}
                  </span>
                  <CaretDownIcon
                    aria-hidden="true"
                    className={`size-4 shrink-0 text-ink-faint transition-transform ${
                      expanded ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {expanded && (
                  <div className="space-y-4 border-t border-line px-4 py-4">
                    {report ? (
                      <AssignmentReportView report={report} />
                    ) : (
                      <Skeleton className="h-32 w-full" />
                    )}
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busyId === assignment.id}
                        onClick={() => onToggleOpen(assignment)}
                      >
                        {assignment.is_open ? 'Приключи заданието' : 'Отвори отново'}
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default ClassAssignmentsPanel;
