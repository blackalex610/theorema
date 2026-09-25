import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('./api', () => ({ default: { get: api.get, post: vi.fn(), delete: vi.fn() } }));

import { watchMobileChannel } from './mobileCapture';

const upload = (name: string) => ({ channel_id: 'ch', file_name: name, file_url: `/media/${name}` });
const context = (gradedAt: string | null) => ({
  channel_id: 'ch',
  problem_number: 34,
  last_grade: gradedAt ? { problem_number: 34, graded_at: gradedAt, is_correct: true } : null,
});

function serve(uploads: unknown[], contexts: unknown[]) {
  api.get.mockImplementation(async (url: string) => ({
    data: url.includes('uploads/latest') ? uploads : contexts,
  }));
}

describe('watchMobileChannel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    api.get.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it('reports only what arrives after the first poll', async () => {
    serve([upload('old.jpg')], [context('t0')]);
    const onUpload = vi.fn();
    const onGrade = vi.fn();
    const stop = watchMobileChannel('ch', { onUpload, onGrade }, 1000);
    await vi.advanceTimersByTimeAsync(0);
    expect(onUpload).not.toHaveBeenCalled();
    expect(onGrade).not.toHaveBeenCalled();

    serve([upload('new.jpg'), upload('old.jpg')], [context('t1')]);
    await vi.advanceTimersByTimeAsync(1000);
    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onUpload.mock.calls[0][0].file_name).toBe('new.jpg');
    expect(onGrade).toHaveBeenCalledTimes(1);
    expect(onGrade.mock.calls[0][0].graded_at).toBe('t1');

    await vi.advanceTimersByTimeAsync(1000);
    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onGrade).toHaveBeenCalledTimes(1);
    stop();
  });

  it('reports errors and recovers', async () => {
    api.get.mockRejectedValueOnce(new Error('offline'));
    const onStatus = vi.fn();
    const stop = watchMobileChannel('ch', { onStatus }, 1000);
    await vi.advanceTimersByTimeAsync(0);
    expect(onStatus).toHaveBeenLastCalledWith('error');

    serve([], []);
    await vi.advanceTimersByTimeAsync(1000);
    expect(onStatus).toHaveBeenLastCalledWith('live');
    stop();
  });

  it('stops polling when stopped', async () => {
    serve([], []);
    const stop = watchMobileChannel('ch', {}, 1000);
    await vi.advanceTimersByTimeAsync(0);
    const calls = api.get.mock.calls.length;
    stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(api.get.mock.calls.length).toBe(calls);
  });

  it('skips grade polling when nobody listens for grades', async () => {
    serve([], []);
    const stop = watchMobileChannel('ch', { onUpload: vi.fn() }, 1000);
    await vi.advanceTimersByTimeAsync(0);
    expect(api.get.mock.calls.every(([url]) => String(url).includes('uploads/latest'))).toBe(true);
    stop();
  });
});
