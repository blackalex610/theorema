/** Bulgarian date and time, e.g. "20.09.2026 г., 14:05". */
export const formatBgDateTime = (iso: string) => {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString('bg-BG', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};
