/**
 * SceneRenderer.tsx
 *
 * One renderer for every NVO figure.
 *
 * The previous approach was one hand-written component per exam question —
 * RhombusCOMDiagram, PerpBisecBCDiagram, twelve of them, each with its own
 * inlined trigonometry. A thirteenth shape cost a developer a day, which made
 * the content team permanently dependent on engineering.
 *
 * Here the backend emits a *scene spec*: named points already laid out in
 * viewBox coordinates, plus the marks to draw on them. This component draws
 * any of it. A new figure is a new builder function in Python — often just a
 * different call to an existing one — and never a new component.
 *
 * The backend can lay figures out rather than solve for them because every
 * official paper since 2018 prints „Те не са начертани в мащаб и не са
 * предназначени за директно измерване на дължини и на ъгли.” — the figure has
 * to be topologically right, not metrically right.
 *
 * Colours come from `currentColor` throughout so the figure inherits the
 * page's foreground in both light and dark themes.
 */
import React from 'react';
import { renderMathText } from './MathRenderer';

// ─── spec types ──────────────────────────────────────────────────────────────

type Pt = [number, number];

export interface FigureScene {
  kind: 'figure';
  width: number;
  height: number;
  points: Record<string, Pt>;
  hidden: string[];
  dots: string[];
  segments: { from: string; to: string; dash?: boolean; weight?: number }[];
  rays: { from: string; to: string; extend?: number; arrow?: boolean; dash?: boolean }[];
  lines: { from: string; to: string; label?: string | null; dash?: boolean; pad?: number }[];
  angles: {
    at: string; from: string; to: string;
    label?: string | null; arcs?: number; fill?: boolean; r?: number; reflex?: boolean;
  }[];
  rightAngles: { at: string; from: string; to: string; size?: number; dot?: boolean }[];
  ticks: { from: string; to: string; count?: number }[];
  texts: { x: number; y: number; text: string; anchor?: TextAnchor; size?: number; italic?: boolean }[];
  labelOffsets: Record<string, [number, number]>;
  aria: string;
}

/** The `text-anchor` values SVG accepts; scene JSON carries one of these. */
export type TextAnchor = 'start' | 'middle' | 'end' | 'inherit';

export interface GridScene {
  kind: 'grid';
  xRange: [number, number];
  yRange: [number, number];
  points: { name: string; x: number; y: number }[];
  polygon: string[];
  unitLabel?: string | null;
  aria: string;
}

export interface BarsScene {
  kind: 'bars';
  categories: string[];
  series: { name?: string | null; values: number[] }[];
  yLabel?: string;
  yMax: number;
  yStep: number;
  aria: string;
}

export interface PieScene {
  kind: 'pie';
  sectors: { label: string; deg: number }[];
  title?: string | null;
  showDegrees?: boolean;
  aria: string;
}

export interface SolidScene {
  kind: 'solid';
  shape: 'cube' | 'box' | 'pyramid' | 'cone' | 'cylinder';
  labels: Record<string, string>;
  aria: string;
}

export interface SchematicScene {
  kind: 'schematic';
  shape: 'pole_cable' | 'spinner' | 'road';
  labels: Record<string, string>;
  aria: string;
}

export interface TableScene {
  kind: 'table';
  headers: string[];
  rows: string[][];
  aria: string;
}

export type Scene =
  | FigureScene | GridScene | BarsScene | PieScene | SolidScene | SchematicScene | TableScene;

// ─── shared helpers ──────────────────────────────────────────────────────────

const STROKE = 1.3;
const FONT = 'Georgia, "Times New Roman", serif';

/** Split `s_{AB}` into a base and a subscript so it can be set with a tspan. */
const splitSubscript = (raw: string): [string, string | null] => {
  const m = /^(.*?)_\{?([^}]*)\}?$/.exec(raw);
  return m ? [m[1], m[2]] : [raw, null];
};

const MathLabel: React.FC<{
  x: number; y: number; text: string; anchor?: TextAnchor; size?: number; italic?: boolean;
}> = ({ x, y, text, anchor = 'middle', size = 11.5, italic = true }) => {
  const [base, sub] = splitSubscript(text);
  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fontFamily={FONT}
      fontSize={size}
      fontStyle={italic ? 'italic' : 'normal'}
      fill="currentColor"
    >
      {base}
      {sub && <tspan fontSize={size * 0.72} dy={size * 0.24}>{sub}</tspan>}
    </text>
  );
};

const Frame: React.FC<{
  width: number; height: number; aria: string; children: React.ReactNode;
}> = ({ width, height, aria, children }) => (
  <div className="my-4 flex justify-center overflow-x-auto">
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={aria}
      style={{ maxWidth: '100%', height: 'auto', width: Math.min(width * 1.6, 460) }}
      className="text-gray-900 dark:text-gray-100"
    >
      {children}
    </svg>
  </div>
);

// ─── plane geometry ──────────────────────────────────────────────────────────

const norm = (v: Pt): Pt => {
  const n = Math.hypot(v[0], v[1]) || 1;
  return [v[0] / n, v[1] / n];
};
const sub = (a: Pt, b: Pt): Pt => [a[0] - b[0], a[1] - b[1]];
const add = (a: Pt, b: Pt): Pt => [a[0] + b[0], a[1] + b[1]];
const mul = (a: Pt, k: number): Pt => [a[0] * k, a[1] * k];

const FigureView: React.FC<{ scene: FigureScene }> = ({ scene }) => {
  const P = (name: string): Pt => scene.points[name] ?? [0, 0];
  const hidden = new Set(scene.hidden ?? []);
  const dots = new Set(scene.dots ?? []);

  /**
   * Keep a label inside the drawing box.
   *
   * The backend places labels by direction, not by position, so a mark on the
   * lowest point of a figure gets a label pushed below the viewBox and is
   * simply clipped away — which is worst exactly where it matters, since the
   * angle being asked about is usually the one at the edge.
   */
  const clamp = (x: number, y: number, pad = 13): Pt => [
    Math.min(Math.max(x, pad), scene.width - pad),
    Math.min(Math.max(y, pad), scene.height - 4),
  ];

  const arcPath = (at: string, from: string, to: string, r: number, reflex: boolean) => {
    const c = P(at);
    const a1 = Math.atan2(P(from)[1] - c[1], P(from)[0] - c[0]);
    const a2 = Math.atan2(P(to)[1] - c[1], P(to)[0] - c[0]);
    let delta = a2 - a1;
    while (delta <= -Math.PI) delta += 2 * Math.PI;
    while (delta > Math.PI) delta -= 2 * Math.PI;
    if (reflex) delta = delta > 0 ? delta - 2 * Math.PI : delta + 2 * Math.PI;
    const end = a1 + delta;
    const s: Pt = [c[0] + r * Math.cos(a1), c[1] + r * Math.sin(a1)];
    const e: Pt = [c[0] + r * Math.cos(end), c[1] + r * Math.sin(end)];
    const large = Math.abs(delta) > Math.PI ? 1 : 0;
    const sweep = delta > 0 ? 1 : 0;
    return { d: `M ${s[0]} ${s[1]} A ${r} ${r} 0 ${large} ${sweep} ${e[0]} ${e[1]}`, mid: a1 + delta / 2 };
  };

  return (
    <Frame width={scene.width} height={scene.height} aria={scene.aria}>
      {/* full lines, drawn first so everything else sits on top */}
      {(scene.lines ?? []).map((ln, i) => {
        const a = P(ln.from);
        const b = P(ln.to);
        const d = norm(sub(b, a));
        const pad = ln.pad ?? 22;
        const s = add(a, mul(d, -pad));
        const e = add(b, mul(d, pad));
        return (
          <g key={`ln${i}`}>
            <line
              x1={s[0]} y1={s[1]} x2={e[0]} y2={e[1]}
              stroke="currentColor" strokeWidth={STROKE}
              strokeDasharray={ln.dash ? '5 4' : undefined}
            />
            {ln.label && (
              <MathLabel x={e[0] + 8} y={e[1] - 5} text={ln.label} anchor="start" />
            )}
          </g>
        );
      })}

      {(scene.segments ?? []).map((sg, i) => {
        const a = P(sg.from);
        const b = P(sg.to);
        return (
          <line
            key={`sg${i}`}
            x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}
            stroke="currentColor" strokeWidth={sg.weight ?? STROKE}
            strokeLinecap="round"
            strokeDasharray={sg.dash ? '5 4' : undefined}
          />
        );
      })}

      {(scene.rays ?? []).map((ry, i) => {
        const a = P(ry.from);
        const b = P(ry.to);
        const d = norm(sub(b, a));
        const e = add(b, mul(d, ry.extend ?? 26));
        const perp: Pt = [-d[1], d[0]];
        const tip1 = add(add(e, mul(d, -7)), mul(perp, 3.2));
        const tip2 = add(add(e, mul(d, -7)), mul(perp, -3.2));
        return (
          <g key={`ry${i}`}>
            <line
              x1={a[0]} y1={a[1]} x2={e[0]} y2={e[1]}
              stroke="currentColor" strokeWidth={STROKE}
              strokeDasharray={ry.dash ? '5 4' : undefined}
            />
            {ry.arrow !== false && (
              <polygon
                points={`${e[0]},${e[1]} ${tip1[0]},${tip1[1]} ${tip2[0]},${tip2[1]}`}
                fill="currentColor"
              />
            )}
          </g>
        );
      })}

      {/* angle arcs — `arcs` repeats the stroke, which is how the papers mark
          two angles as equal without writing a value on either */}
      {(scene.angles ?? []).map((an, i) => {
        const count = an.arcs ?? 1;
        const base = an.r ?? 20;
        const c = P(an.at);
        const { mid } = arcPath(an.at, an.from, an.to, base, !!an.reflex);
        return (
          <g key={`an${i}`}>
            {Array.from({ length: count }, (_, k) => {
              const r = base - k * 4;
              const { d } = arcPath(an.at, an.from, an.to, r, !!an.reflex);
              return (
                <path
                  key={k} d={d} fill="none"
                  stroke="currentColor" strokeWidth={1.1}
                  opacity={an.fill ? 0.95 : 1}
                />
              );
            })}
            {an.fill && (
              <path
                d={`${arcPath(an.at, an.from, an.to, base, !!an.reflex).d} L ${c[0]} ${c[1]} Z`}
                fill="currentColor" opacity={0.16} stroke="none"
              />
            )}
            {an.label && (() => {
              const [lx, ly] = clamp(
                c[0] + (base + 13) * Math.cos(mid),
                c[1] + (base + 13) * Math.sin(mid) + 4,
                16
              );
              return <MathLabel x={lx} y={ly} text={an.label} italic={false} size={10.5} />;
            })()}
          </g>
        );
      })}

      {(scene.rightAngles ?? []).map((ra, i) => {
        const c = P(ra.at);
        const u = norm(sub(P(ra.from), c));
        const v = norm(sub(P(ra.to), c));
        const s = ra.size ?? 9;
        const p1 = add(c, mul(u, s));
        const p2 = add(add(c, mul(u, s)), mul(v, s));
        const p3 = add(c, mul(v, s));
        const dotAt = add(c, mul(norm(add(u, v)), s * 0.55));
        return (
          <g key={`ra${i}`}>
            <polyline
              points={`${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`}
              fill="none" stroke="currentColor" strokeWidth={1}
            />
            {ra.dot !== false && <circle cx={dotAt[0]} cy={dotAt[1]} r={1.3} fill="currentColor" />}
          </g>
        );
      })}

      {/* equal-length tick marks across the middle of a segment */}
      {(scene.ticks ?? []).map((tk, i) => {
        const a = P(tk.from);
        const b = P(tk.to);
        const mid = mul(add(a, b), 0.5);
        const d = norm(sub(b, a));
        const perp: Pt = [-d[1], d[0]];
        const n = tk.count ?? 1;
        return (
          <g key={`tk${i}`}>
            {Array.from({ length: n }, (_, k) => {
              const off = (k - (n - 1) / 2) * 3.6;
              const centre = add(mid, mul(d, off));
              const s = add(centre, mul(perp, 4.2));
              const e = add(centre, mul(perp, -4.2));
              return (
                <line
                  key={k} x1={s[0]} y1={s[1]} x2={e[0]} y2={e[1]}
                  stroke="currentColor" strokeWidth={1.1}
                />
              );
            })}
          </g>
        );
      })}

      {Object.entries(scene.points).map(([name, p]) =>
        dots.has(name) ? <circle key={`dot${name}`} cx={p[0]} cy={p[1]} r={2.3} fill="currentColor" /> : null
      )}

      {Object.entries(scene.points).map(([name, p]) => {
        if (hidden.has(name)) return null;
        const [dx, dy] = scene.labelOffsets?.[name] ?? [0, -8];
        const [lx, ly] = clamp(p[0] + dx, p[1] + dy);
        return <MathLabel key={`lb${name}`} x={lx} y={ly} text={name} />;
      })}

      {(scene.texts ?? []).map((t, i) => {
        const [lx, ly] = clamp(t.x, t.y);
        return (
          <MathLabel
            key={`tx${i}`} x={lx} y={ly} text={t.text}
            anchor={t.anchor} size={t.size} italic={t.italic}
          />
        );
      })}
    </Frame>
  );
};

// ─── coordinate grid ─────────────────────────────────────────────────────────

const GridView: React.FC<{ scene: GridScene }> = ({ scene }) => {
  const [x0, x1] = scene.xRange;
  const [y0, y1] = scene.yRange;
  const cell = 24;
  const pad = 22;
  const width = (x1 - x0) * cell + pad * 2;
  const height = (y1 - y0) * cell + pad * 2;
  const sx = (x: number) => pad + (x - x0) * cell;
  const sy = (y: number) => height - pad - (y - y0) * cell;

  return (
    <Frame width={width} height={height} aria={scene.aria}>
      <g stroke="currentColor" strokeWidth={0.6} opacity={0.3}>
        {Array.from({ length: x1 - x0 + 1 }, (_, i) => (
          <line key={`v${i}`} x1={sx(x0 + i)} y1={sy(y0)} x2={sx(x0 + i)} y2={sy(y1)} />
        ))}
        {Array.from({ length: y1 - y0 + 1 }, (_, i) => (
          <line key={`h${i}`} x1={sx(x0)} y1={sy(y0 + i)} x2={sx(x1)} y2={sy(y0 + i)} />
        ))}
      </g>

      <g stroke="currentColor" strokeWidth={1.3} fill="none">
        <line x1={sx(x0)} y1={sy(0)} x2={sx(x1) + 10} y2={sy(0)} />
        <line x1={sx(0)} y1={sy(y0)} x2={sx(0)} y2={sy(y1) - 10} />
        <polyline points={`${sx(x1) + 4},${sy(0) - 4} ${sx(x1) + 11},${sy(0)} ${sx(x1) + 4},${sy(0) + 4}`} />
        <polyline points={`${sx(0) - 4},${sy(y1) - 4} ${sx(0)},${sy(y1) - 11} ${sx(0) + 4},${sy(y1) - 4}`} />
      </g>

      <MathLabel x={sx(x1) + 6} y={sy(0) + 16} text="x" size={11} />
      <MathLabel x={sx(0) - 12} y={sy(y1) - 6} text="y" size={11} />
      <MathLabel x={sx(0) - 10} y={sy(0) + 14} text="O" size={11} />

      {scene.polygon?.length > 1 && (
        <polygon
          points={scene.polygon
            .map((n) => scene.points.find((p) => p.name === n))
            .filter(Boolean)
            .map((p) => `${sx(p!.x)},${sy(p!.y)}`)
            .join(' ')}
          fill="none" stroke="currentColor" strokeWidth={1.3}
        />
      )}

      {scene.points.map((p) => (
        <g key={p.name}>
          <circle cx={sx(p.x)} cy={sy(p.y)} r={2.6} fill="currentColor" />
          <MathLabel x={sx(p.x) - 10} y={sy(p.y) - 7} text={p.name} />
        </g>
      ))}

      {scene.unitLabel && (
        <g>
          <line
            x1={sx(x1) - cell} y1={pad - 8} x2={sx(x1)} y2={pad - 8}
            stroke="currentColor" strokeWidth={1}
          />
          <MathLabel
            x={sx(x1) - cell / 2} y={pad - 12} text={scene.unitLabel}
            italic={false} size={8.5}
          />
        </g>
      )}
    </Frame>
  );
};

// ─── bar chart ───────────────────────────────────────────────────────────────

const BarsView: React.FC<{ scene: BarsScene }> = ({ scene }) => {
  const width = 320;
  const height = 190;
  const left = 44;
  const bottom = 148;
  const top = 18;
  const plotW = width - left - 14;
  const groups = scene.categories.length;
  const seriesCount = scene.series.length;
  const slot = plotW / groups;
  const barW = Math.min(26, (slot * 0.62) / seriesCount);
  const scaleY = (v: number) => bottom - (v / scene.yMax) * (bottom - top);
  const ticks: number[] = [];
  for (let v = 0; v <= scene.yMax + 1e-9; v += scene.yStep) ticks.push(v);

  return (
    <Frame width={width} height={height} aria={scene.aria}>
      <g stroke="currentColor" strokeWidth={0.7} opacity={0.4}>
        {ticks.map((v) => (
          <line key={v} x1={left} y1={scaleY(v)} x2={width - 12} y2={scaleY(v)} />
        ))}
      </g>
      <g fontFamily="system-ui, sans-serif" fontSize={8.5} fill="currentColor" textAnchor="end">
        {ticks.map((v) => (
          <text key={v} x={left - 6} y={scaleY(v) + 3}>{v}</text>
        ))}
      </g>

      {scene.series.map((s, si) =>
        s.values.map((v, i) => {
          const groupLeft = left + i * slot + (slot - barW * seriesCount) / 2;
          const x = groupLeft + si * barW;
          return (
            <rect
              key={`${si}-${i}`}
              x={x} y={scaleY(v)} width={barW} height={bottom - scaleY(v)}
              fill="currentColor" opacity={si === 0 ? 0.62 : 0.3}
              stroke="currentColor" strokeWidth={si === 0 ? 0 : 0.8}
            />
          );
        })
      )}

      <line x1={left} y1={bottom} x2={width - 12} y2={bottom} stroke="currentColor" strokeWidth={1.3} />

      <g fontFamily="system-ui, sans-serif" fontSize={8} fill="currentColor" textAnchor="middle">
        {scene.categories.map((c, i) => (
          <text key={c} x={left + i * slot + slot / 2} y={bottom + 12}>{c}</text>
        ))}
      </g>

      {scene.yLabel && (
        <text
          transform={`rotate(-90 12 ${(top + bottom) / 2})`}
          x={12} y={(top + bottom) / 2}
          fontFamily="system-ui, sans-serif" fontSize={8.5} fill="currentColor"
          textAnchor="middle" fontWeight={600}
        >
          {scene.yLabel}
        </text>
      )}

      {seriesCount > 1 && (
        <g fontFamily="system-ui, sans-serif" fontSize={8} fill="currentColor">
          {scene.series.map((s, si) => (
            <g key={si} transform={`translate(${left}, ${height - 8 - (seriesCount - 1 - si) * 10})`}>
              <rect width={8} height={8} y={-7} fill="currentColor" opacity={si === 0 ? 0.62 : 0.3}
                    stroke="currentColor" strokeWidth={si === 0 ? 0 : 0.8} />
              <text x={12}>{s.name}</text>
            </g>
          ))}
        </g>
      )}
    </Frame>
  );
};

// ─── pie chart ───────────────────────────────────────────────────────────────

/** Cumulative start/end angle per sector, measured from twelve o'clock. */
const sectorBounds = (sectors: { deg: number }[]): { from: number; to: number }[] => {
  let cursor = -90;
  return sectors.map((s) => {
    const from = cursor;
    cursor += s.deg;
    return { from, to: cursor };
  });
};

const PieView: React.FC<{ scene: PieScene }> = ({ scene }) => {
  // Wide enough for the sector names to sit outside the circle without being
  // clipped — at 210 square the longest Bulgarian labels ("танцови",
  // "художествена") ran off the edge.
  const width = 300;
  const height = 215;
  const cx = 150;
  const cy = 112;
  const r = 62;

  // Sector bounds are derived up front rather than accumulated inside the map —
  // mutating a closure variable while rendering is the classic way to get a
  // pie chart that redraws differently on a re-render.
  const bounds = sectorBounds(scene.sectors);

  const arc = (from: number, to: number) => {
    const a = (from * Math.PI) / 180;
    const b = (to * Math.PI) / 180;
    const large = to - from > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${cx + r * Math.cos(a)} ${cy + r * Math.sin(a)} ` +
      `A ${r} ${r} 0 ${large} 1 ${cx + r * Math.cos(b)} ${cy + r * Math.sin(b)} Z`;
  };

  return (
    <Frame width={width} height={height} aria={scene.aria}>
      {scene.title && (
        <text
          x={cx} y={16} textAnchor="middle"
          fontFamily="system-ui, sans-serif" fontSize={10} fontWeight={700} fill="currentColor"
        >
          {scene.title}
        </text>
      )}
      {scene.sectors.map((s, i) => {
        const { from, to } = bounds[i];
        const midAngle = ((from + to) / 2 * Math.PI) / 180;
        return (
          <g key={s.label}>
            <path
              d={arc(from, to)}
              fill="currentColor" fillOpacity={0.08 + (i % 4) * 0.11}
              stroke="currentColor" strokeWidth={1.1}
            />
            {scene.showDegrees !== false && (
              <text
                x={cx + r * 0.58 * Math.cos(midAngle)}
                y={cy + r * 0.58 * Math.sin(midAngle) + 3}
                textAnchor="middle"
                fontFamily="system-ui, sans-serif" fontSize={9} fontWeight={600} fill="currentColor"
              >
                {s.deg}°
              </text>
            )}
            <text
              x={Math.min(Math.max(cx + (r + 12) * Math.cos(midAngle), 4), width - 4)}
              y={Math.min(Math.max(cy + (r + 14) * Math.sin(midAngle) + 3, 12), height - 4)}
              textAnchor={Math.cos(midAngle) > 0.25 ? 'start' : Math.cos(midAngle) < -0.25 ? 'end' : 'middle'}
              fontFamily="system-ui, sans-serif" fontSize={8.5} fill="currentColor"
            >
              {s.label}
            </text>
          </g>
        );
      })}
    </Frame>
  );
};

// ─── 3D solids ───────────────────────────────────────────────────────────────
// These carry no varying mathematical structure — only the dimension strings
// change between papers — so a fixed drawing per shape is enough, and is what
// the official papers do too.

const SolidView: React.FC<{ scene: SolidScene }> = ({ scene }) => {
  const L = (k: string) => scene.labels[k] ?? '';
  const body = () => {
    switch (scene.shape) {
      case 'cube':
      case 'box':
        return (
          <>
            <g fill="none" stroke="currentColor" strokeWidth={STROKE} strokeLinejoin="round">
              <polyline points="46,52 46,126 136,126 136,52 46,52" />
              <polyline points="46,52 82,26 172,26 136,52" />
              <polyline points="136,126 172,100 172,26" />
            </g>
            <g fill="none" stroke="currentColor" strokeWidth={1} strokeDasharray="4 3.5" opacity={0.75}>
              <polyline points="46,126 82,100 82,26" />
              <line x1={82} y1={100} x2={172} y2={100} />
            </g>
            <g fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
              <text x={68} y={142}>{L('w')}</text>
              <text x={145} y={122}>{L('d')}</text>
              <text x={180} y={70}>{L('h')}</text>
            </g>
          </>
        );
      case 'pyramid':
        return (
          <>
            <g fill="none" stroke="currentColor" strokeWidth={STROKE} strokeLinejoin="round">
              <polygon points="40,124 108,140 176,124 150,108 66,108" />
              <polyline points="40,124 108,26 176,124" />
              <line x1={66} y1={108} x2={108} y2={26} />
              <line x1={150} y1={108} x2={108} y2={26} />
            </g>
            <line x1={108} y1={26} x2={108} y2={128} stroke="currentColor" strokeWidth={1} strokeDasharray="4 3" opacity={0.7} />
            <g fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
              <text x={182} y={124}>{L('a')}</text>
              <text x={114} y={78}>{L('h')}</text>
            </g>
          </>
        );
      case 'cone':
        return (
          <>
            <g fill="none" stroke="currentColor" strokeWidth={STROKE}>
              <ellipse cx={108} cy={124} rx={58} ry={16} />
              <line x1={50} y1={124} x2={108} y2={26} />
              <line x1={166} y1={124} x2={108} y2={26} />
            </g>
            <line x1={108} y1={26} x2={108} y2={124} stroke="currentColor" strokeWidth={1} strokeDasharray="4 3" opacity={0.7} />
            <g fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
              <text x={140} y={72}>{L('l')}</text>
              <text x={114} y={80}>{L('h')}</text>
              <text x={128} y={140}>{L('r')}</text>
            </g>
          </>
        );
      case 'cylinder':
      default:
        return (
          <>
            <g fill="none" stroke="currentColor" strokeWidth={STROKE}>
              <ellipse cx={108} cy={40} rx={52} ry={14} />
              <line x1={56} y1={40} x2={56} y2={124} />
              <line x1={160} y1={40} x2={160} y2={124} />
              <path d="M 56 124 A 52 14 0 0 0 160 124" />
            </g>
            <path d="M 56 124 A 52 14 0 0 1 160 124" fill="none" stroke="currentColor"
                  strokeWidth={1} strokeDasharray="4 3" opacity={0.7} />
            <g fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
              <text x={168} y={86}>{L('h')}</text>
              <text x={120} y={36}>{L('r')}</text>
            </g>
          </>
        );
    }
  };

  return <Frame width={216} height={156} aria={scene.aria}>{body()}</Frame>;
};

// ─── real-world schematics ───────────────────────────────────────────────────

const SchematicView: React.FC<{ scene: SchematicScene }> = ({ scene }) => {
  const L = (k: string) => scene.labels[k] ?? '';

  if (scene.shape === 'spinner') {
    const words = (scene.labels.sectors ?? '').split(',').filter(Boolean);
    const n = words.length || 8;
    const r = 66;
    const cx = 92;
    const cy = 92;
    return (
      <Frame width={184} height={184} aria={scene.aria}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="currentColor" strokeWidth={STROKE} />
        {Array.from({ length: n }, (_, i) => {
          const a = ((i * 360) / n - 90) * (Math.PI / 180);
          const mid = (((i + 0.5) * 360) / n - 90) * (Math.PI / 180);
          return (
            <g key={i}>
              <line
                x1={cx} y1={cy}
                x2={cx + r * Math.cos(a)} y2={cy + r * Math.sin(a)}
                stroke="currentColor" strokeWidth={1}
              />
              <text
                x={cx + r * 0.64 * Math.cos(mid)}
                y={cy + r * 0.64 * Math.sin(mid) + 3}
                textAnchor="middle"
                fontFamily="system-ui, sans-serif" fontSize={7.5} fill="currentColor"
              >
                {words[i] ?? ''}
              </text>
            </g>
          );
        })}
        <polygon points={`${cx},${cy - r - 4} ${cx - 6},${cy - r - 18} ${cx + 6},${cy - r - 18}`} fill="currentColor" />
      </Frame>
    );
  }

  if (scene.shape === 'road') {
    return (
      <Frame width={280} height={90} aria={scene.aria}>
        <line x1={24} y1={58} x2={256} y2={58} stroke="currentColor" strokeWidth={STROKE} />
        {[24, 140, 256].map((x, i) => (
          <g key={x}>
            <circle cx={x} cy={58} r={2.6} fill="currentColor" />
            <MathLabel x={x} y={76} text={['A', 'B', 'C'][i]} />
          </g>
        ))}
        <text x={82} y={48} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
          {L('left')}
        </text>
        <text x={198} y={48} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={9.5} fill="currentColor">
          {L('right')}
        </text>
      </Frame>
    );
  }

  // pole_cable
  return (
    <Frame width={240} height={150} aria={scene.aria}>
      <line x1={36} y1={120} x2={212} y2={120} stroke="currentColor" strokeWidth={STROKE} />
      <rect x={168} y={38} width={5.5} height={82} fill="currentColor" opacity={0.72} />
      <line x1={58} y1={120} x2={168} y2={38} stroke="currentColor" strokeWidth={1.6} strokeDasharray="9 5" />
      <polyline points="156,120 156,108 168,108" fill="none" stroke="currentColor" strokeWidth={1} opacity={0.7} />
      <g fontFamily="system-ui, sans-serif" fontSize={11} fill="currentColor">
        <text x={82} y={74}>{L('cable')}</text>
        <text x={180} y={84}>{L('pole')}</text>
      </g>
    </Frame>
  );
};

// ─── data table ──────────────────────────────────────────────────────────────

const TableView: React.FC<{ scene: TableScene }> = ({ scene }) => (
  <div className="my-4 overflow-x-auto" role="img" aria-label={scene.aria}>
    <table className="mx-auto border-collapse text-sm">
      <thead>
        <tr>
          {scene.headers.map((h) => (
            <th
              key={h}
              className="border border-gray-400 dark:border-gray-500 px-3 py-1.5 font-semibold
                         text-gray-900 dark:text-gray-100 bg-gray-50 dark:bg-gray-800"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {scene.rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td
                key={j}
                className="border border-gray-400 dark:border-gray-500 px-3 py-2 text-center
                           text-gray-800 dark:text-gray-200"
              >
                {/* Table cells are real DOM, not SVG, so they take KaTeX —
                    the 2025 Q19 table prints n/2 and n/4 as set fractions. */}
                {renderMathText(cell)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

// ─── entry point ─────────────────────────────────────────────────────────────

const SceneRenderer: React.FC<{ scene: Scene | null | undefined }> = ({ scene }) => {
  if (!scene || typeof scene !== 'object' || !('kind' in scene)) return null;
  switch (scene.kind) {
    case 'figure': return <FigureView scene={scene} />;
    case 'grid': return <GridView scene={scene} />;
    case 'bars': return <BarsView scene={scene} />;
    case 'pie': return <PieView scene={scene} />;
    case 'solid': return <SolidView scene={scene} />;
    case 'schematic': return <SchematicView scene={scene} />;
    case 'table': return <TableView scene={scene} />;
    default: return null;
  }
};

export default SceneRenderer;
