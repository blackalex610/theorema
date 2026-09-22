import type { TopicRow } from '../services/classrooms';

/**
 * Shaping topic results for the screen a teacher reads.
 *
 * The rule running through all of it: a number that looks precise and is
 * built on two questions is worse than no number, so sample size travels
 * with every figure and weak samples are marked rather than hidden.
 */

export type MasteryTone = 'danger' | 'warn' | 'ok' | 'empty';

/** Bands chosen to match how the roster already colours a score. */
export const masteryTone = (percent: number | null): MasteryTone => {
  if (percent === null) return 'empty';
  if (percent >= 70) return 'ok';
  if (percent >= 50) return 'warn';
  return 'danger';
};

export const SMALL_SAMPLE_NOTE =
  'Твърде малко зададени задачи, за да се смята за извод.';

/** True when there is too little behind a topic to draw a conclusion. */
export const isSmallSample = (topic: TopicRow, minAsked: number): boolean =>
  topic.asked < minAsked;

export interface StrandGroup {
  key: string;
  label: string;
  asked: number;
  correct: number;
  percentCorrect: number;
  topics: TopicRow[];
}

const UNIDENTIFIED = '__other__';

/**
 * Group topics by curriculum strand, weakest strand first.
 *
 * Each strand's percentage is computed from its own questions rather than
 * by averaging its topics' percentages — a topic asked 90 times and one
 * asked 10 do not carry the same weight, and an average of averages would
 * quietly pretend they do.
 *
 * Topics the server could not identify (`strand: null`) are kept in their
 * own group at the end. They belong to no strand, and folding them into one
 * would put unrecognised questions inside a real subject's number.
 */
export const groupByStrand = (topics: TopicRow[]): StrandGroup[] => {
  const groups = new Map<string, StrandGroup>();

  for (const topic of topics) {
    const key = topic.strand ?? UNIDENTIFIED;
    const group = groups.get(key) ?? {
      key,
      label: topic.strand_label,
      asked: 0,
      correct: 0,
      percentCorrect: 0,
      topics: [],
    };
    group.asked += topic.asked;
    group.correct += topic.correct;
    group.topics.push(topic);
    groups.set(key, group);
  }

  const ordered = [...groups.values()].map((group) => ({
    ...group,
    percentCorrect: group.asked ? Math.round((100 * group.correct) / group.asked) : 0,
    topics: [...group.topics].sort((a, b) => a.percent_correct - b.percent_correct),
  }));

  ordered.sort((a, b) => {
    // Unidentified always last: it is a data-quality signal, not a subject.
    if (a.key === UNIDENTIFIED) return 1;
    if (b.key === UNIDENTIFIED) return -1;
    return a.percentCorrect - b.percentCorrect;
  });

  return ordered;
};
