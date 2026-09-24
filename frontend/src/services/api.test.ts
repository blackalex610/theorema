import { describe, expect, it } from 'vitest';
import { apiErrorMessage, getLimitErrorDetail, isLimitError } from './api';

const httpError = (status: number, detail: unknown) => ({ response: { status, data: { detail } } });

describe('apiErrorMessage', () => {
  it('uses a string detail', () => {
    expect(apiErrorMessage(httpError(502, 'AI услугата не отговаря'), 'fallback')).toBe('AI услугата не отговаря');
  });

  it('uses detail.message from a structured error instead of rendering the object', () => {
    const limit = { code: 'LIMIT_REACHED', feature: 'ai_theory', message: 'Достигнахте дневния лимит' };
    expect(apiErrorMessage(httpError(429, limit), 'fallback')).toBe('Достигнахте дневния лимит');
  });

  it('falls back for network errors and non-errors', () => {
    expect(apiErrorMessage(new Error('Network Error'), 'fallback')).toBe('fallback');
    expect(apiErrorMessage(null, 'fallback')).toBe('fallback');
    expect(apiErrorMessage(httpError(500, { unexpected: true }), 'fallback')).toBe('fallback');
  });
});

describe('limit errors', () => {
  it('recognises a plan-limit 429', () => {
    const error = httpError(429, { code: 'LIMIT_REACHED', feature: 'ai_chat', message: 'лимит' });
    expect(isLimitError(error)).toBe(true);
    expect(getLimitErrorDetail(error)).toEqual({ feature: 'ai_chat', message: 'лимит' });
  });

  it('does not mistake a rate-limit 429 for a plan limit', () => {
    expect(isLimitError(httpError(429, { code: 'RATE_LIMITED', message: 'бавно' }))).toBe(false);
  });
});
