import * as React from 'react';
import { Link } from 'react-router-dom';
import { ArrowClockwiseIcon, CaretRightIcon, WarningIcon } from '@phosphor-icons/react';

import { Reveal } from '@/components/motion/Reveal';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * The layout vocabulary every application page is built from.
 *
 * Pages stopped inventing their own max-widths and paddings when this landed;
 * the measured column and the vertical rhythm now live in exactly one place.
 */

export const PageShell: React.FC<
  React.PropsWithChildren<{ className?: string; wide?: boolean }>
> = ({ children, className, wide = false }) => (
  <main
    className={cn(
      'mx-auto w-full shell-x pb-24 pt-8 sm:pt-10',
      wide ? 'max-w-[90rem]' : 'max-w-[75rem]',
      className
    )}
  >
    {children}
  </main>
);

export type Crumb = { label: string; to?: string };

export const Breadcrumbs: React.FC<{ items: Crumb[] }> = ({ items }) => (
  <nav aria-label="Навигация по нива">
    <ol className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted">
      {items.map((item, index) => (
        <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
          {index > 0 && <CaretRightIcon aria-hidden="true" className="size-3 text-ink-faint" />}
          {item.to ? (
            <Link to={item.to} className="rounded transition-colors hover:text-ink">
              {item.label}
            </Link>
          ) : (
            <span className="text-ink" aria-current="page">
              {item.label}
            </span>
          )}
        </li>
      ))}
    </ol>
  </nav>
);

export const PageHeader: React.FC<{
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Use sparingly. One kicker per page at most, and only when it classifies. */
  kicker?: string;
  crumbs?: Crumb[];
  actions?: React.ReactNode;
  className?: string;
}> = ({ title, description, kicker, crumbs, actions, className }) => (
  <Reveal className={cn('mb-8 flex flex-col gap-4', className)}>
    {crumbs && crumbs.length > 0 && <Breadcrumbs items={crumbs} />}
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 space-y-2">
        {kicker && (
          <p className="text-micro font-semibold uppercase tracking-[0.1em] text-brand-ink">
            {kicker}
          </p>
        )}
        <h1 className="text-section font-display font-semibold text-ink">{title}</h1>
        {description && (
          <p className="max-w-2xl text-lead text-ink-muted">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  </Reveal>
);

/** A single measured value. The number always carries the mono face. */
export const StatTile: React.FC<{
  label: string;
  value: React.ReactNode;
  suffix?: string;
  hint?: string;
  tone?: 'default' | 'brand' | 'warn';
  onClick?: () => void;
}> = ({ label, value, suffix, hint, tone = 'default', onClick }) => {
  const Comp = onClick ? 'button' : 'div';
  return (
    <Comp
      {...(onClick ? { onClick, type: 'button' as const } : {})}
      className={cn(
        'flex flex-col gap-1 rounded-xl border border-line bg-surface p-5 text-left shadow-lift-1 transition-[border-color,box-shadow] duration-200',
        onClick && 'hover:border-brand hover:shadow-lift-2'
      )}
    >
      <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
        {label}
      </span>
      <span className="flex items-baseline gap-1">
        <span
          className={cn(
            'tnum text-[2rem] font-semibold leading-none',
            tone === 'brand' && 'text-brand-ink',
            tone === 'warn' && 'text-warn',
            tone === 'default' && 'text-ink'
          )}
        >
          {value}
        </span>
        {suffix && <span className="tnum text-title text-ink-faint">{suffix}</span>}
      </span>
      {hint && <span className="text-caption text-ink-muted">{hint}</span>}
    </Comp>
  );
};

/** Nothing here yet. An empty screen is an invitation to act, not an apology. */
export const EmptyState: React.FC<{
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}> = ({ title, description, action, icon }) => (
  <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
    {icon && <span className="text-ink-faint [&_svg]:size-8">{icon}</span>}
    <h3 className="font-display text-title font-semibold text-ink">{title}</h3>
    {description && <p className="max-w-md text-body text-ink-muted">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);

/** Something failed. Say what happened and how to get past it. */
export const ErrorState: React.FC<{
  title?: string;
  description: string;
  onRetry?: () => void;
  retryLabel?: string;
}> = ({ title = 'Данните не се заредиха', description, onRetry, retryLabel = 'Опитай пак' }) => (
  <div
    role="alert"
    className="flex flex-col gap-3 rounded-xl border border-danger-edge bg-danger-wash p-5 sm:flex-row sm:items-center sm:justify-between"
  >
    <div className="flex items-start gap-3">
      <WarningIcon weight="fill" aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-danger" />
      <div className="space-y-0.5">
        <p className="text-body font-semibold text-ink">{title}</p>
        <p className="text-caption text-ink-muted">{description}</p>
      </div>
    </div>
    {onRetry && (
      <Button variant="outline" size="sm" onClick={onRetry} className="shrink-0 self-start sm:self-auto">
        <ArrowClockwiseIcon />
        {retryLabel}
      </Button>
    )}
  </div>
);

/** A row of section-level structure: heading plus optional trailing control. */
export const SectionHeading: React.FC<{
  title: string;
  description?: string;
  action?: React.ReactNode;
  id?: string;
  className?: string;
}> = ({ title, description, action, id, className }) => (
  <div
    id={id}
    className={cn('mb-4 flex items-end justify-between gap-4 scroll-mt-24', className)}
  >
    <div className="space-y-1">
      <h2 className="font-display text-title font-semibold text-ink">{title}</h2>
      {description && <p className="text-caption text-ink-muted">{description}</p>}
    </div>
    {action}
  </div>
);
