import { WarningCircleIcon } from '@phosphor-icons/react';

import type { TopicRow } from '../../services/classrooms';
import {
  SMALL_SAMPLE_NOTE,
  groupByStrand,
  isSmallSample,
  masteryTone,
} from '../../utils/topicDiagnostics';

/**
 * How a class performed, topic by topic, grouped by curriculum strand.
 *
 * Deliberately a table rather than a colour grid. A teacher needs to see the
 * sample size next to every percentage — "30% correct" means one thing over
 * 40 questions and nothing at all over three — and a coloured square cannot
 * carry that. The bar is there to make the ranking scannable, not to be the
 * only way to read the number.
 */

const barTone: Record<string, string> = {
  danger: 'bg-danger',
  warn: 'bg-warn',
  ok: 'bg-brand',
  empty: 'bg-line-strong',
};

const textTone: Record<string, string> = {
  danger: 'text-danger',
  warn: 'text-warn',
  ok: 'text-brand-ink',
  empty: 'text-ink-faint',
};

const TopicBar: React.FC<{ percent: number; muted: boolean }> = ({ percent, muted }) => (
  <span
    className="block h-2 w-full overflow-hidden rounded-full bg-sunken"
    role="presentation"
  >
    <span
      className={`block h-full rounded-full transition-[width] duration-500 ${
        muted ? 'bg-line-strong' : barTone[masteryTone(percent)]
      }`}
      style={{ width: `${Math.max(percent, 2)}%` }}
    />
  </span>
);

const TopicHeatmap: React.FC<{
  topics: TopicRow[];
  minAsked: number;
  /** Shown per row when the class is the unit; hidden for one student. */
  showStudents?: boolean;
}> = ({ topics, minAsked, showStudents = true }) => {
  const groups = groupByStrand(topics);

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.key}>
          <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-line pb-2">
            <h3 className="font-display text-body font-semibold text-ink">{group.label}</h3>
            <span className="tnum text-caption text-ink-muted">
              <span className={`font-semibold ${textTone[masteryTone(group.percentCorrect)]}`}>
                {group.percentCorrect}%
              </span>{' '}
              от {group.asked} задачи
            </span>
          </div>

          <ul className="space-y-2.5">
            {group.topics.map((topic) => {
              const weak = isSmallSample(topic, minAsked);
              return (
                /* Fixed number column: with `auto`, each row sized it to its
                   own figures and the bars stopped lining up down the list. */
                <li key={topic.key} className="grid grid-cols-[minmax(0,1fr)_9.5rem] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[minmax(0,1fr)_8rem_9.5rem]">
                  <span className="col-span-2 flex min-w-0 items-center gap-1.5 sm:col-span-1">
                    <span className="truncate text-caption text-ink">{topic.label}</span>
                    {weak && (
                      <span
                        title={SMALL_SAMPLE_NOTE}
                        aria-label={SMALL_SAMPLE_NOTE}
                        className="shrink-0 text-ink-faint"
                      >
                        <WarningCircleIcon aria-hidden="true" className="size-3.5" />
                      </span>
                    )}
                  </span>

                  <span className="min-w-0">
                    <TopicBar percent={topic.percent_correct} muted={weak} />
                  </span>

                  <span className="tnum whitespace-nowrap text-right text-caption">
                    <span
                      className={`font-semibold ${
                        weak ? 'text-ink-faint' : textTone[masteryTone(topic.percent_correct)]
                      }`}
                    >
                      {topic.percent_correct}%
                    </span>
                    {/* Sample size always travels with the percentage. */}
                    <span className="ml-1.5 text-ink-faint">
                      {topic.correct}/{topic.asked}
                      {showStudents && topic.students > 0 && ` · ${topic.students} уч.`}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
};

export default TopicHeatmap;
