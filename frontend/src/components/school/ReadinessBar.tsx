import { useState } from 'react';

import type { ReadinessBand } from '../../services/schools';

/**
 * How ready a school's cohort is for НВО: parts of a whole, so one stacked
 * bar. Colours are the validated `--ready-*` tokens (a diverging scale
 * broken at the pass line), but colour is never the only way in — the
 * legend underneath names every band with its count and share, and doubles
 * as the table view.
 */
const FILL: Record<ReadinessBand['key'], string> = {
  excellent: 'bg-ready-excellent',
  good: 'bg-ready-good',
  borderline: 'bg-ready-borderline',
  at_risk: 'bg-ready-at-risk',
};

const share = (count: number, total: number) => (total ? Math.round((100 * count) / total) : 0);

const ReadinessBar: React.FC<{ bands: ReadinessBand[] }> = ({ bands }) => {
  const [hovered, setHovered] = useState<ReadinessBand['key'] | null>(null);
  const total = bands.reduce((sum, b) => sum + b.students, 0);

  if (total === 0) {
    return (
      <p className="text-caption text-ink-muted">
        Още никой от учениците в прикачените класове не е решил изпит.
      </p>
    );
  }

  const visible = bands.filter((b) => b.students > 0);
  const active = bands.find((b) => b.key === hovered);

  return (
    <figure className="space-y-4">
      <div className="relative">
        {/* 2px gaps between segments come from `gap-0.5` over the surface. */}
        <div
          className="flex h-6 w-full gap-0.5 overflow-hidden rounded"
          role="img"
          aria-label={bands
            .map((b) => `${b.label}: ${b.students} ученици (${share(b.students, total)}%)`)
            .join('; ')}
        >
          {visible.map((band, index) => (
            <div
              key={band.key}
              onMouseEnter={() => setHovered(band.key)}
              onMouseLeave={() => setHovered(null)}
              className={`h-full transition-opacity duration-150 ${FILL[band.key]} ${
                hovered && hovered !== band.key ? 'opacity-40' : ''
              } ${index === 0 ? 'rounded-l' : ''} ${index === visible.length - 1 ? 'rounded-r' : ''}`}
              style={{ width: `${(100 * band.students) / total}%`, minWidth: '0.5rem' }}
            />
          ))}
        </div>
        {active && (
          <div
            role="status"
            className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-line bg-surface px-3 py-1.5 text-caption text-ink shadow-lift-2"
          >
            <span className="font-semibold">{active.label}</span> · {active.students} ученици ·{' '}
            {share(active.students, total)}%
          </div>
        )}
      </div>

      <ul className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {bands.map((band) => (
          <li
            key={band.key}
            onMouseEnter={() => setHovered(band.key)}
            onMouseLeave={() => setHovered(null)}
            className="flex items-center gap-2.5 text-caption"
          >
            <span aria-hidden="true" className={`size-3 shrink-0 rounded-sm ${FILL[band.key]}`} />
            <span className="min-w-0 flex-1 text-ink">{band.label}</span>
            <span className="tnum font-semibold text-ink">{band.students}</span>
            <span className="tnum w-10 text-right text-ink-faint">{share(band.students, total)}%</span>
          </li>
        ))}
      </ul>
      <figcaption className="text-micro text-ink-faint">
        По последния предаден изпит на всеки ученик — къде е випускът сега, не средно за срока.
      </figcaption>
    </figure>
  );
};

export default ReadinessBar;
