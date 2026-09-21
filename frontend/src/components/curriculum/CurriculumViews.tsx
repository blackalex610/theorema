import { useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRightIcon,
  BookOpenIcon,
  CheckCircleIcon,
  PencilSimpleLineIcon,
} from '@phosphor-icons/react';

import type { Grade, Lesson, Topic } from '../../services/curriculum';
import type { LessonProgress, TopicProgress } from '../../services/progress';
import { EmptyState } from '../app/PageShell';
import { RevealGroup, RevealItem } from '@/components/motion/Reveal';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/**
 * The three levels of the curriculum browser: grade, topic, lesson.
 *
 * Both tracks (practice and theory) walk the same hierarchy, so they share
 * these views and differ only in where a click lands. Previously this was six
 * near-identical page files that had already drifted apart from each other.
 */

/** What a class is actually about, in the words a student would use. */
const GRADE_SUMMARY: Record<number, { blurb: string; strands: string[] }> = {
  5: {
    blurb: 'Действия с естествени и дробни числа, основни геометрични фигури, текстови задачи.',
    strands: ['Дроби и десетични числа', 'Лице и периметър', 'Текстови задачи'],
  },
  6: {
    blurb: 'Цели и рационални числа, отношения и проценти, първи уравнения, обеми на тела.',
    strands: ['Рационални числа', 'Проценти', 'Обеми'],
  },
  7: {
    blurb: 'Алгебрични тъждества, уравнения и неравенства, еднаквост на триъгълници, изпитният материал.',
    strands: ['Тъждества', 'Уравнения', 'Геометрия', 'Материал за НВО'],
  },
};

/* ── Grades ──────────────────────────────────────────────────────────────── */

export const GradeGrid: React.FC<{ grades: Grade[]; toPath: (grade: Grade) => string }> = ({
  grades,
  toPath,
}) => {
  const navigate = useNavigate();

  if (grades.length === 0) {
    return (
      <EmptyState
        icon={<BookOpenIcon weight="duotone" />}
        title="Няма налични класове"
        description="Учебното съдържание не се зареди. Опресни страницата след малко."
      />
    );
  }

  return (
    <RevealGroup className="grid gap-4 md:grid-cols-3">
      {grades.map((grade) => {
        const meta = GRADE_SUMMARY[grade.grade_number];
        return (
          <RevealItem key={grade.id}>
            <button
              type="button"
              onClick={() => navigate(toPath(grade))}
              className="group flex h-full w-full flex-col gap-4 rounded-xl border border-line bg-surface p-6 text-left shadow-lift-1 transition-[border-color,box-shadow] duration-200 hover:border-brand hover:shadow-lift-2"
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="flex items-baseline gap-1.5">
                  <span className="tnum text-[2.5rem] font-semibold leading-none text-ink">
                    {grade.grade_number}
                  </span>
                  <span className="text-title text-ink-muted">клас</span>
                </span>
                <ArrowRightIcon
                  aria-hidden="true"
                  className="size-5 text-ink-faint transition-transform duration-200 group-hover:translate-x-1 group-hover:text-brand"
                />
              </span>

              <span className="text-body text-ink-muted">
                {meta?.blurb ?? 'Задачи по математика за този клас.'}
              </span>

              <span className="mt-auto flex flex-wrap gap-1.5">
                {(meta?.strands ?? []).map((strand) => (
                  <Badge key={strand} variant="neutral" className="normal-case tracking-normal">
                    {strand}
                  </Badge>
                ))}
              </span>
            </button>
          </RevealItem>
        );
      })}
    </RevealGroup>
  );
};

/* ── Topics ──────────────────────────────────────────────────────────────── */

export const TopicList: React.FC<{
  topics: Topic[];
  progress?: Map<number, TopicProgress>;
  toPath: (topic: Topic) => string;
}> = ({ topics, progress, toPath }) => {
  const navigate = useNavigate();
  const reduced = useReducedMotion();

  if (topics.length === 0) {
    return (
      <EmptyState
        icon={<BookOpenIcon weight="duotone" />}
        title="Няма теми за този клас"
        description="Съдържанието за този клас още се подготвя."
      />
    );
  }

  return (
    <RevealGroup className="grid gap-3 md:grid-cols-2">
      {topics.map((topic) => {
        const stat = progress?.get(topic.id);
        return (
          <RevealItem key={topic.id}>
            <button
              type="button"
              onClick={() => navigate(toPath(topic))}
              className="group flex h-full w-full flex-col gap-3 rounded-xl border border-line bg-surface p-5 text-left shadow-lift-1 transition-[border-color,box-shadow] duration-200 hover:border-brand hover:shadow-lift-2"
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="block text-title font-display font-semibold text-ink">
                    {topic.title}
                  </span>
                  {topic.description && (
                    <span className="mt-1 block text-caption text-ink-muted">
                      {topic.description}
                    </span>
                  )}
                </span>
                {stat?.needs_practice && <Badge variant="warn">за повторение</Badge>}
              </span>

              {stat && (
                <span className="mt-auto space-y-1.5">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="tnum text-caption text-ink-muted">
                      {stat.completed_exercises} / {stat.total_exercises} задачи
                    </span>
                    <span
                      className={cn(
                        'tnum text-caption font-semibold',
                        stat.accuracy >= 80
                          ? 'text-brand-ink'
                          : stat.accuracy >= 60
                            ? 'text-ink'
                            : 'text-warn'
                      )}
                    >
                      {stat.accuracy.toFixed(0)}% точност
                    </span>
                  </span>
                  <span className="block h-1.5 overflow-hidden rounded-full bg-sunken">
                    <motion.span
                      initial={reduced ? false : { width: 0 }}
                      whileInView={{ width: `${stat.progress_percentage}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                      className="block h-full rounded-full bg-brand"
                    />
                  </span>
                </span>
              )}
            </button>
          </RevealItem>
        );
      })}
    </RevealGroup>
  );
};

/* ── Lessons ─────────────────────────────────────────────────────────────── */

export const LessonList: React.FC<{
  lessons: Lesson[];
  progress?: Map<number, LessonProgress>;
  toPath: (lesson: Lesson) => string;
  /** Shown on the row so the destination is never a surprise. */
  actionLabel: string;
}> = ({ lessons, progress, toPath, actionLabel }) => {
  const navigate = useNavigate();

  if (lessons.length === 0) {
    return (
      <EmptyState
        icon={<BookOpenIcon weight="duotone" />}
        title="Няма уроци по тази тема"
        description="Съдържанието по темата още се подготвя."
      />
    );
  }

  return (
    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
      {lessons.map((lesson, index) => {
        const stat = progress?.get(lesson.id);
        const done = stat?.completed ?? false;
        return (
          <li key={lesson.id}>
            <button
              type="button"
              onClick={() => navigate(toPath(lesson))}
              className="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors duration-200 hover:bg-sunken"
            >
              <span
                aria-hidden="true"
                className={cn(
                  'tnum inline-flex size-8 shrink-0 items-center justify-center rounded-lg border text-caption font-semibold',
                  done
                    ? 'border-brand bg-brand text-white'
                    : 'border-line text-ink-muted'
                )}
              >
                {done ? <CheckCircleIcon weight="fill" className="size-4" /> : index + 1}
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-body font-semibold text-ink">
                  {lesson.title}
                </span>
                {stat && stat.total_exercises > 0 && (
                  <span className="tnum mt-0.5 block text-caption text-ink-muted">
                    {stat.completed_exercises} от {stat.total_exercises} задачи решени
                  </span>
                )}
              </span>

              {stat && stat.total_exercises > 0 && (
                <span className="hidden w-32 shrink-0 sm:block">
                  <Progress value={stat.progress_percentage} />
                </span>
              )}

              <span className="hidden shrink-0 items-center gap-1.5 text-caption font-semibold text-ink-muted transition-colors group-hover:text-brand-ink md:inline-flex">
                {actionLabel}
                <ArrowRightIcon className="size-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
              </span>
              <ArrowRightIcon
                aria-hidden="true"
                className="size-4 shrink-0 text-ink-faint md:hidden"
              />
            </button>
          </li>
        );
      })}
    </ul>
  );
};

/* ── Loading ─────────────────────────────────────────────────────────────── */

export const CurriculumSkeleton: React.FC<{ rows?: number; columns?: 1 | 2 | 3 }> = ({
  rows = 6,
  columns = 2,
}) => (
  <div
    className={cn(
      'grid gap-3',
      columns === 3 && 'md:grid-cols-3',
      columns === 2 && 'md:grid-cols-2'
    )}
    role="status"
    aria-live="polite"
  >
    <span className="sr-only">Съдържанието се зарежда</span>
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className={columns === 1 ? 'h-16' : 'h-32'} />
    ))}
  </div>
);

export const practiceIcon = <PencilSimpleLineIcon weight="duotone" />;
