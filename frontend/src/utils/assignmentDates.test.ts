import { describe, expect, it } from 'vitest';

import { dueDateToIso, isOverdue } from './assignmentDates';

describe('dueDateToIso', () => {
  it('turns a picked day into the last minute of that day, local time', () => {
    const iso = dueDateToIso('2030-10-01');
    const due = new Date(iso as string);

    expect(due.getFullYear()).toBe(2030);
    expect(due.getMonth()).toBe(9);
    expect(due.getDate()).toBe(1);
    expect(due.getHours()).toBe(23);
    expect(due.getMinutes()).toBe(59);
  });

  it('sends no due date when none was picked', () => {
    expect(dueDateToIso('')).toBeNull();
  });

  it('rejects something that is not a date rather than sending garbage', () => {
    expect(dueDateToIso('not-a-date')).toBeNull();
  });
});

describe('isOverdue', () => {
  const now = new Date('2030-10-02T10:00:00Z');

  it('is overdue once the due moment has passed', () => {
    expect(isOverdue('2030-10-01T20:59:00', now)).toBe(true);
  });

  it('is not overdue before it', () => {
    expect(isOverdue('2030-10-05T20:59:00', now)).toBe(false);
  });

  it('is never overdue without a due date', () => {
    expect(isOverdue(null, now)).toBe(false);
  });

  it('reads the server’s naive timestamps as UTC, which is what they are', () => {
    // 2030-10-02T09:30 UTC is before `now` (10:00 UTC) whatever the browser's zone.
    expect(isOverdue('2030-10-02T09:30:00', now)).toBe(true);
    expect(isOverdue('2030-10-02T10:30:00', now)).toBe(false);
  });
});
