import { cn } from '@/lib/utils';

/**
 * The wordmark.
 *
 * Typographic, not drawn: a sigma set in the mono face on a brand plate, next
 * to the name in the display face. The sigma is the product's own material,
 * and keeping it as live text means it inherits the type system instead of
 * living as a separate asset that drifts out of sync.
 */

type BrandProps = {
  className?: string;
  /** Hide the wordmark and keep only the plate (collapsed nav, mobile bar). */
  markOnly?: boolean;
  size?: 'sm' | 'md';
};

export const BrandMark: React.FC<{ className?: string; size?: 'sm' | 'md' }> = ({
  className,
  size = 'md',
}) => (
  <span
    aria-hidden="true"
    className={cn(
      'inline-flex shrink-0 select-none items-center justify-center rounded-lg bg-brand font-mono font-medium leading-none text-white',
      size === 'sm' ? 'size-7 text-caption' : 'size-9 text-lead',
      className
    )}
  >
    &#8721;
  </span>
);

const Brand: React.FC<BrandProps> = ({ className, markOnly = false, size = 'md' }) => (
  <span className={cn('inline-flex items-center gap-2.5', className)}>
    <BrandMark size={size} />
    {!markOnly && (
      <span
        className={cn(
          'font-display font-semibold tracking-[-0.02em] text-ink',
          size === 'sm' ? 'text-body' : 'text-lead'
        )}
      >
        Smart NVO
      </span>
    )}
  </span>
);

export default Brand;
