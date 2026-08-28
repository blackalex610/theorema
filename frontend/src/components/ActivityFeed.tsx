import { useEffect, useState } from 'react';
import {
  CameraIcon,
  FireIcon,
  ListChecksIcon,
  PencilSimpleLineIcon,
  StarIcon,
} from '@phosphor-icons/react';

import { getActivityFeed, type ActivityEvent } from '../services/progress';
import { EmptyState } from './app/PageShell';
import { Skeleton } from '@/components/ui/skeleton';

/** Each XP event carries the icon of the thing that earned it. */
const SOURCE_ICON: Record<string, React.ComponentType<{ className?: string; weight?: 'fill' }>> = {
  exercise: PencilSimpleLineIcon,
  streak: FireIcon,
  nvo_exam: ListChecksIcon,
  mission: StarIcon,
  image_scan: CameraIcon,
};

function timeAgo(isoString: string): string {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60) return 'преди секунди';
  if (diff < 3600) return `преди ${Math.floor(diff / 60)} мин`;
  if (diff < 86400) return `преди ${Math.floor(diff / 3600)} ч`;
  return `преди ${Math.floor(diff / 86400)} дни`;
}

export default function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getActivityFeed(15)
      .then(setEvents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-2" role="status" aria-live="polite">
        <span className="sr-only">Историята се зарежда</span>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-11" />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        icon={<StarIcon weight="duotone" />}
        title="Още няма записана активност"
        description="Всяка решена задача и всеки завършен урок се появяват тук."
      />
    );
  }

  return (
    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
      {events.map((event) => {
        const Icon = SOURCE_ICON[event.source_type] ?? StarIcon;
        return (
          <li key={event.id} className="flex items-center gap-3 px-4 py-3">
            <Icon weight="fill" className="size-4 shrink-0 text-ink-faint" />
            <span className="min-w-0 flex-1 truncate text-caption text-ink">{event.reason}</span>
            <span className="tnum shrink-0 text-caption font-semibold text-brand-ink">
              +{event.xp_amount} XP
            </span>
            <span className="hidden w-24 shrink-0 text-right text-caption text-ink-faint sm:block">
              {timeAgo(event.created_at)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
