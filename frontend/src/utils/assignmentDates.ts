/**
 * Due dates cross a timezone boundary twice, and both crossings matter.
 *
 * Outbound, a teacher picks a *day* in Bulgaria; "due 1 October" means the
 * end of that day where they are, not midnight UTC (which is 03:00 the
 * same morning in Sofia, and would close the homework before school).
 *
 * Inbound, the server stores and returns naive UTC timestamps with no
 * offset. `new Date()` reads an offset-less string as *local* time, which
 * would shift every deadline by two or three hours — so they are read as
 * UTC explicitly.
 */

/** A picked `YYYY-MM-DD` as 23:59 local time on that day, in ISO form. */
export const dueDateToIso = (day: string): string | null => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const [year, month, date] = day.split('-').map(Number);
  const due = new Date(year, month - 1, date, 23, 59, 0, 0);
  return Number.isNaN(due.getTime()) ? null : due.toISOString();
};

/** Parse a server timestamp, which is naive UTC. */
export const parseServerDate = (iso: string | null): Date | null => {
  if (!iso) return null;
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const parsed = new Date(hasZone ? iso : `${iso}Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const isOverdue = (dueIso: string | null, now: Date = new Date()): boolean => {
  const due = parseServerDate(dueIso);
  return due !== null && due.getTime() < now.getTime();
};

export const formatDue = (dueIso: string | null): string => {
  const due = parseServerDate(dueIso);
  if (!due) return 'без срок';
  return `до ${due.toLocaleDateString('bg-BG', { day: '2-digit', month: '2-digit' })}`;
};
