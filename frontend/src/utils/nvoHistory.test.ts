import { describe, it, expect } from 'vitest';
import { mergeServerAttempts, canReview, type AttemptRecord, type HistoryLike } from './nvoHistory';

type Entry = HistoryLike & { examId: string; note?: string };

const attempt = (overrides: Partial<AttemptRecord> = {}): AttemptRecord => ({
  exam_id: 'exam-1',
  difficulty: 'standard',
  format: 'full',
  score: 14,
  max_score: 23,
  percentage_correct: 61,
  graded_at: '2026-09-18T10:00:00',
  created_at: '2026-09-18T09:00:00',
  ...overrides,
});

const entry = (overrides: Partial<Entry> = {}): Entry => ({
  examId: 'exam-1',
  status: 'completed',
  score: 0,
  maxScore: 0,
  scorePercent: 0,
  questions: [],
  ...overrides,
});

const synthesize = (a: AttemptRecord): Entry => ({
  examId: a.exam_id,
  status: 'completed',
  score: a.score,
  maxScore: a.max_score,
  scorePercent: a.percentage_correct,
  questions: [],
});

describe('mergeServerAttempts', () => {
  it('returns local history untouched when the server has nothing', () => {
    const local = [entry({ examId: 'a', score: 5, maxScore: 10 })];
    expect(mergeServerAttempts(local, [], synthesize)).toEqual(local);
  });

  it('adds an attempt this device has never seen', () => {
    const merged = mergeServerAttempts([], [attempt({ exam_id: 'from-phone' })], synthesize);

    expect(merged).toHaveLength(1);
    expect(merged[0].examId).toBe('from-phone');
    expect(merged[0].score).toBe(14);
  });

  it('lets the server correct a stale local score', () => {
    const local = [entry({ examId: 'exam-1', score: 99, maxScore: 99, scorePercent: 100 })];

    const [merged] = mergeServerAttempts(local, [attempt()], synthesize);

    expect(merged.score).toBe(14);
    expect(merged.maxScore).toBe(23);
    expect(merged.scorePercent).toBe(61);
  });

  it('keeps the local review payload while taking the server score', () => {
    const local = [entry({ examId: 'exam-1', questions: [{ id: 1 }, { id: 2 }], note: 'local' })];

    const [merged] = mergeServerAttempts(local, [attempt()], synthesize);

    expect(merged.questions).toHaveLength(2);
    expect(merged.note).toBe('local');
    expect(merged.score).toBe(14);
  });

  it('never duplicates an attempt the device already has', () => {
    const local = [entry({ examId: 'exam-1' })];

    expect(mergeServerAttempts(local, [attempt()], synthesize)).toHaveLength(1);
  });

  it('promotes an attempt left unfinished here but submitted elsewhere', () => {
    const local = [entry({ examId: 'exam-1', status: 'unfinished' })];

    const [merged] = mergeServerAttempts(local, [attempt()], synthesize);

    expect(merged.status).toBe('completed');
  });

  it('leaves a not-yet-started exam alone', () => {
    // The server only ever records submitted exams, so a `ready` entry can
    // never match one — but it must survive the merge regardless.
    const local = [entry({ examId: 'exam-9', status: 'ready' })];

    const [merged] = mergeServerAttempts(local, [attempt()], synthesize);

    expect(merged.status).toBe('ready');
  });

  it('ignores a local entry with no exam id instead of matching it to anything', () => {
    const local = [entry({ examId: '', score: 3 })];

    const merged = mergeServerAttempts(local, [attempt({ exam_id: '' })], synthesize);

    expect(merged[0].score).toBe(3);
    expect(merged).toHaveLength(2); // the server attempt still arrives on its own
  });

  it('merges several attempts across devices at once', () => {
    const local = [entry({ examId: 'here' })];
    const remote = [attempt({ exam_id: 'here' }), attempt({ exam_id: 'there' })];

    expect(mergeServerAttempts(local, remote, synthesize).map((e) => e.examId))
      .toEqual(['here', 'there']);
  });
});

describe('canReview', () => {
  it('is false for a server-only attempt, whose questions never left the other device', () => {
    expect(canReview(synthesize(attempt()))).toBe(false);
  });

  it('is true once the device holds the questions', () => {
    expect(canReview(entry({ questions: [{ id: 1 }] }))).toBe(true);
  });
});
