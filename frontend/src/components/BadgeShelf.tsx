import { useEffect, useState } from 'react';

import { getUserBadges, type UserBadge } from '../services/progress';
import { useIsDevMode } from '../context/DeveloperModeContext';
import { SectionHeading } from './app/PageShell';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export default function BadgeShelf() {
  const isDevMode = useIsDevMode();
  const [badges, setBadges] = useState<UserBadge[]>([]);

  useEffect(() => {
    if (!isDevMode) return;
    getUserBadges().then(setBadges).catch(() => {});
  }, [isDevMode]);

  if (!isDevMode || badges.length === 0) return null;

  return (
    <section>
      <SectionHeading title="Значки" description="Отключени за постигнати цели." />
      <ul className="flex flex-wrap gap-2">
        {badges.map((badge) => (
          <li key={badge.key}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  tabIndex={0}
                  className="flex w-24 flex-col items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-3 text-center shadow-lift-1 transition-colors hover:border-brand"
                >
                  <span aria-hidden="true" className="text-2xl leading-none">
                    {badge.emoji}
                  </span>
                  <span className="text-caption font-semibold text-ink">{badge.title}</span>
                </span>
              </TooltipTrigger>
              <TooltipContent>{badge.description}</TooltipContent>
            </Tooltip>
          </li>
        ))}
      </ul>
    </section>
  );
}
