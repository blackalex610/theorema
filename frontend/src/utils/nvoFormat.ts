import type { NVOFormat } from '../components/NVOFormatSelector';

export const SHORT_EXAM_DURATION_SECONDS = 30 * 60;
export const FULL_EXAM_DURATION_SECONDS = 90 * 60;

export function getExamDurationSeconds(format: NVOFormat | undefined): number {
  return format === 'short' ? SHORT_EXAM_DURATION_SECONDS : FULL_EXAM_DURATION_SECONDS;
}
