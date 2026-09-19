/**
 * Reconciling the exam page's local history with the server's attempt records.
 *
 * The page has always built its history list from localStorage alone, so a
 * student who switched devices or cleared site data lost every past score —
 * even though /nvo/submit had been writing a graded row per sitting the whole
 * time. `GET /nvo/attempts` reads those rows back; this merges them into
 * whatever the device already knows.
 *
 * Two rules decide every conflict:
 *
 *  - **The server owns the scores.** It graded the exam against its own stored
 *    answer key; the local copy is a display cache that can be stale or, for
 *    an attempt finished on another device, absent.
 *  - **The device owns the review payload.** Questions, submitted answers and
 *    marked-for-review flags exist only in localStorage. Generated exams drop
 *    out of the server's store after 24h, so a synthesized entry has no
 *    questions and the page must not offer a review for it.
 *
 * Entries that are not finished attempts (`ready`, `in_progress`) are local-only
 * by definition — the server never sees an exam that was not submitted — so
 * they pass through untouched.
 */

export type AttemptRecord = {
  exam_id: string;
  difficulty: string;
  format: string;
  score: number;
  max_score: number;
  percentage_correct: number;
  graded_at: string;
  created_at: string;
};

export type HistoryLike = {
  examId: string;
  status: 'ready' | 'in_progress' | 'unfinished' | 'completed';
  score: number;
  maxScore: number;
  scorePercent: number;
  questions: unknown[];
};

/** True when this entry carries the payload a per-question review needs. */
export const canReview = (entry: HistoryLike): boolean =>
  entry.questions.length > 0;

export function mergeServerAttempts<T extends HistoryLike>(
  local: T[],
  remote: AttemptRecord[],
  synthesize: (attempt: AttemptRecord) => T,
): T[] {
  const byExamId = new Map(remote.map((a) => [a.exam_id, a]));
  const seen = new Set<string>();

  const reconciled = local.map((entry) => {
    const attempt = entry.examId ? byExamId.get(entry.examId) : undefined;
    if (!attempt) return entry;
    seen.add(entry.examId);

    // A local entry the student never finished on this device may have been
    // submitted on another one. The server having graded it is what settles
    // that, so promote it rather than leaving a stale "Недовършен" badge.
    return {
      ...entry,
      status: 'completed' as const,
      score: attempt.score,
      maxScore: attempt.max_score,
      scorePercent: attempt.percentage_correct,
    };
  });

  const serverOnly = remote
    .filter((a) => !seen.has(a.exam_id))
    .map(synthesize);

  return [...reconciled, ...serverOnly];
}
