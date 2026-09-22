import { describe, expect, it } from 'vitest';

import {
  SMALL_SAMPLE_NOTE,
  groupByStrand,
  isSmallSample,
  masteryTone,
} from './topicDiagnostics';
import type { TopicRow } from '../services/classrooms';

const topic = (over: Partial<TopicRow> = {}): TopicRow => ({
  key: 'inequality',
  label: 'Неравенства',
  strand: 'algebra',
  strand_label: 'Алгебра',
  asked: 10,
  correct: 5,
  percent_correct: 50,
  students: 3,
  ...over,
});

describe('masteryTone', () => {
  it('flags a failing topic as trouble', () => {
    expect(masteryTone(20)).toBe('danger');
  });

  it('treats the middle as a warning rather than a failure', () => {
    expect(masteryTone(55)).toBe('warn');
  });

  it('treats a strong topic as fine', () => {
    expect(masteryTone(85)).toBe('ok');
  });

  it('has no tone for a topic with nothing behind it', () => {
    expect(masteryTone(null)).toBe('empty');
  });
});

describe('isSmallSample', () => {
  it('marks a topic asked fewer times than the threshold', () => {
    expect(isSmallSample(topic({ asked: 2 }), 3)).toBe(true);
  });

  it('does not mark one that reaches the threshold', () => {
    expect(isSmallSample(topic({ asked: 3 }), 3)).toBe(false);
  });
});

describe('groupByStrand', () => {
  it('groups topics under their curriculum strand', () => {
    const groups = groupByStrand([
      topic({ key: 'inequality', strand: 'algebra', strand_label: 'Алгебра' }),
      topic({ key: 'linear_equation', strand: 'algebra', strand_label: 'Алгебра' }),
      topic({ key: 'geom_triangle', strand: 'geometry', strand_label: 'Геометрия' }),
    ]);

    expect(groups.map((g) => g.label)).toEqual(['Алгебра', 'Геометрия']);
    expect(groups[0].topics).toHaveLength(2);
  });

  it('keeps the weakest strand first, so trouble is read first', () => {
    const groups = groupByStrand([
      topic({ key: 'powers', strand: 'arithmetic', strand_label: 'Аритметика', percent_correct: 90, asked: 10, correct: 9 }),
      topic({ key: 'inequality', strand: 'algebra', strand_label: 'Алгебра', percent_correct: 20, asked: 10, correct: 2 }),
    ]);

    expect(groups[0].label).toBe('Алгебра');
  });

  it('puts unidentified topics last and never inside a real strand', () => {
    const groups = groupByStrand([
      topic({ key: 'other', strand: null, strand_label: 'Друго', percent_correct: 10, asked: 20, correct: 2 }),
      topic({ key: 'inequality', strand: 'algebra', strand_label: 'Алгебра', percent_correct: 80 }),
    ]);

    expect(groups[groups.length - 1].label).toBe('Друго');
    expect(groups.find((g) => g.label === 'Алгебра')?.topics.map((t) => t.key)).toEqual([
      'inequality',
    ]);
  });

  it('computes each strand percentage from its own questions, not from an average of averages', () => {
    const groups = groupByStrand([
      topic({ key: 'inequality', strand: 'algebra', strand_label: 'Алгебра', asked: 90, correct: 90, percent_correct: 100 }),
      topic({ key: 'linear_equation', strand: 'algebra', strand_label: 'Алгебра', asked: 10, correct: 0, percent_correct: 0 }),
    ]);

    // Mean of the two topic percentages would be 50; the honest figure is 90.
    expect(groups[0].percentCorrect).toBe(90);
  });

  it('returns nothing for no data rather than an empty strand list', () => {
    expect(groupByStrand([])).toEqual([]);
  });
});

describe('SMALL_SAMPLE_NOTE', () => {
  it('is written in Bulgarian for the teacher reading it', () => {
    expect(SMALL_SAMPLE_NOTE).toMatch(/[а-яА-Я]/);
  });
});
