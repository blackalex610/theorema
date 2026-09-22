/** Formatting shared by the roster, profile, report and school screens. */

import { parseServerDate } from './assignmentDates';

/** Server timestamps are naive UTC; parse them as such before formatting. */
export const formatDate = (iso: string | null) => {
  const date = parseServerDate(iso);
  if (!date) return '—';
  return date.toLocaleDateString('bg-BG', { day: '2-digit', month: '2-digit', year: '2-digit' });
};

/** Colour follows the number, so a teacher scanning a class sees trouble first. */
export const scoreTone = (score: number | null) => {
  if (score === null) return 'text-ink-faint';
  if (score >= 70) return 'text-brand-ink';
  if (score >= 50) return 'text-warn';
  return 'text-danger';
};
