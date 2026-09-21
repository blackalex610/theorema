import { describe, it, expect } from 'vitest';
import { getExamDurationSeconds } from './nvoFormat';

describe('getExamDurationSeconds', () => {
  it('returns 30 minutes for the short NVO format', () => {
    expect(getExamDurationSeconds('short')).toBe(30 * 60);
  });

  it('returns 90 minutes for the full NVO format', () => {
    expect(getExamDurationSeconds('full')).toBe(90 * 60);
  });

  it('defaults to the full duration when format is undefined', () => {
    expect(getExamDurationSeconds(undefined)).toBe(90 * 60);
  });
});
