import { Skeleton } from '@/components/ui/skeleton';

/**
 * Shown while a lazily loaded route chunk is in flight. It mirrors the shape
 * every application page settles into (header row, then a content grid), so the
 * page does not jump when the real content arrives.
 */
const RouteFallback: React.FC = () => (
  <div className="min-h-dvh bg-paper">
    <div className="h-16 border-b border-line" />
    <div className="mx-auto w-full max-w-[75rem] shell-x py-10" role="status" aria-live="polite">
      <span className="sr-only">Страницата се зарежда</span>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-4 h-9 w-72 max-w-full" />
      <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-64 lg:col-span-2" />
        <Skeleton className="h-64" />
      </div>
    </div>
  </div>
);

export default RouteFallback;
