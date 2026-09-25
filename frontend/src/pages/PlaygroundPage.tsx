import React, { useState, useEffect, useRef } from 'react';
import { generateChannelId, isStrongChannelId } from '../utils/channelId';
import { renderMathText } from '../components/MathRenderer';
import { sendChatMessage } from '../services/ai';
import { getLatestMobileUploads, setTaskContext, watchMobileChannel, clearChannelHistory, type TaskGradeResult } from '../services/mobileCapture';
import AppNavbar from '../components/AppNavbar';
import { ParallelogramABCDDiagram, type ParallelogramABCDConfig } from '../components/NvoDiagrams';


const TASK_UPLOAD_CHANNEL_KEY = 'playground_task_upload_channel_v1';

const getOrCreateTaskUploadChannelId = (): string => {
  const cached = localStorage.getItem(TASK_UPLOAD_CHANNEL_KEY)?.trim();
  if (cached && isStrongChannelId(cached)) return cached;
  const created = generateChannelId();
  localStorage.setItem(TASK_UPLOAD_CHANNEL_KEY, created);
  return created;
};

const isLocalHostName = (host: string): boolean => host === 'localhost' || host === '127.0.0.1';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const EXAMPLE_SNIPPETS = [
  { label: 'Дроб', text: 'Площта е $\\frac{a^2\\sqrt{3}}{4}$ кв. см.' },
  { label: 'Уравнение', text: '$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$' },
  { label: 'Степен', text: 'Обемът е $V = \\frac{4}{3}\\pi r^3$.' },
  { label: 'Сума', text: '$\\sum_{k=1}^{n} k = \\frac{n(n+1)}{2}$' },
];

// Half-integer coords, never 0, range [-3, 3]
const COORD_POOL = [-4, -3, -2, -1, 1, 2, 3, 4];
function randomCoord(): number {
  return COORD_POOL[Math.floor(Math.random() * COORD_POOL.length)];
}

type Point = [number, number];

// ── Pie chart generation ──────────────────────────────────────────────────
const PIE_COLORS = [
  '#e11d48', // rose
  '#2563eb', // blue
  '#16a34a', // green
  '#d97706', // amber
  '#7c3aed', // violet
  '#0891b2', // cyan
];

type PieSlice = { label: string; degrees: number; color: string; isX: boolean };

function generatePieSlices(): PieSlice[] {
  const n = 4 + Math.floor(Math.random() * 3); // 4, 5, or 6
  const knownCount = n - 2; // minus the 90° slice and the x slice
  const knownValues: number[] = [];
  let remaining = 270; // 360 - 90
  for (let i = 0; i < knownCount; i++) {
    const left = knownCount - i;
    // ensure each remaining slot (including x) gets at least 30°
    const maxThis = Math.min(remaining - left * 30 - 30, 100);
    const minThis = 30;
    if (maxThis < minThis) { knownValues.push(minThis); remaining -= minThis; continue; }
    const steps = Math.floor((maxThis - minThis) / 5);
    let val = minThis + Math.floor(Math.random() * (steps + 1)) * 5;
    // only the dedicated 90° slice may be exactly 90
    if (val === 90) val = 85;
    knownValues.push(val);
    remaining -= val;
  }
  let xVal = remaining;
  // prevent x from also landing on exactly 90
  if (xVal === 90 && knownValues.length > 0) {
    const idx = knownValues.length - 1;
    if (knownValues[idx] > 30) { knownValues[idx] -= 5; xVal = 95; }
    else { knownValues[idx] += 5; xVal = 85; }
  }

  // Build slices, shuffle so x and 90 aren't always first/last
  const raw: Omit<PieSlice, 'color'>[] = [
    { label: '90°', degrees: 90, isX: false },
    ...knownValues.map(v => ({ label: `${v}°`, degrees: v, isX: false })),
    { label: 'x', degrees: xVal, isX: true },
  ];
  // Fisher-Yates shuffle
  for (let i = raw.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [raw[i], raw[j]] = [raw[j], raw[i]];
  }
  return raw.map((s, i) => ({ ...s, color: PIE_COLORS[i % PIE_COLORS.length] }));
}

function polarXY(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg - 90) * (Math.PI / 180);
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function slicePath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarXY(cx, cy, r, startDeg);
  const e = polarXY(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M${cx},${cy} L${s.x},${s.y} A${r},${r} 0 ${large},1 ${e.x},${e.y} Z`;
}

// Right-angle arc marker:
//   - arc at arcR from centre spanning the two sides of the slice
//   - dot at the intersection of perpendiculars from the midpoints of those two sides
//     (the geometric "corner" of the right-angle marker, sitting inside the arc)
function RightAngleSymbol({ cx, cy, startDeg, endDeg }: {
  cx: number; cy: number; startDeg: number; endDeg: number;
}) {
  const arcR = 26;
  const s = polarXY(cx, cy, arcR, startDeg);
  const e = polarXY(cx, cy, arcR, endDeg);

  // α is the SVG angle (rad) of the start side
  const α = (startDeg - 90) * (Math.PI / 180);
  // For a 90° sector β = α + π/2. The perpendicular-intersection formula gives:
  //   dot = centre + (arcR/2) * (cos α − sin α, sin α + cos α)
  // which places the dot at arcR/√2 from centre — nicely inside the arc.
  const midR = arcR / 2;
  const dot = {
    x: cx + midR * (Math.cos(α) - Math.sin(α)),
    y: cy + midR * (Math.sin(α) + Math.cos(α)),
  };

  const arcPath = `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${arcR} ${arcR} 0 0 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
  return (
    <g>
      <path d={arcPath} fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" />
      <circle cx={dot.x} cy={dot.y} r={2.2} fill="white" />
    </g>
  );
}

const PieChartSection: React.FC<{ slices: PieSlice[]; demo?: boolean }> = ({ slices, demo = false }) => {
  const cx = 140; const cy = 140; const r = 120;
  const paths = slices.reduce<Array<PieSlice & { start: number; end: number }>>((acc, s) => {
    const start = acc.length > 0 ? acc[acc.length - 1].end : 0;
    acc.push({ ...s, start, end: start + s.degrees });
    return acc;
  }, []);

  const LABEL_R = 75;
  // Legend entries: skip the 90° slice (it's conveyed by the symbol in the diagram)
  const legendPaths = paths.filter(p => !(!p.isX && p.label === '90°'));
  // Re-number legend entries to match what's shown inside the slice
  const legendIndexMap = new Map(paths.map((p, i) => [p, i + 1]));

  return (
    <div className="flex flex-col sm:flex-row items-start gap-6 p-6">
      {/* SVG pie */}
      <svg width={280} height={280} viewBox="0 0 280 280" className="shrink-0">
        {paths.map((p, i) => (
          <path key={i} d={slicePath(cx, cy, r, p.start, p.end)} fill={p.color} stroke="white" strokeWidth={2} />
        ))}
        {/* right-angle symbol on the 90° slice */}
        {paths.filter(p => !p.isX && p.label === '90°').map((p, i) => (
          <RightAngleSymbol key={`ra-${i}`} cx={cx} cy={cy} startDeg={p.start} endDeg={p.end} />
        ))}
        {/* index numbers inside large-enough non-90° slices */}
        {paths.map((p, i) => {
          if (p.label === '90°' && !p.isX) return null; // no number on 90° slice
          if (p.degrees < 25) return null;
          const mid = p.start + p.degrees / 2;
          const pos = polarXY(cx, cy, LABEL_R, mid);
          return (
            <text key={`lbl-${i}`} x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="central"
              fontSize={13} fontWeight="bold" fill="white">
              {i + 1}
            </text>
          );
        })}
      </svg>

      {/* Legend – 90° slice intentionally omitted */}
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Легенда</p>
        {legendPaths.map((p) => {
          const num = legendIndexMap.get(p)!;
          return (
            <div key={num} className="flex items-center gap-2 text-sm">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-white text-xs font-bold shrink-0" style={{ background: p.color }}>
                {num}
              </span>
              <span className={p.isX ? 'font-black text-gray-900 text-base' : 'text-gray-700'}>
                {demo && !p.isX ? <span className="inline-block bg-amber-100 text-amber-700 rounded px-1 font-mono text-xs font-bold">?°</span> : p.label}
              </span>
              {p.isX && !demo && (
                <span className="text-xs text-gray-400">
                  = {p.degrees}° (неизвестно)
                </span>
              )}
            </div>
          );
        })}
        <p className="mt-3 text-xs text-gray-400">Сбор: {slices.reduce((a, s) => a + s.degrees, 0)}°</p>
      </div>
    </div>
  );
};

// ── Parallel lines with two transversals ─────────────────────────────────────
// Flavors let each angle be the acute OR supplementary pocket for variety.
// All computed values are whole numbers (even angle pool).
type ParallelLinesConfig = {
  angle1: number;
  angle2: number;
  alphaFlavor: 'acute' | 'obtuse';                      // α at P1
  betaFlavor:  'upper' | 'right' | 'lower' | 'left';   // β at M – all 4 pockets
  gammaFlavor: 'acute' | 'obtuse';                      // γ at P4
};

function generateParallelLinesConfig(): ParallelLinesConfig {
  const opts = [40, 44, 48, 52, 56, 60];
  const angle1 = opts[Math.floor(Math.random() * opts.length)];
  let angle2: number;
  do { angle2 = opts[Math.floor(Math.random() * opts.length)]; } while (angle2 === angle1);
  const betaOpts: ParallelLinesConfig['betaFlavor'][] = ['upper', 'right', 'lower', 'left'];
  return {
    angle1, angle2,
    alphaFlavor: Math.random() < 0.5 ? 'acute' : 'obtuse',
    betaFlavor:  betaOpts[Math.floor(Math.random() * betaOpts.length)],
    gammaFlavor: Math.random() < 0.5 ? 'acute' : 'obtuse',
  };
}

const ParallelLinesDiagram: React.FC<{ config: ParallelLinesConfig }> = ({ config }) => {
  const { angle1, angle2, alphaFlavor, betaFlavor, gammaFlavor } = config;
  const W = 420, H = 330;
  const xa = 100, xb = 320;
  const mx = (xa + xb) / 2, my = H / 2;

  const a1r = (angle1 * Math.PI) / 180;
  const a2r = (angle2 * Math.PI) / 180;
  const cot1 = Math.cos(a1r) / Math.sin(a1r);
  const cot2 = Math.cos(a2r) / Math.sin(a2r);

  const yAt = (slope: number, x: number) => my + slope * (x - mx);

  const y1a = yAt(cot1, xa);
  const y2a = yAt(-cot2, xa);
  const y1b = yAt(cot1, xb);
  const y2b = yAt(-cot2, xb);

  const ext = 24;
  const AR = 18;
  const LDIST = AR + 16;

  const arc = (cx: number, cy: number, r: number, sDeg: number, eDeg: number) => {
    const toRad = (d: number) => d * Math.PI / 180;
    const sx = cx + r * Math.cos(toRad(sDeg));
    const sy = cy + r * Math.sin(toRad(sDeg));
    const ex = cx + r * Math.cos(toRad(eDeg));
    const ey = cy + r * Math.sin(toRad(eDeg));
    const large = ((eDeg - sDeg) + 360) % 360 > 180 ? 1 : 0;
    return `M ${sx.toFixed(1)} ${sy.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${ex.toFixed(1)} ${ey.toFixed(1)}`;
  };

  const labelPos = (cx: number, cy: number, sDeg: number, eDeg: number, dist: number) => {
    const delta = ((eDeg - sDeg) + 360) % 360;
    const mid = (sDeg + delta / 2) * Math.PI / 180;
    return { x: +(cx + dist * Math.cos(mid)).toFixed(1), y: +(cy + dist * Math.sin(mid)).toFixed(1) };
  };

  // Transversal arm directions in SVG degrees (clockwise from right)
  const svgT1right = 90 - angle1;        // T1 toward lower-right
  const svgT1left  = 270 - angle1;       // T1 toward upper-left
  const svgT2right = 270 + angle2;       // T2 toward upper-right
  const svgT2left  = 90 + angle2;        // T2 toward lower-left

  // α at P1
  const arcAlphaS = alphaFlavor === 'acute' ? svgT1right : 270;
  const arcAlphaE = alphaFlavor === 'acute' ? 90         : svgT1right;
  // β at M – all 4 pockets:
  //   upper : T1-upper-left → T2-upper-right  (value = angle1+angle2)
  //   right : T2-upper-right → T1-lower-right (value = 180-angle1-angle2)
  //   lower : T1-lower-right → T2-lower-left  (value = angle1+angle2)
  //   left  : T2-lower-left  → T1-upper-left  (value = 180-angle1-angle2)
  const arcBetaS = betaFlavor === 'upper' ? svgT1left
                 : betaFlavor === 'right' ? svgT2right
                 : betaFlavor === 'lower' ? svgT1right
                 :                          svgT2left;   // 'left'
  const arcBetaE = betaFlavor === 'upper' ? svgT2right
                 : betaFlavor === 'right' ? svgT1right
                 : betaFlavor === 'lower' ? svgT2left
                 :                          svgT1left;   // 'left'
  // γ at P4
  const arcGammaS = gammaFlavor === 'acute' ? 90      : svgT2left;
  const arcGammaE = gammaFlavor === 'acute' ? svgT2left : 270;

  const posA = labelPos(xa, y1a, arcAlphaS, arcAlphaE, LDIST);
  const posB = labelPos(mx, my,  arcBetaS,  arcBetaE,  LDIST);
  const posG = labelPos(xb, y2b, arcGammaS, arcGammaE, LDIST);

  const R = 90;
  const rot   = `rotate(${R}, ${mx}, ${my})`;
  const unrot = (x: number, y: number) => `rotate(${-R}, ${x}, ${y})`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', margin: '0 auto', overflow: 'visible' }}>
      <g transform={rot}>
        {/* Parallel line a (no label) */}
        <line x1={xa} y1={8} x2={xa} y2={H - 8} stroke="#1e3a5f" strokeWidth={2.2} />
        {/* Parallel line b (no label) */}
        <line x1={xb} y1={8} x2={xb} y2={H - 8} stroke="#1e3a5f" strokeWidth={2.2} />
        {/* Double tick marks ∥ */}
        <line x1={xa - 7} y1={22} x2={xa + 7} y2={22} stroke="#1e3a5f" strokeWidth={1.5} />
        <line x1={xa - 7} y1={30} x2={xa + 7} y2={30} stroke="#1e3a5f" strokeWidth={1.5} />
        <line x1={xb - 7} y1={22} x2={xb + 7} y2={22} stroke="#1e3a5f" strokeWidth={1.5} />
        <line x1={xb - 7} y1={30} x2={xb + 7} y2={30} stroke="#1e3a5f" strokeWidth={1.5} />
        {/* Transversal T1 (blue) */}
        <line x1={xa - ext} y1={yAt(cot1, xa - ext)} x2={xb + ext} y2={yAt(cot1, xb + ext)} stroke="#2563eb" strokeWidth={1.8} />
        {/* Transversal T2 (red) */}
        <line x1={xa - ext} y1={yAt(-cot2, xa - ext)} x2={xb + ext} y2={yAt(-cot2, xb + ext)} stroke="#e11d48" strokeWidth={1.8} />
        {/* Intersection dots */}
        <circle cx={xa} cy={y1a} r={3.5} fill="#2563eb" />
        <circle cx={xa} cy={y2a} r={3.5} fill="#e11d48" />
        <circle cx={xb} cy={y1b} r={3.5} fill="#2563eb" />
        <circle cx={xb} cy={y2b} r={3.5} fill="#e11d48" />
        <circle cx={mx} cy={my} r={4.5} fill="#7c3aed" />
        {/* ── Arcs + Greek labels ── */}
        <path d={arc(xa, y1a, AR, arcAlphaS, arcAlphaE)} fill="none" stroke="#2563eb" strokeWidth={1.5} />
        <text x={posA.x} y={posA.y} fontSize={14} fill="#2563eb" textAnchor="middle" dominantBaseline="middle" fontStyle="italic" transform={unrot(posA.x, posA.y)}>α</text>
        <path d={arc(mx, my, AR, arcBetaS, arcBetaE)} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
        <text x={posB.x} y={posB.y} fontSize={14} fill="#7c3aed" textAnchor="middle" dominantBaseline="middle" fontStyle="italic" transform={unrot(posB.x, posB.y)}>β</text>
        <path d={arc(xb, y2b, AR, arcGammaS, arcGammaE)} fill="none" stroke="#e11d48" strokeWidth={1.5} />
        <text x={posG.x} y={posG.y} fontSize={14} fill="#e11d48" textAnchor="middle" dominantBaseline="middle" fontStyle="italic" transform={unrot(posG.x, posG.y)}>γ</text>
      </g>
    </svg>
  );
};

// ── Isosceles triangle diagram ──────────────────────────────────────────────────
type TriangleConfig = { angleC: number; bisectorSide: 'AC' | 'BC' };

function generateTriangleConfig(): TriangleConfig {
  // Only even values so that 3α/2 and α/2 are always whole numbers
  const opts = [10, 20, 30, 40];
  return {
    angleC: opts[Math.floor(Math.random() * opts.length)],
    bisectorSide: Math.random() < 0.5 ? 'AC' : 'BC',
  };
}

const IsoscelesTriangleDiagram: React.FC<{ config: TriangleConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angleC, bisectorSide } = config;

  // Angles of triangle ABF
  const angF = 2 * angleC;
  const angA = bisectorSide === 'AC' ? 90 - (3 * angleC) / 2 : 90 - angleC / 2;
  const angB = bisectorSide === 'AC' ? 90 - angleC / 2 : 90 - (3 * angleC) / 2;
  const fmtAngle = (v: number) => demo ? '?°' : `${v}°`;
  const W = 400, SH = 290;
  // cx shifted slightly left so the dashed bisector (which extends right for AC case) stays in view
  const cx = 190, yBase = 265, yTop = 45, TH = yBase - yTop;
  const halfRad = (angleC / 2) * (Math.PI / 180);
  const d = TH * Math.tan(halfRad);      // half-base
  const Lsq = TH * TH + d * d;           // leg²
  const L = Math.sqrt(Lsq);
  const denom = TH * TH - d * d;         // > 0 for angleC < 90°

  const A = { x: cx - d, y: yBase };
  const B = { x: cx + d, y: yBase };
  const C = { x: cx, y: yTop };
  const yMid = (yBase + yTop) / 2;

  // F = intersection of perp bisector of chosen side with the opposite leg
  // s = parameter on that opposite leg (s=0 at the base vertex, s=1 at C)
  const s_param = (TH * TH - 3 * d * d) / (2 * denom);
  const Fy = yBase - s_param * TH;

  let F: { x: number; y: number };
  let M: { x: number; y: number };       // midpoint of bisected leg
  let bisNorm: { x: number; y: number }; // unit direction of bisector
  let ilx1: number, ily1: number, ilx2: number, ily2: number; // inner dividing line

  if (bisectorSide === 'AC') {
    // Bisector of AC intersects BC at F
    // F lies on BC: Q(s) = (cx+d*(1-s), yBase-s*TH)
    F = { x: cx + d * (1 - s_param), y: Fy };
    M = { x: cx - d / 2, y: yMid };
    // Perp to AC direction (d, -TH) in SVG → (TH, d)/L
    bisNorm = { x: TH / L, y: d / L };
    ilx1 = A.x; ily1 = A.y; ilx2 = F.x; ily2 = F.y;
  } else {
    // Bisector of BC intersects AC at F (mirror image)
    F = { x: cx - d * (1 - s_param), y: Fy };
    M = { x: cx + d / 2, y: yMid };
    // Perp to BC direction (-d, -TH) in SVG → (-TH, d)/L
    bisNorm = { x: -TH / L, y: d / L };
    ilx1 = B.x; ily1 = B.y; ilx2 = F.x; ily2 = F.y;
  }

  // Extend dashed bisector: 55 units before M and 60 past F
  const dMF = Math.sqrt((F.x - M.x) ** 2 + (F.y - M.y) ** 2);
  const bs = { x: M.x - bisNorm.x * 55, y: M.y - bisNorm.y * 55 };
  const be = { x: M.x + bisNorm.x * (dMF + 60), y: M.y + bisNorm.y * (dMF + 60) };

  // Angle arc at C showing angleC
  const ar = 18;
  const arcS = polarXY(cx, yTop, ar, 180 - angleC / 2); // on C→B side
  const arcE = polarXY(cx, yTop, ar, 180 + angleC / 2); // on C→A side
  const arcLabel = polarXY(cx, yTop, ar + 17, 180);     // straight down, for the degree text

  // Equal-leg tick marks
  const tkLen = 6;
  const mCA = { x: cx - d / 2, y: yMid };
  const mCB = { x: cx + d / 2, y: yMid };
  const tkx = TH / L * tkLen, tky = d / L * tkLen;

  // Bisector label position (near the "back" end of the dashed line)
  const blx = bs.x + (bisectorSide === 'AC' ? -5 : 5);
  const bly = bs.y - 12;

  return (
    <svg width={W} height={SH} viewBox={`0 0 ${W} ${SH}`}>
      {/* Triangle fill */}
      <polygon
        points={`${A.x.toFixed(1)},${A.y} ${B.x.toFixed(1)},${B.y} ${C.x},${C.y}`}
        fill="#eef2ff" stroke="#1e3a5f" strokeWidth={2} strokeLinejoin="round"
      />
      {/* Inner dividing line (AF or BF) – forms triangle ABF */}
      <line x1={ilx1} y1={ily1} x2={ilx2} y2={ily2} stroke="#1e3a5f" strokeWidth={1.8} />
      {/* Perpendicular bisector dashed line */}
      <line
        x1={bs.x.toFixed(1)} y1={bs.y.toFixed(1)}
        x2={be.x.toFixed(1)} y2={be.y.toFixed(1)}
        stroke="#64748b" strokeWidth={1.5} strokeDasharray="7 4"
      />
      {/* Equal-side tick on CA */}
      <line
        x1={mCA.x - tkx} y1={mCA.y - tky}
        x2={mCA.x + tkx} y2={mCA.y + tky}
        stroke="#1e3a5f" strokeWidth={1.5}
      />
      {/* Equal-side tick on CB */}
      <line
        x1={mCB.x - tkx} y1={mCB.y + tky}
        x2={mCB.x + tkx} y2={mCB.y - tky}
        stroke="#1e3a5f" strokeWidth={1.5}
      />
      {/* Angle arc at C */}
      <path
        d={`M ${arcS.x.toFixed(2)},${arcS.y.toFixed(2)} A ${ar} ${ar} 0 0 1 ${arcE.x.toFixed(2)},${arcE.y.toFixed(2)}`}
        fill="none" stroke="#1e3a5f" strokeWidth={1.3}
      />
      <text x={arcLabel.x} y={arcLabel.y} textAnchor="middle" dominantBaseline="middle" fontSize={13} fontStyle="italic" fill="#1e3a5f">
        α
      </text>
      {/* Vertex labels */}
      <text x={C.x} y={C.y - 10} textAnchor="middle" fontSize={15} fontWeight="bold" fill="#1e3a5f">C</text>
      <text x={A.x - 13} y={A.y + 5} textAnchor="middle" fontSize={15} fontWeight="bold" fill="#1e3a5f">A</text>
      <text x={B.x + 13} y={B.y + 5} textAnchor="middle" fontSize={15} fontWeight="bold" fill="#1e3a5f">B</text>
      {/* Angle labels at A, B, F for triangle ABF */}
      <text x={A.x + 2} y={A.y - 12} textAnchor="middle" fontSize={11} fill="#7c3aed">{fmtAngle(angA)}</text>
      <text x={B.x - 2} y={B.y - 12} textAnchor="end" fontSize={11} fill="#7c3aed">{fmtAngle(angB)}</text>
      <text
        x={bisectorSide === 'AC' ? F.x - 18 : F.x + 18}
        y={F.y - 10}
        textAnchor="middle" fontSize={11} fill="#7c3aed"
      >{fmtAngle(angF)}</text>
      {/* F point */}
      <circle cx={F.x} cy={F.y} r={3.5} fill="#c026d3" />
      <text
        x={bisectorSide === 'AC' ? F.x + 14 : F.x - 14}
        y={F.y + 4}
        textAnchor="middle" fontSize={14} fontWeight="bold" fill="#c026d3"
      >F</text>
      {/* Bisector label s_AC or s_BC */}
      <text x={blx} y={bly} textAnchor="middle" fontSize={12} fill="#64748b">
        s<tspan dy="3" fontSize="9">{bisectorSide}</tspan>
      </text>
    </svg>
  );
};

function collinear(A: Point, B: Point, C: Point): boolean {
  // cross product of AB × AC; zero means collinear
  return (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0]) === 0;
}

function generateDistinctPoints(): { A: Point; B: Point; C: Point } {
  const key = (p: Point) => `${p[0]},${p[1]}`;
  let A: Point, B: Point, C: Point;
  do {
    A = [randomCoord(), randomCoord()];
    B = [randomCoord(), randomCoord()];
    C = [randomCoord(), randomCoord()];
  } while (key(A) === key(B) || key(C) === key(A) || key(C) === key(B) || collinear(A, B, C));
  return { A, B, C };
}

type SymConfig = {
  A: Point; B: Point; C: Point;
  sourceLabel: 'A' | 'B';
  axis: 'Ox' | 'Oy';
};

function generateSymConfig(): SymConfig {
  const key = (p: Point) => `${p[0]},${p[1]}`;
  while (true) {
    const axis: 'Ox' | 'Oy' = Math.random() < 0.5 ? 'Ox' : 'Oy';
    const sourceLabel: 'A' | 'B' = Math.random() < 0.5 ? 'A' : 'B';
    const A: Point = [randomCoord(), randomCoord()];
    const B: Point = [randomCoord(), randomCoord()];
    const src = sourceLabel === 'A' ? A : B;
    const C: Point = axis === 'Ox' ? [src[0], -src[1]] : [-src[0], src[1]];
    if (key(A) !== key(B) && key(C) !== key(A) && key(C) !== key(B) && !collinear(A, B, C)) {
      return { A, B, C, sourceLabel, axis };
    }
  }
}

// ── Circumcenter (perp bisectors of AB and AC) ──────────────────────
type CircumcenterConfig = { angOBA: number; angOCA: number };

function generateCircumcenterConfig(): CircumcenterConfig {
  // Even values, sum < 88 so angBAC = angOBA+angOCA stays acute
  const pairs: [number, number][] = [
    [30, 40],[30, 50],[32, 44],[34, 42],[34, 48],[36, 40],[36, 46],[38, 40],[38, 44],[40, 40],
  ];
  const [a, b] = pairs[Math.floor(Math.random() * pairs.length)];
  return { angOBA: a, angOCA: b };
}

const CircumcenterDiagram: React.FC<{ config: CircumcenterConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angOBA, angOCA } = config;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 380, H = 290;

  // Place A bottom-left, B bottom-right, build triangle from angles
  const Ax = 60, Ay = 265, Bx = 320, By = 265;
  const angBAC = angOBA + angOCA;
  const AB = Bx - Ax;
  // C via law of sines for display
  const Cx = Ax + AB * Math.cos(toRad(angBAC)) * 0.82;
  const Cy = Ay - AB * Math.sin(toRad(angBAC)) * 0.82;

  // O = circumcenter: intersection of perp bisectors
  // Use the known property: O lies at (Bx+(Ax-Bx)*cos2B, By+(Ay-By)*cos... )
  // Easier: O is equidistant from A,B,C — place it via the circumcenter formula
  const ax = Bx - Ax, ay = By - Ay;
  const bx = Cx - Ax, by = Cy - Ay;
  const D = 2 * (ax * by - ay * bx);
  const ux = (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / D;
  const uy = (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / D;
  const Ox = Ax + ux, Oy = Ay + uy;

  // Perpendicular bisectors (dashed): midpoints of AB and AC to O
  const mABx = (Ax + Bx) / 2, mABy = (Ay + By) / 2;
  const mACx = (Ax + Cx) / 2, mACy = (Ay + Cy) / 2;
  const bisExt = 170;
  const abDirX = Ox - mABx, abDirY = Oy - mABy;
  const abLen = Math.sqrt(abDirX * abDirX + abDirY * abDirY) || 1;
  const abUx = abDirX / abLen, abUy = abDirY / abLen;
  const abL1x = mABx - abUx * bisExt, abL1y = mABy - abUy * bisExt;
  const abL2x = mABx + abUx * bisExt, abL2y = mABy + abUy * bisExt;
  const acDirX = Ox - mACx, acDirY = Oy - mACy;
  const acLen = Math.sqrt(acDirX * acDirX + acDirY * acDirY) || 1;
  const acUx = acDirX / acLen, acUy = acDirY / acLen;
  const acL1x = mACx - acUx * bisExt, acL1y = mACy - acUy * bisExt;
  const acL2x = mACx + acUx * bisExt, acL2y = mACy + acUy * bisExt;

  const f = (v: number) => demo ? '?' : `${v}`;
  const AR = 20; // arc radius for angle labels

  // Angle arc helper
  const arcPath = (cx: number, cy: number, r: number, a1: number, a2: number) => {
    const tr = (d: number) => d * Math.PI / 180;
    const sx = cx + r * Math.cos(tr(a1)), sy = cy + r * Math.sin(tr(a1));
    const ex = cx + r * Math.cos(tr(a2)), ey = cy + r * Math.sin(tr(a2));
    const large = ((a2 - a1 + 360) % 360) > 180 ? 1 : 0;
    return `M ${sx.toFixed(1)} ${sy.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${ex.toFixed(1)} ${ey.toFixed(1)}`;
  };

  // Angles at B: AB goes left (180°), BO direction
  const angBO_B = Math.atan2(Oy - By, Ox - Bx) * 180 / Math.PI;
  // Angles at C: CA direction, CO direction
  const angCA_C = Math.atan2(Ay - Cy, Ax - Cx) * 180 / Math.PI;
  const angCO_C = Math.atan2(Oy - Cy, Ox - Cx) * 180 / Math.PI;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', margin: '0 auto' }}>
      {/* Triangle sides */}
      <line x1={Ax} y1={Ay} x2={Bx} y2={By} stroke="#1e3a5f" strokeWidth={2} />
      <line x1={Bx} y1={By} x2={Cx} y2={Cy} stroke="#1e3a5f" strokeWidth={2} />
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#1e3a5f" strokeWidth={2} />
      {/* OB and OA and OC lines */}
      <line x1={Ox} y1={Oy} x2={Bx} y2={By} stroke="#6366f1" strokeWidth={1.5} />
      <line x1={Ox} y1={Oy} x2={Ax} y2={Ay} stroke="#6366f1" strokeWidth={1.5} />
      <line x1={Ox} y1={Oy} x2={Cx} y2={Cy} stroke="#6366f1" strokeWidth={1.5} />
      {/* Extended perpendicular bisector of AB (dashed) */}
      <line x1={abL1x} y1={abL1y} x2={abL2x} y2={abL2y} stroke="#9ca3af" strokeWidth={1.2} strokeDasharray="5 3" />
      {/* Extended perpendicular bisector of AC (dashed) */}
      <line x1={acL1x} y1={acL1y} x2={acL2x} y2={acL2y} stroke="#9ca3af" strokeWidth={1.2} strokeDasharray="5 3" />
      {/* Angle arc at B: angOBA */}
      <path d={arcPath(Bx, By, AR, 180, angBO_B)} fill="none" stroke="#6366f1" strokeWidth={1.4} />
      <text
        x={(Bx + (AR + 14) * Math.cos(((angBO_B + 180) / 2) * Math.PI / 180)).toFixed(1)}
        y={(By + (AR + 14) * Math.sin(((angBO_B + 180) / 2) * Math.PI / 180)).toFixed(1)}
        fontSize={12} fill="#6366f1" textAnchor="middle" dominantBaseline="middle"
      >{f(angOBA)}°</text>
      {/* Angle arc at C: angOCA */}
      <path d={arcPath(Cx, Cy, AR, angCO_C, angCA_C)} fill="none" stroke="#6366f1" strokeWidth={1.4} />
      <text
        x={(Cx + (AR + 14) * Math.cos(((angCA_C + angCO_C) / 2) * Math.PI / 180)).toFixed(1)}
        y={(Cy + (AR + 14) * Math.sin(((angCA_C + angCO_C) / 2) * Math.PI / 180)).toFixed(1)}
        fontSize={12} fill="#6366f1" textAnchor="middle" dominantBaseline="middle"
      >{f(angOCA)}°</text>
      {/* Dots */}
      <circle cx={Ox} cy={Oy} r={4} fill="#6366f1" />
      <circle cx={Ax} cy={Ay} r={3} fill="#1e3a5f" />
      <circle cx={Bx} cy={By} r={3} fill="#1e3a5f" />
      <circle cx={Cx} cy={Cy} r={3} fill="#1e3a5f" />
      {/* Tick marks on dashed bisectors */}
      <line x1={mABx - 5} y1={mABy} x2={mABx + 5} y2={mABy} stroke="#9ca3af" strokeWidth={1.4} />
      <line x1={mABx} y1={mABy - 5} x2={mABx} y2={mABy + 5} stroke="#9ca3af" strokeWidth={1.4} />
      <line x1={mACx - 4} y1={mACy - 4} x2={mACx + 4} y2={mACy + 4} stroke="#9ca3af" strokeWidth={1.4} />
      <line x1={mACx + 4} y1={mACy - 4} x2={mACx - 4} y2={mACy + 4} stroke="#9ca3af" strokeWidth={1.4} />
      {/* Labels */}
      <text x={Ax - 14} y={Ay + 6}  fontSize={14} fontWeight="bold" fill="#1e3a5f">A</text>
      <text x={Bx + 8}  y={By + 6}  fontSize={14} fontWeight="bold" fill="#1e3a5f">B</text>
      <text x={Cx + 8}  y={Cy - 4}  fontSize={14} fontWeight="bold" fill="#1e3a5f">C</text>
      <text x={Ox + 8}  y={Oy - 6}  fontSize={13} fontWeight="bold" fill="#6366f1">O</text>
      {/* s_AC and s_AB labels on bisectors */}
      <text x={mACx - 22} y={mACy - 4} fontSize={11} fill="#9ca3af" fontStyle="italic">sₐᴄ</text>
      <text x={mABx + 6}  y={mABy + 14} fontSize={11} fill="#9ca3af" fontStyle="italic">sₐᴃ</text>
    </svg>
  );
};

// ── Equilateral triangle perpendicular (PM ⊥ AC) diagram ───────────────
type EqTriPerpConfig = { AP: number; MB: number };

const EQ_TRI_PERP_POOL: EqTriPerpConfig[] = [
  { AP: 3, MB: 6 },  // AB=12
  { AP: 3, MB: 8 },  // AB=14
  { AP: 4, MB: 5 },  // AB=13
  { AP: 4, MB: 7 },  // AB=15
  { AP: 5, MB: 8 },  // AB=18
  { AP: 5, MB: 5 },  // AB=15
  { AP: 3, MB: 7 },  // AB=13
  { AP: 6, MB: 6 },  // AB=18
];

function generateEqTriPerpConfig(): EqTriPerpConfig {
  return EQ_TRI_PERP_POOL[Math.floor(Math.random() * EQ_TRI_PERP_POOL.length)];
}

const EqTriPerpDiagram: React.FC<{ config: EqTriPerpConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { AP, MB } = config;
  const AB = 2 * AP + MB;  // AM = 2*AP (cos60° = AP/AM), so AB = AM + MB
  const W = 400, H = 280;
  const fv = (v: number) => demo ? '？' : String(v);
  const toRad = (d: number) => d * Math.PI / 180;

  // Triangle vertices
  const Ax = 55, Ay = 256;
  const Bx = 345, By = 256;
  const sidePx = Bx - Ax; // 290px
  const Cx = (Ax + Bx) / 2;  // 200
  const Cy = Ay - sidePx * Math.sin(toRad(60));  // ≈ 256 - 251.2 ≈ 5

  // P on AC: fraction AP/AB along AC from A
  const tP = AP / AB;
  const Px = Ax + tP * (Cx - Ax);
  const Py = Ay + tP * (Cy - Ay);

  // M on AB: fraction AM/AB = 2*AP/AB along AB from A
  const tM = (2 * AP) / AB;
  const Mx = Ax + tM * (Bx - Ax);
  const My = Ay;

  // AC unit vector
  const acLen = Math.sqrt((Cx - Ax) ** 2 + (Cy - Ay) ** 2);
  const acUx = (Cx - Ax) / acLen;
  const acUy = (Cy - Ay) / acLen;

  // Right-angle arc at P (PM ⊥ AC)
  const arcR = 12;
  const uCx = acUx, uCy = acUy;  // unit vec P → C (same as AC direction)
  const pmLen = Math.sqrt((Mx - Px) ** 2 + (My - Py) ** 2);
  const uMx = (Mx - Px) / pmLen, uMy = (My - Py) / pmLen;  // unit vec P → M
  // sweep=1 (CW in SVG): arc goes from P→C arm clockwise to P→M arm
  const arcSx = (Px + arcR * uCx).toFixed(2), arcSy = (Py + arcR * uCy).toFixed(2);
  const arcEx = (Px + arcR * uMx).toFixed(2), arcEy = (Py + arcR * uMy).toFixed(2);
  const arcDotX = Px + arcR / 2 * (uCx + uMx);
  const arcDotY = Py + arcR / 2 * (uCy + uMy);

  // Midpoints for labels
  const apMidX = (Ax + Px) / 2, apMidY = (Ay + Py) / 2;
  const pmMidX = (Px + Mx) / 2, pmMidY = (Py + My) / 2;
  const mbMidX = (Mx + Bx) / 2, mbMidY = (My + By) / 2;

  return (
    <svg viewBox={`0 -20 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle */}
      <polygon
        points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8}
      />

      {/* PM line */}
      <line x1={Px} y1={Py} x2={Mx} y2={My} stroke="#7c3aed" strokeWidth={1.8} />

      {/* Right-angle quarter-arc + dot at P (PM ⊥ AC) */}
      <path d={`M ${arcSx},${arcSy} A ${arcR},${arcR} 0 0,1 ${arcEx},${arcEy}`} fill="none" stroke="#374151" strokeWidth={1.3} strokeLinecap="round"/>
      <circle cx={arcDotX} cy={arcDotY} r={2.2} fill="#374151"/>

      {/* Vertex labels */}
      <text x={Cx} y={Cy - 6} fontSize={13} textAnchor="middle" fill="#1e40af" fontWeight="700">C</text>
      <text x={Ax - 12} y={Ay + 5} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6} y={By + 5} fontSize={13} fill="#1e40af" fontWeight="700">B</text>

      {/* P label */}
      <text x={Px - 14} y={Py + 4} fontSize={12} fill="#374151" fontWeight="600">P</text>

      {/* M label on base */}
      <text x={Mx - 4} y={My + 16} fontSize={12} fill="#374151" fontWeight="600">M</text>

      {/* AP dimension */}
      <text x={apMidX - 14} y={apMidY + 2} fontSize={11} fill="#dc2626" fontWeight="600">{fv(AP)}</text>

      {/* MB dimension */}
      <text x={mbMidX} y={mbMidY + 16} fontSize={11} fill="#dc2626" fontWeight="600" textAnchor="middle">{fv(MB)}</text>

      {/* PM label */}
      <text x={pmMidX + 8} y={pmMidY + 4} fontSize={11} fill="#7c3aed">PM</text>
    </svg>
  );
};

// ── Isosceles chain: AC = CF = BF, find ∠ACB ────────────────────────────
// Angle at A = (x + k)°, angle FBC = x°.  Solving: x = k, ∠ACB = 180 - 3k
type IsoscChainConfig = { k: number };

const ISOSC_CHAIN_POOL = [20, 25, 30, 35, 40];

function generateIsoscChainConfig(): IsoscChainConfig {
  const k = ISOSC_CHAIN_POOL[Math.floor(Math.random() * ISOSC_CHAIN_POOL.length)];
  return { k };
}

const IsoscChainDiagram: React.FC<{ config: IsoscChainConfig; demo?: boolean }> = ({ config }) => {
  const { k } = config;
  const W = 420, H = 290;
  const toRad = (d: number) => d * Math.PI / 180;

  const AB_len = 260;
  const Ax = 55, Ay = 250;
  const Bx = Ax + AB_len, By = Ay;

  // C via intersection of rays from A (angle 2k) and B (angle 180-k)
  const cosK = Math.cos(toRad(k));
  const s_BC = 2 * AB_len * cosK / (4 * cosK * cosK - 1);
  const Cx = Bx - s_BC * cosK;
  const Cy = By - s_BC * Math.sin(toRad(k));

  // F on AB: BF = BC / (2 cos k)
  const BC_dist = Math.sqrt((Cx - Bx) ** 2 + (Cy - By) ** 2);
  const BF_len = BC_dist / (2 * cosK);
  const Fx = Bx - BF_len;
  const Fy = Ay;

  // Tick mark at midpoint of segment, perpendicular
  const tickPath = (x1: number, y1: number, x2: number, y2: number, sz = 7) => {
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.sqrt(dx * dx + dy * dy);
    const nx = -dy / len * sz / 2, ny = dx / len * sz / 2;
    return `M ${mx - nx},${my - ny} L ${mx + nx},${my + ny}`;
  };

  // Angle arc at A: from AB direction (right) sweeping up to AC direction
  const arcR = 32;
  const arcAEx = Ax + arcR * Math.cos(toRad(2 * k));
  const arcAEy = Ay - arcR * Math.sin(toRad(2 * k));

  // Angle arc at B: from BA direction (left) sweeping up to BC direction
  const arcBEx = Bx + arcR * Math.cos(toRad(180 - k));
  const arcBEy = By - arcR * Math.sin(toRad(k));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle sides */}
      <line x1={Ax} y1={Ay} x2={Bx} y2={By} stroke="#1e40af" strokeWidth={1.8} />
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#1e40af" strokeWidth={1.8} />
      <line x1={Cx} y1={Cy} x2={Bx} y2={By} stroke="#1e40af" strokeWidth={1.8} />

      {/* CF line */}
      <line x1={Cx} y1={Cy} x2={Fx} y2={Fy} stroke="#374151" strokeWidth={1.5} />

      {/* Equal-length tick marks on AC, CF, BF */}
      <path d={tickPath(Ax, Ay, Cx, Cy)} stroke="#dc2626" strokeWidth={2.2} fill="none" />
      <path d={tickPath(Cx, Cy, Fx, Fy)} stroke="#dc2626" strokeWidth={2.2} fill="none" />
      <path d={tickPath(Fx, Fy, Bx, By)} stroke="#dc2626" strokeWidth={2.2} fill="none" />

      {/* Angle arc at A (angle 2k) */}
      <path
        d={`M ${Ax + arcR},${Ay} A ${arcR},${arcR} 0 0,0 ${arcAEx},${arcAEy}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5}
      />
      <text x={Ax + arcR + 5} y={Ay - 6} fontSize={12} fill="#374151">(x + {k})°</text>

      {/* Angle arc at B (angle k) */}
      <path
        d={`M ${Bx - arcR},${By} A ${arcR},${arcR} 0 0,1 ${arcBEx},${arcBEy}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5}
      />
      <text x={Bx - arcR - 24} y={Ay - 8} fontSize={12} fill="#374151">x°</text>

      {/* Vertex labels */}
      <text x={Ax - 14} y={Ay + 6} fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6} fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 9} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
      <text x={Fx - 4}  y={Fy + 16} fontSize={13} fill="#374151" fontWeight="600">F</text>
    </svg>
  );
};

// ── Rhombus ABCD: diagonals meet at O, M=midpoint BC, find ∠COM ───────────
// AB=AD ⇒ △ABD isosceles ⇒ ∠ADB=∠ABD.  ∠COM = 90° − ∠ADB
type RhombusCOMConfig = { angADB: number };

const RHOMBUS_COM_POOL: RhombusCOMConfig[] = [
  { angADB: 60 },  // ∠COM=30
  { angADB: 50 },  // ∠COM=40
  { angADB: 45 },  // ∠COM=45
  { angADB: 40 },  // ∠COM=50
  { angADB: 30 },  // ∠COM=60
];

function generateRhombusCOMConfig(): RhombusCOMConfig {
  return RHOMBUS_COM_POOL[Math.floor(Math.random() * RHOMBUS_COM_POOL.length)];
}

const RhombusCOMDiagram: React.FC<{ config: RhombusCOMConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angADB } = config;
  const angDAB = 180 - 2 * angADB;   // ∠DAB
  const angCOM = 90 - angADB;         // the answer
  const fv = (v: number) => demo ? '？' : String(v);
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 440, H = 290;

  // Build rhombus with auto-centering to avoid clipping for any angle
  const beta = toRad(angDAB);
  const side = 160;

  // Relative offsets from A=(0,0): up is negative Y in SVG
  const relBx = side,                        relBy = 0;
  const relDx = side * Math.cos(beta),       relDy = -side * Math.sin(beta);
  const relCx = side + relDx,               relCy = relDy;

  // Bounding box of the four vertices relative to A
  const relMinX = Math.min(0, relBx, relCx, relDx);
  const relMaxX = Math.max(0, relBx, relCx, relDx);
  const relMinY = Math.min(0, relBy, relCy, relDy);
  const relMaxY = Math.max(0, relBy, relCy, relDy);

  // Place A so shape is centered with padding 50px on all sides
  const pad = 50;
  const Ax = pad - relMinX + (W - pad * 2 - (relMaxX - relMinX)) / 2;
  const Ay = pad - relMinY + (H - pad * 2 - (relMaxY - relMinY)) / 2;

  const Bx = Ax + relBx, By = Ay + relBy;
  const Dx = Ax + relDx, Dy = Ay + relDy;
  const Cx = Ax + relCx, Cy = Ay + relCy;

  // O = midpoint of diagonals
  const Ox = (Ax + Cx) / 2, Oy = (Ay + Cy) / 2;

  // M = midpoint of BC
  const Mx = (Bx + Cx) / 2, My = (By + Cy) / 2;

  // ∠ADB arc at D
  const arcDr = 32;
  const DAang = Math.atan2(Ay - Dy, Ax - Dx);
  const DBang = Math.atan2(By - Dy, Bx - Dx);
  const arcDsx = Dx + arcDr * Math.cos(DAang), arcDsy = Dy + arcDr * Math.sin(DAang);
  const arcDex = Dx + arcDr * Math.cos(DBang), arcDey = Dy + arcDr * Math.sin(DBang);

  // ∠COM arc at O (between OC and OM)
  const arcOr = 28;
  const OCang = Math.atan2(Cy - Oy, Cx - Ox);
  const OMang = Math.atan2(My - Oy, Mx - Ox);
  const largeArc = Math.abs(angCOM) > 180 ? 1 : 0;
  // Determine sweep direction: from OC to OM
  const cross = (Cx - Ox) * (My - Oy) - (Cy - Oy) * (Mx - Ox);
  const sweepCOM = cross > 0 ? 1 : 0;
  const arcOsx = Ox + arcOr * Math.cos(OCang), arcOsy = Oy + arcOr * Math.sin(OCang);
  const arcOex = Ox + arcOr * Math.cos(OMang), arcOey = Oy + arcOr * Math.sin(OMang);

  // Label position for ∠COM (midangle between OC and OM)
  const midAng = (OCang + OMang) / 2 + (sweepCOM === 0 && OCang > OMang ? Math.PI : 0);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Rhombus */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy} ${Dx},${Dy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />

      {/* Diagonals */}
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#6b7280" strokeWidth={1.3} strokeDasharray="5,3" />
      <line x1={Bx} y1={By} x2={Dx} y2={Dy} stroke="#6b7280" strokeWidth={1.3} strokeDasharray="5,3" />

      {/* OM line */}
      <line x1={Ox} y1={Oy} x2={Mx} y2={My} stroke="#dc2626" strokeWidth={1.6} strokeDasharray="4,3" />

      {/* ∠ADB arc at D */}
      <path d={`M ${arcDsx},${arcDsy} A ${arcDr},${arcDr} 0 0,0 ${arcDex},${arcDey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text
        x={Dx + Math.cos((DAang + DBang) / 2 + Math.PI) * (arcDr + 14)}
        y={Dy + Math.sin((DAang + DBang) / 2 + Math.PI) * (arcDr + 14)}
        fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle"
      >{angADB}°</text>

      {/* ∠COM arc at O */}
      <path d={`M ${arcOsx},${arcOsy} A ${arcOr},${arcOr} 0 ${largeArc},${sweepCOM} ${arcOex},${arcOey}`}
        fill="none" stroke="#dc2626" strokeWidth={1.5} />
      <text
        x={Ox + Math.cos(midAng) * (arcOr + 14)}
        y={Oy + Math.sin(midAng) * (arcOr + 14)}
        fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="middle"
      >{fv(angCOM)}°</text>

      {/* O dot */}
      <circle cx={Ox} cy={Oy} r={5} fill="#1e40af" stroke="#fff" strokeWidth={1.5} />
      {/* M dot */}
      <circle cx={Mx} cy={My} r={3} fill="#374151" />

      {/* Vertex labels */}
      <text x={Ax - 16} y={Ay + 6}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 2}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Dx - 6}  y={Dy - 10} fontSize={13} fill="#1e40af" fontWeight="700">D</text>
      <text x={Ox + 8}  y={Oy - 8}  fontSize={15} fill="#1e40af" fontWeight="700">O</text>
      <text x={Mx + 6}  y={My + 4}  fontSize={12} fill="#374151">M</text>
    </svg>
  );
};

// ── Bar chart: two operators cleaning a hall floor ──────────────────────
// t1, t2 = minutes each operator needs alone
// A) together to clean 25%: 0.25 / (1/t1 + 1/t2) = t1*t2 / (4*(t1+t2))
// B) op2 reduces time by 1/3 → new t2' = 2*t2/3; time = 2*t1*t2/(2*t2+3*t1)
type BarChartCleaningConfig = { t1: number; t2: number };

const BAR_CHART_CLEANING_POOL: BarChartCleaningConfig[] = [
  { t1: 20, t2: 30 },  // A=3, B=10
  { t1: 40, t2: 60 },  // A=6, B=20
  { t1: 40, t2: 40 },  // A=5, B=16
];

function generateBarChartCleaningConfig(): BarChartCleaningConfig {
  return BAR_CHART_CLEANING_POOL[Math.floor(Math.random() * BAR_CHART_CLEANING_POOL.length)];
}

const BarChartCleaningDiagram: React.FC<{ config: BarChartCleaningConfig }> = ({ config }) => {
  const { t1, t2 } = config;
  const W = 300, H = 250;
  const ml = 60, mr = 15, mt = 18, mb = 54;
  const chartW = W - ml - mr;
  const chartH = H - mt - mb;
  const yMax = Math.ceil((Math.max(t1, t2) + 5) / 5) * 5;
  const yStep = 5;
  const tickCount = yMax / yStep;
  const yToSvg = (v: number) => mt + chartH * (1 - v / yMax);
  const barW = 46;
  const bar1cx = ml + chartW * 0.28;
  const bar2cx = ml + chartW * 0.72;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Gridlines + Y-axis ticks */}
      {Array.from({ length: tickCount + 1 }, (_, i) => {
        const val = i * yStep;
        const y = yToSvg(val);
        return (
          <g key={i}>
            {val > 0 && (
              <line x1={ml} y1={y} x2={ml + chartW} y2={y} stroke="#d1d5db" strokeWidth={0.8} />
            )}
            <text x={ml - 5} y={y + 4} fontSize={10} fill="#374151" textAnchor="end">{val}</text>
          </g>
        );
      })}
      {/* Axes */}
      <line x1={ml} y1={mt} x2={ml} y2={mt + chartH} stroke="#374151" strokeWidth={1.5} />
      <line x1={ml} y1={mt + chartH} x2={ml + chartW} y2={mt + chartH} stroke="#374151" strokeWidth={1.5} />
      {/* Y-axis label */}
      <text
        x={14} y={mt + chartH / 2}
        fontSize={10} fill="#374151" textAnchor="middle"
        transform={`rotate(-90, 14, ${mt + chartH / 2})`}
      >Време в минути</text>
      {/* Bar 1 */}
      <rect
        x={bar1cx - barW / 2} y={yToSvg(t1)}
        width={barW} height={chartH * t1 / yMax}
        fill="#6b7280"
      />
      <text x={bar1cx} y={mt + chartH + 16} fontSize={10} fill="#374151" textAnchor="middle">оператор 1</text>
      {/* Bar 2 */}
      <rect
        x={bar2cx - barW / 2} y={yToSvg(t2)}
        width={barW} height={chartH * t2 / yMax}
        fill="#6b7280"
      />
      <text x={bar2cx} y={mt + chartH + 16} fontSize={10} fill="#374151" textAnchor="middle">оператор 2</text>
    </svg>
  );
};

// ── Coordinate grid: points M, N, P — read coords, find Q symmetric to N, area of △MNP ──
type CoordGridConfig = { Mx: number; My: number; Nx: number; Ny: number; Px: number; Py: number };

const COORD_GRID_POOL: CoordGridConfig[] = [
  { Mx: -2, My: 3, Nx: 0, Ny: 1, Px: 4, Py: 2 },  // area=5, Q=(0,-1)
  { Mx: -2, My: 4, Nx: 0, Ny: 1, Px: 4, Py: 3 },  // area=8, Q=(0,-1)
  { Mx: -1, My: 4, Nx: 1, Ny: 1, Px: 5, Py: 3 },  // area=8, Q=(-1,-1)
  { Mx: -2, My: 4, Nx: 1, Ny: 1, Px: 5, Py: 3 },  // area=9, Q=(-1,-1)
];

function generateCoordGridConfig(): CoordGridConfig {
  return COORD_GRID_POOL[Math.floor(Math.random() * COORD_GRID_POOL.length)];
}

const CoordGridDiagram: React.FC<{ config: CoordGridConfig }> = ({ config }) => {
  const { Mx, My, Nx, Ny, Px, Py } = config;
  const xMin = -4, xMax = 6, yMin = -2, yMax = 5;
  const cell = 32;
  const ml = 32, mt = 24, mr = 28, mb = 20;
  const W = ml + (xMax - xMin) * cell + mr;
  const H = mt + (yMax - yMin) * cell + mb;
  const toX = (x: number) => ml + (x - xMin) * cell;
  const toY = (y: number) => mt + (yMax - y) * cell;
  const Ox = toX(0), Oy = toY(0);
  const gW = (xMax - xMin) * cell, gH = (yMax - yMin) * cell;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <rect x={ml} y={mt} width={gW} height={gH} fill="#f9fafb" />
      {/* grid lines */}
      {Array.from({ length: xMax - xMin + 1 }, (_, i) => (
        <line key={`vg${i}`} x1={ml + i * cell} y1={mt} x2={ml + i * cell} y2={mt + gH} stroke="#e5e7eb" strokeWidth={0.8} />
      ))}
      {Array.from({ length: yMax - yMin + 1 }, (_, i) => (
        <line key={`hg${i}`} x1={ml} y1={mt + i * cell} x2={ml + gW} y2={mt + i * cell} stroke="#e5e7eb" strokeWidth={0.8} />
      ))}
      {/* X axis */}
      <line x1={ml - 4} y1={Oy} x2={ml + gW + 14} y2={Oy} stroke="#374151" strokeWidth={1.5} />
      <polygon points={`${ml+gW+14},${Oy} ${ml+gW+7},${Oy-4} ${ml+gW+7},${Oy+4}`} fill="#374151" />
      <text x={ml + gW + 20} y={Oy + 5} fontSize={13} fill="#374151" fontWeight="600">x</text>
      {/* Y axis */}
      <line x1={Ox} y1={mt + gH + 4} x2={Ox} y2={mt - 14} stroke="#374151" strokeWidth={1.5} />
      <polygon points={`${Ox},${mt-14} ${Ox-4},${mt-7} ${Ox+4},${mt-7}`} fill="#374151" />
      <text x={Ox + 5} y={mt - 16} fontSize={13} fill="#374151" fontWeight="600">y</text>
      {/* O label */}
      <text x={Ox - 14} y={Oy + 14} fontSize={11} fill="#374151">O</text>
      {/* X ticks */}
      {Array.from({ length: xMax - xMin + 1 }, (_, i) => {
        const x = xMin + i;
        if (x === 0) return null;
        return (
          <g key={`xt${i}`}>
            <line x1={toX(x)} y1={Oy - 3} x2={toX(x)} y2={Oy + 3} stroke="#374151" strokeWidth={1} />
            <text x={toX(x)} y={Oy + 14} fontSize={9} fill="#6b7280" textAnchor="middle">{x}</text>
          </g>
        );
      })}
      {/* Y ticks */}
      {Array.from({ length: yMax - yMin + 1 }, (_, i) => {
        const y = yMin + i;
        if (y === 0) return null;
        return (
          <g key={`yt${i}`}>
            <line x1={Ox - 3} y1={toY(y)} x2={Ox + 3} y2={toY(y)} stroke="#374151" strokeWidth={1} />
            <text x={Ox - 6} y={toY(y) + 4} fontSize={9} fill="#6b7280" textAnchor="end">{y}</text>
          </g>
        );
      })}
      {/* 1 cm scale indicator (top-right of grid) */}
      {(() => {
        const sx = ml + gW - cell, sy = mt + 10;
        return (
          <g>
            <line x1={sx} y1={sy} x2={sx + cell} y2={sy} stroke="#374151" strokeWidth={1.5} />
            <line x1={sx} y1={sy - 4} x2={sx} y2={sy + 4} stroke="#374151" strokeWidth={1} />
            <line x1={sx + cell} y1={sy - 4} x2={sx + cell} y2={sy + 4} stroke="#374151" strokeWidth={1} />
            <text x={sx + cell / 2} y={sy - 7} fontSize={9} fill="#374151" textAnchor="middle">1 cm</text>
          </g>
        );
      })()}
      {/* Triangle MNP */}
      <polygon
        points={`${toX(Mx)},${toY(My)} ${toX(Nx)},${toY(Ny)} ${toX(Px)},${toY(Py)}`}
        fill="rgba(59,130,246,0.1)" stroke="#1e40af" strokeWidth={1.6}
      />
      {/* Point M */}
      <circle cx={toX(Mx)} cy={toY(My)} r={3.5} fill="#1e40af" />
      <text x={toX(Mx) - 10} y={toY(My) - 7} fontSize={12} fill="#1e40af" fontWeight="700">M</text>
      {/* Point N */}
      <circle cx={toX(Nx)} cy={toY(Ny)} r={3.5} fill="#1e40af" />
      <text x={toX(Nx) + (Nx <= 0 ? -8 : 8)} y={toY(Ny) + 16} fontSize={12} fill="#1e40af" fontWeight="700" textAnchor={Nx <= 0 ? 'end' : 'start'}>N</text>
      {/* Point P */}
      <circle cx={toX(Px)} cy={toY(Py)} r={3.5} fill="#1e40af" />
      <text x={toX(Px) + 8} y={toY(Py) - 6} fontSize={12} fill="#1e40af" fontWeight="700">P</text>
    </svg>
  );
};

// ── Grouped bar chart: Клуб Умник vs Клуб Атлет, find year with max ratio ───────────
type ClubRatioConfig = {
  data: { year: number; umnik: number; atlet: number }[];
  answerYear: number;
  answerLabel: string;
};

const CLUB_RATIO_POOL: ClubRatioConfig[] = [
  { // answer 2020 (В)
    data: [
      { year: 2018, umnik: 36, atlet: 24 },
      { year: 2019, umnik: 15, atlet: 32 },
      { year: 2020, umnik: 34, atlet: 17 },
      { year: 2021, umnik: 31, atlet: 31 },
    ],
    answerYear: 2020, answerLabel: 'В'
  },
  { // answer 2018 (А)
    data: [
      { year: 2018, umnik: 36, atlet: 18 },
      { year: 2019, umnik: 15, atlet: 20 },
      { year: 2020, umnik: 30, atlet: 20 },
      { year: 2021, umnik: 28, atlet: 30 },
    ],
    answerYear: 2018, answerLabel: 'А'
  },
  { // answer 2019 (Б)
    data: [
      { year: 2018, umnik: 20, atlet: 30 },
      { year: 2019, umnik: 35, atlet: 15 },
      { year: 2020, umnik: 25, atlet: 20 },
      { year: 2021, umnik: 20, atlet: 25 },
    ],
    answerYear: 2019, answerLabel: 'Б'
  },
  { // answer 2021 (Г)
    data: [
      { year: 2018, umnik: 18, atlet: 30 },
      { year: 2019, umnik: 25, atlet: 30 },
      { year: 2020, umnik: 30, atlet: 25 },
      { year: 2021, umnik: 35, atlet: 15 },
    ],
    answerYear: 2021, answerLabel: 'Г'
  },
];

function generateClubRatioConfig(): ClubRatioConfig {
  return CLUB_RATIO_POOL[Math.floor(Math.random() * CLUB_RATIO_POOL.length)];
}

const ClubRatioDiagram: React.FC<{ config: ClubRatioConfig }> = ({ config }) => {
  const { data } = config;
  const W = 400, H = 260;
  const ml = 54, mr = 16, mt = 16, mb = 46;
  const chartW = W - ml - mr;
  const chartH = H - mt - mb;
  const allVals = data.flatMap(d => [d.umnik, d.atlet]);
  const yMax = Math.ceil((Math.max(...allVals) + 4) / 5) * 5;
  const yStep = 5;
  const tickCount = yMax / yStep;
  const toY = (v: number) => mt + chartH * (1 - v / yMax);
  const groupW = chartW / data.length;
  const barW = groupW * 0.28;
  const gap = groupW * 0.06;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* grid + y-ticks */}
      {Array.from({ length: tickCount + 1 }, (_, i) => {
        const v = i * yStep;
        const y = toY(v);
        return (
          <g key={i}>
            {v > 0 && <line x1={ml} y1={y} x2={ml + chartW} y2={y} stroke="#e5e7eb" strokeWidth={0.8} />}
            <text x={ml - 4} y={y + 4} fontSize={10} fill="#374151" textAnchor="end">{v}</text>
          </g>
        );
      })}
      {/* axes */}
      <line x1={ml} y1={mt} x2={ml} y2={mt + chartH} stroke="#374151" strokeWidth={1.4} />
      <line x1={ml} y1={mt + chartH} x2={ml + chartW} y2={mt + chartH} stroke="#374151" strokeWidth={1.4} />
      {/* Y-axis label */}
      <text x={13} y={mt + chartH / 2} fontSize={9} fill="#374151" textAnchor="middle"
        transform={`rotate(-90, 13, ${mt + chartH / 2})`}>Брой участници</text>
      {/* X-axis label */}
      <text x={ml + chartW / 2} y={H - 3} fontSize={10} fill="#374151" textAnchor="middle">Година</text>
      {/* bars */}
      {data.map((d, i) => {
        const cx = ml + i * groupW + groupW / 2;
        const x1 = cx - gap / 2 - barW;
        const x2 = cx + gap / 2;
        return (
          <g key={d.year}>
            <rect x={x1} y={toY(d.umnik)} width={barW} height={chartH * d.umnik / yMax} fill="#374151" />
            <rect x={x2} y={toY(d.atlet)} width={barW} height={chartH * d.atlet / yMax} fill="#d1d5db" stroke="#9ca3af" strokeWidth={0.5} />
            <text x={cx} y={mt + chartH + 14} fontSize={10} fill="#374151" textAnchor="middle">{d.year}</text>
          </g>
        );
      })}
      {/* legend */}
      <rect x={ml + 6} y={mt + 4} width={12} height={10} fill="#374151" />
      <text x={ml + 22} y={mt + 13} fontSize={9} fill="#374151">Клуб Умник</text>
      <rect x={ml + 80} y={mt + 4} width={12} height={10} fill="#d1d5db" stroke="#9ca3af" strokeWidth={0.5} />
      <text x={ml + 96} y={mt + 13} fontSize={9} fill="#374151">Клуб Атлет</text>
    </svg>
  );
};

// ── O on line AC, OD bisects ∠BOC, given ∠BOD — find ∠AOB ───────────────
// ∠BOC = 2·∠BOD ⇒ ∠AOB = 180 − 2·∠BOD
type AngleBisecODConfig = { angBOD: number };

const ANGLE_BISEC_OD_POOL: AngleBisecODConfig[] = [
  { angBOD: 63 },  // ∠AOB=54
  { angBOD: 65 },  // ∠AOB=50
  { angBOD: 70 },  // ∠AOB=40
  { angBOD: 54 },  // ∠AOB=72
];

function generateAngleBisecODConfig(): AngleBisecODConfig {
  return ANGLE_BISEC_OD_POOL[Math.floor(Math.random() * ANGLE_BISEC_OD_POOL.length)];
}

const AngleBisecODDiagram: React.FC<{ config: AngleBisecODConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angBOD } = config;
  const angBOC = 2 * angBOD;
  const angAOB = 180 - angBOC;
  const fv = (v: number) => demo ? '？' : `${v}°`;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 380, H = 260;
  const Ox = 195, Oy = 195;
  const rayLen = 115;

  // OB in upper-left (angle angBOC from +x CCW)
  const OBx = Ox + rayLen * Math.cos(toRad(angBOC));
  const OBy = Oy - rayLen * Math.sin(toRad(angBOC));
  // OD in upper-right (angle angBOD from +x CCW)
  const ODx = Ox + rayLen * Math.cos(toRad(angBOD));
  const ODy = Oy - rayLen * Math.sin(toRad(angBOD));

  // Arc showing ∠BOD (between OD and OB, sweeping through top)
  const arcR = 48;
  const arcSx = Ox + arcR * Math.cos(toRad(angBOD)); // start on OD side
  const arcSy = Oy - arcR * Math.sin(toRad(angBOD));
  const arcEx = Ox + arcR * Math.cos(toRad(angBOC)); // end on OB side
  const arcEy = Oy - arcR * Math.sin(toRad(angBOC));
  // Label midpoint at 1.5*angBOD from +x
  const midAng = 1.5 * angBOD;
  const labR = arcR + 18;
  const labX = Ox + labR * Math.cos(toRad(midAng));
  const labY = Oy - labR * Math.sin(toRad(midAng));

  // Arc showing ∠AOB (between OA=-x direction and OB, sweeping through upper-left)
  const arcAOBr = 32;
  const aoAng = 180; // OA direction from +x
  const aobSx = Ox + arcAOBr * Math.cos(toRad(aoAng));
  const aobSy = Oy - arcAOBr * Math.sin(toRad(aoAng));
  const aobEx = Ox + arcAOBr * Math.cos(toRad(angBOC));
  const aobEy = Oy - arcAOBr * Math.sin(toRad(angBOC));
  const aobMidAng = (180 + angBOC) / 2;
  const aobLabR = arcAOBr + 16;
  const aobLabX = Ox + aobLabR * Math.cos(toRad(aobMidAng));
  const aobLabY = Oy - aobLabR * Math.sin(toRad(aobMidAng));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Horizontal line AC */}
      <line x1={30} y1={Oy} x2={350} y2={Oy} stroke="#374151" strokeWidth={1.8} />

      {/* Ray OB */}
      <line x1={Ox} y1={Oy} x2={OBx} y2={OBy} stroke="#374151" strokeWidth={1.6} />
      {/* Ray OD */}
      <line x1={Ox} y1={Oy} x2={ODx} y2={ODy} stroke="#374151" strokeWidth={1.6} />

      {/* Given angle arc (∠BOD) — between OD and OB, CCW in SVG through top */}
      <path d={`M ${arcSx},${arcSy} A ${arcR},${arcR} 0 0,0 ${arcEx},${arcEy}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={labX} y={labY} fontSize={13} fill="#374151" fontWeight="700" textAnchor="middle">
        {angBOD}°
      </text>

      {/* Answer arc (∠AOB) — between OA and OB */}
      <path d={`M ${aobSx},${aobSy} A ${arcAOBr},${arcAOBr} 0 0,1 ${aobEx},${aobEy}`}
        fill="none" stroke="#dc2626" strokeWidth={1.5} />
      <text x={aobLabX} y={aobLabY} fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="middle">
        {fv(angAOB)}
      </text>

      {/* Dots */}
      <circle cx={Ox} cy={Oy} r={3} fill="#374151" />
      <circle cx={30} cy={Oy} r={2.5} fill="#374151" />
      <circle cx={350} cy={Oy} r={2.5} fill="#374151" />

      {/* Labels */}
      <text x={30} y={Oy + 16} fontSize={13} fill="#1e40af" fontWeight="700" textAnchor="middle">A</text>
      <text x={Ox} y={Oy + 16} fontSize={13} fill="#374151" fontWeight="700" textAnchor="middle">O</text>
      <text x={350} y={Oy + 16} fontSize={13} fill="#1e40af" fontWeight="700" textAnchor="middle">C</text>
      <text x={OBx - 8} y={OBy - 8} fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={ODx + 6} y={ODy - 8} fontSize={13} fill="#1e40af" fontWeight="700">D</text>
    </svg>
  );
};

// ── Two lines a and b intersect: adjacent angles (2x+k1) and (x+k2) are supplementary ──
// (2x+k1)+(x+k2)=180 ⇒ x=(180-k1-k2)/3; smaller=x+k2
type IntersectLinesConfig = { k1: number; k2: number; aAng: number; bAng: number };

// Final curated pool — aAng: angle of line a from +x, bAng: angle of line b from +x
const INTERSECT_LINES_FINAL: IntersectLinesConfig[] = [
  { k1: 10, k2: 20, aAng:  5, bAng: 70 },
  { k1: 20, k2: 10, aAng: 15, bAng: 80 },
  { k1: 30, k2: 0,  aAng: 10, bAng: 60 },
  { k1: 0,  k2: 30, aAng: 20, bAng: 75 },
  { k1: 40, k2: 20, aAng:  0, bAng: 65 },
  { k1: 10, k2: 20, aAng: 25, bAng: 85 },
  { k1: 20, k2: 10, aAng:  8, bAng: 55 },
  { k1: 30, k2: 0,  aAng: 18, bAng: 78 },
];

function generateIntersectLinesConfig(): IntersectLinesConfig {
  return INTERSECT_LINES_FINAL[Math.floor(Math.random() * INTERSECT_LINES_FINAL.length)];
}

const IntersectLinesDiagram: React.FC<{ config: IntersectLinesConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { k1, k2, aAng, bAng } = config;
  const x = (180 - k1 - k2) / 3;
  const ang1 = 2 * x + k1;  // upper angle
  const ang2 = x + k2;       // lower angle (at the right of intersection)
  const smaller = Math.min(ang1, ang2);
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 360, H = 230;

  // Intersection point
  const Ix = 195, Iy = 140;
  const rayLen = 120;

  // Line a: aAng from +x; Line b: bAng from +x (steeper)
  // aAng and bAng come from config for per-entry visual variation

  // Four ray endpoints from intersection
  const aRx = Ix + rayLen * Math.cos(toRad(aAng)),      aRy = Iy - rayLen * Math.sin(toRad(aAng));
  const aLx = Ix - rayLen * Math.cos(toRad(aAng)),      aLy = Iy + rayLen * Math.sin(toRad(aAng));
  const bUx = Ix + rayLen * Math.cos(toRad(bAng)),      bUy = Iy - rayLen * Math.sin(toRad(bAng));
  const bDx = Ix - rayLen * Math.cos(toRad(bAng)),      bDy = Iy + rayLen * Math.sin(toRad(bAng));

  // The two labeled angles are: ang1 between ray b-up and ray a-right (upper region)
  //                              ang2 between ray a-right and ray b-down (lower-right region)
  // Arc for ang1 (upper between b-up and a-right): from a-right CCW to b-up
  const arc1r = 44;
  const arc1sa = toRad(aAng), arc1ea = toRad(bAng);
  const arc1sx = Ix + arc1r * Math.cos(arc1sa), arc1sy = Iy - arc1r * Math.sin(arc1sa);
  const arc1ex = Ix + arc1r * Math.cos(arc1ea), arc1ey = Iy - arc1r * Math.sin(arc1ea);
  // sweep=0 → CCW in SVG (negative-y up) → goes from a-right up to b-up ✓
  const arc1midRad = (arc1sa + arc1ea) / 2;
  const arc1labR = arc1r + 22;

  // Arc for ang2 (lower between a-right and b-down): from a-right CW down to b-down
  // b-down direction angle in standard coords: bAng + 180
  const arc2r = 38;
  const arc2sa = toRad(aAng);
  const arc2ea = toRad(bAng + 180);  // direction toward b-down
  const arc2sx = Ix + arc2r * Math.cos(arc2sa), arc2sy = Iy - arc2r * Math.sin(arc2sa);
  const arc2ex = Ix + arc2r * Math.cos(arc2ea), arc2ey = Iy - arc2r * Math.sin(arc2ea);
  // sweep=1 → CW in SVG → goes from a-right down to b-down ✓
  const arc2midRad = arc2sa - (arc2sa - (arc2ea - 2 * Math.PI)) / 2;  // midpoint going CW
  const arc2labR = arc2r + 22;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Line a */}
      <line x1={aLx} y1={aLy} x2={aRx} y2={aRy} stroke="#374151" strokeWidth={1.8} />
      {/* Line b */}
      <line x1={bDx} y1={bDy} x2={bUx} y2={bUy} stroke="#374151" strokeWidth={1.8} />

      {/* Arc for upper angle (ang1) */}
      <path d={`M ${arc1sx},${arc1sy} A ${arc1r},${arc1r} 0 0,0 ${arc1ex},${arc1ey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text
        x={Ix + arc1labR * Math.cos(arc1midRad)}
        y={Iy - arc1labR * Math.sin(arc1midRad)}
        fontSize={12} fill="#374151" textAnchor="middle"
      >{demo ? `2x+${k1}°` : `2x+${k1}°`}</text>

      {/* Arc for lower angle (ang2) */}
      <path d={`M ${arc2sx},${arc2sy} A ${arc2r},${arc2r} 0 0,1 ${arc2ex},${arc2ey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text
        x={Ix + arc2labR * Math.cos(arc2midRad)}
        y={Iy - arc2labR * Math.sin(arc2midRad)}
        fontSize={12} fill="#374151" textAnchor="middle"
      >{`x+${k2}°`}</text>

      {/* Answer: smaller angle label in red near the intersection */}
      {!demo && (
        <text x={Ix + 60} y={Iy + 30} fontSize={13} fill="#dc2626" fontWeight="700">
          → {smaller}°
        </text>
      )}

      {/* Intersection dot */}
      <circle cx={Ix} cy={Iy} r={3} fill="#374151" />

      {/* Line labels */}
      <text x={bUx + 6} y={bUy - 4} fontSize={13} fill="#1e40af" fontWeight="700">b</text>
      <text x={aLx + 4} y={aLy + 14} fontSize={13} fill="#1e40af" fontWeight="700">a</text>
    </svg>
  );
};

// ── Triangle ABC: two interior angles given, find exterior angle at a vertex ─
// extAt: exterior angle to FIND (red, ?)  givenExt: exterior angle GIVEN (purple, known)
// thirdV (the remaining vertex) shows its interior angle
type ExtAngBConfig = { angA: number; angC: number; extAt: 'A' | 'B' | 'C'; givenExt: 'A' | 'B' | 'C' };

const EXT_ANG_B_POOL: ExtAngBConfig[] = [
  // find ext at B, given ext at A, interior at C
  { angA: 35, angC: 85, extAt: 'B', givenExt: 'A' },  // intC=85, extA=145, findExtB=120
  { angA: 30, angC: 80, extAt: 'B', givenExt: 'A' },  // intC=80, extA=150, findExtB=110
  { angA: 40, angC: 95, extAt: 'B', givenExt: 'A' },  // intC=95, extA=140, findExtB=135
  // find ext at B, given ext at C, interior at A
  { angA: 35, angC: 85, extAt: 'B', givenExt: 'C' },  // intA=35, extC=95, findExtB=120
  { angA: 45, angC: 65, extAt: 'B', givenExt: 'C' },  // intA=45, extC=115, findExtB=110
  // find ext at A, given ext at B, interior at C
  { angA: 50, angC: 70, extAt: 'A', givenExt: 'B' },  // intC=70, extB=120, findExtA=130
  { angA: 55, angC: 75, extAt: 'A', givenExt: 'B' },  // intC=75, extB=130(angB=50), findExtA=125
  // find ext at A, given ext at C, interior at B
  { angA: 55, angC: 75, extAt: 'A', givenExt: 'C' },  // intB=50, extC=105, findExtA=125
  // find ext at C, given ext at A, interior at B
  { angA: 40, angC: 75, extAt: 'C', givenExt: 'A' },  // intB=65, extA=140, findExtC=105
  { angA: 30, angC: 95, extAt: 'C', givenExt: 'A' },  // intB=55, extA=150, findExtC=85(wait:180-95=85)
  // find ext at C, given ext at B, interior at A
  { angA: 40, angC: 75, extAt: 'C', givenExt: 'B' },  // intA=40, extB=115, findExtC=105
];

function generateExtAngBConfig(): ExtAngBConfig {
  return EXT_ANG_B_POOL[Math.floor(Math.random() * EXT_ANG_B_POOL.length)];
}

const ExtAngBDiagram: React.FC<{ config: ExtAngBConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angA, angC, extAt, givenExt } = config;
  const angB = 180 - angA - angC;
  const thirdV = (['A', 'B', 'C'] as const).find(v => v !== extAt && v !== givenExt)!;
  const extAngOf = (v: 'A'|'B'|'C') => v === 'A' ? 180-angA : v === 'B' ? 180-angB : 180-angC;
  const intAngOf = (v: 'A'|'B'|'C') => v === 'A' ? angA : v === 'B' ? angB : angC;
  const fv = (val: number) => demo ? '？' : `${val}°`;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 420, H = 240, pad = 48, base = 200, extLen = 65;

  const tanA = Math.tan(toRad(angA));
  const tanBv = Math.tan(toRad(angB));
  const rCx = (base * tanBv) / (tanA + tanBv);
  const rCy = -(rCx * tanA);

  // Ext tip in relative coords for each vertex
  // A: extend BA beyond A (leftward), B: extend CB beyond B, C: extend BC beyond C
  const relExtTip = (v: 'A'|'B'|'C'): [number, number] => {
    if (v === 'A') return [-extLen, 0];
    const [ox, oy] = v === 'B' ? [base, 0] : [rCx, rCy];
    const [fx, fy] = v === 'B' ? [rCx, rCy] : [base, 0];
    const dx = ox - fx, dy = oy - fy;
    const len = Math.sqrt(dx * dx + dy * dy);
    return [ox + dx / len * extLen, oy + dy / len * extLen];
  };

  const [rExtAtX, rExtAtY] = relExtTip(extAt);
  const [rExtGivX, rExtGivY] = relExtTip(givenExt);

  const allX = [0, base, rCx, rExtAtX, rExtGivX];
  const allY = [0, 0, rCy, rExtAtY, rExtGivY];
  const minX = Math.min(...allX), maxX = Math.max(...allX);
  const minY = Math.min(...allY), maxY = Math.max(...allY);
  const sc = Math.min((W - pad * 2) / (maxX - minX || 1), (H - pad * 2) / (maxY - minY || 1), 1.6);
  const tx = pad - minX * sc + (W - pad * 2 - (maxX - minX) * sc) / 2;
  const ty = pad - minY * sc + (H - pad * 2 - (maxY - minY) * sc) / 2;
  const t = (rx: number, ry: number): [number, number] => [rx * sc + tx, ry * sc + ty];

  const [Ax, Ay] = t(0, 0);
  const [Bx, By] = t(base, 0);
  const [Cx, Cy] = t(rCx, rCy);
  const [ExtAtX, ExtAtY] = t(rExtAtX, rExtAtY);
  const [ExtGivX, ExtGivY] = t(rExtGivX, rExtGivY);

  const vPos = (v: 'A'|'B'|'C'): [number, number] => v === 'A' ? [Ax, Ay] : v === 'B' ? [Bx, By] : [Cx, Cy];
  // The non-extended adjacent vertex for each exterior arc:
  // A extends BA → arc between C-direction and ext tip
  // B extends CB → arc between A-direction and ext tip
  // C extends BC → arc between A-direction and ext tip
  const extAdjV = (v: 'A'|'B'|'C'): 'A'|'B'|'C' => v === 'A' ? 'C' : 'A';

  const arcR = 26, arcRext = 28;

  const intArcEl = (v: 'A'|'B'|'C') => {
    const [Vx, Vy] = vPos(v);
    const others = (['A', 'B', 'C'] as const).filter(x => x !== v) as ['A'|'B'|'C', 'A'|'B'|'C'];
    const [U1x, U1y] = vPos(others[0]);
    const [U2x, U2y] = vPos(others[1]);
    const d1 = Math.atan2(U1y - Vy, U1x - Vx);
    const d2 = Math.atan2(U2y - Vy, U2x - Vx);
    const sx = Vx + arcR * Math.cos(d1), sy = Vy + arcR * Math.sin(d1);
    const ex2 = Vx + arcR * Math.cos(d2), ey2 = Vy + arcR * Math.sin(d2);
    const sweep = (Math.cos(d1) * Math.sin(d2) - Math.sin(d1) * Math.cos(d2)) > 0 ? 1 : 0;
    const mid = (d1 + d2) / 2;
    return (<g key={`int-${v}`}>
      <path d={`M ${sx},${sy} A ${arcR},${arcR} 0 0,${sweep} ${ex2},${ey2}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text x={Vx + (arcR + 16) * Math.cos(mid)} y={Vy + (arcR + 16) * Math.sin(mid)}
        fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{intAngOf(v)}°</text>
    </g>);
  };

  const extArcEl = (v: 'A'|'B'|'C', etx: number, ety: number, label: string, color: string) => {
    const [Vx, Vy] = vPos(v);
    const [Wx, Wy] = vPos(extAdjV(v));
    const d1 = Math.atan2(Wy - Vy, Wx - Vx);
    const d2 = Math.atan2(ety - Vy, etx - Vx);
    const sx = Vx + arcRext * Math.cos(d1), sy = Vy + arcRext * Math.sin(d1);
    const epx = Vx + arcRext * Math.cos(d2), epy = Vy + arcRext * Math.sin(d2);
    const sweep = (Math.cos(d1) * Math.sin(d2) - Math.sin(d1) * Math.cos(d2)) > 0 ? 1 : 0;
    const mid = (d1 + d2) / 2;
    return (<g key={`ext-${v}`}>
      <path d={`M ${sx},${sy} A ${arcRext},${arcRext} 0 0,${sweep} ${epx},${epy}`}
        fill="none" stroke={color} strokeWidth={1.5} />
      <text x={Vx + (arcRext + 20) * Math.cos(mid)} y={Vy + (arcRext + 20) * Math.sin(mid)}
        fontSize={13} fill={color} fontWeight="700" textAnchor="middle">{label}</text>
    </g>);
  };

  const [eAtVx, eAtVy] = vPos(extAt);
  const [eGivVx, eGivVy] = vPos(givenExt);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="rgba(59,130,246,0.08)" stroke="#1e40af" strokeWidth={1.7} />

      {/* Two exterior rays */}
      <line x1={eAtVx} y1={eAtVy} x2={ExtAtX} y2={ExtAtY} stroke="#374151" strokeWidth={1.7} />
      <line x1={eGivVx} y1={eGivVy} x2={ExtGivX} y2={ExtGivY} stroke="#374151" strokeWidth={1.7} />

      {/* Arcs */}
      {extArcEl(extAt, ExtAtX, ExtAtY, fv(extAngOf(extAt)), '#dc2626')}
      {extArcEl(givenExt, ExtGivX, ExtGivY, `${extAngOf(givenExt)}°`, '#7c3aed')}
      {intArcEl(thirdV)}

      {/* Vertex dots */}
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />

      {/* Vertex labels */}
      <text x={Ax - 12} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx - 6} y={By + 16} fontSize={13} fill="#1e40af" fontWeight="700" textAnchor="middle">B</text>
      <text x={Cx + 8} y={Cy - 6} fontSize={13} fill="#1e40af" fontWeight="700">C</text>
    </svg>
  );
};

// ── Isosceles △ABC (AC=BC), CH altitude, AH and AH:HC given, find BC ────────
// H is midpoint of AB (isosceles), BC=√(HB²+HC²), HB=AH
type IsoscAltConfig = { AH: number; ratioP: number; ratioQ: number }; // AH:HC = ratioP:ratioQ

const ISOSC_ALT_POOL: IsoscAltConfig[] = [
  { AH: 3, ratioP: 3, ratioQ: 4 },  // HC=4, BC=5
  { AH: 4, ratioP: 4, ratioQ: 3 },  // HC=3, BC=5
  { AH: 6, ratioP: 3, ratioQ: 4 },  // HC=8, BC=10
  { AH: 5, ratioP: 5, ratioQ: 12 }, // HC=12, BC=13
];

function generateIsoscAltConfig(): IsoscAltConfig {
  return ISOSC_ALT_POOL[Math.floor(Math.random() * ISOSC_ALT_POOL.length)];
}

const IsoscAltDiagram: React.FC<{ config: IsoscAltConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { AH, ratioP, ratioQ } = config;
  const HC = AH * ratioQ / ratioP;
  const HB = AH;
  const BC = Math.round(Math.sqrt(HC * HC + HB * HB));
  const fv = (v: number) => demo ? '？' : `${v} cm`;
  const W = 380, H = 240, pad = 44;

  // Auto-fit: relative coords — A=(0,0), H=(AH,0), B=(2*AH,0), C=(AH,-HC)
  const totalAB = 2 * AH;
  const scX = (W - pad * 2) / totalAB;
  const scY = (H - pad * 2) / HC;
  const sc = Math.min(scX, scY, 30);
  const tx = (W - totalAB * sc) / 2;
  const ty = pad + HC * sc;  // baseline y so C lands at pad from top

  const Ax = tx,            Ay = ty;
  const Hx = tx + AH * sc,  Hy = ty;
  const Bx = tx + totalAB * sc, By = ty;
  const Cx = Hx,            Cy = ty - HC * sc;

  // Arc+dot right-angle marker at H (foot of altitude, where CH ⊥ AB)
  const arcR = 10;
  const arcSx = Hx, arcSy = Hy - arcR;  // along CH direction (upward)
  const arcEx = Hx + arcR, arcEy = Hy;   // along HB direction (rightward)
  const dotX = Hx + arcR / 2, dotY = Hy - arcR / 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Full isosceles triangle ACB */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="rgba(59,130,246,0.08)" stroke="#1e40af" strokeWidth={1.7} />
      {/* Altitude CH */}
      <line x1={Cx} y1={Cy} x2={Hx} y2={Hy} stroke="#6b7280" strokeWidth={1.5} strokeDasharray="5,3" />
      {/* Right-angle arc+dot at H */}
      <path d={`M ${arcSx},${arcSy} A ${arcR},${arcR} 0 0,1 ${arcEx},${arcEy}`} fill="none" stroke="#374151" strokeWidth={1.3} />
      <circle cx={dotX} cy={dotY} r={2.2} fill="#374151" />

      {/* AH label */}
      <text x={(Ax + Hx) / 2} y={Ay + 16} fontSize={12} fill="#374151" textAnchor="middle">{AH}</text>
      {/* HB label */}
      <text x={(Hx + Bx) / 2} y={Ay + 16} fontSize={12} fill="#374151" textAnchor="middle">{HB}</text>

      {/* BC label (answer) */}
      <text
        x={(Bx + Cx) / 2 + 14}
        y={(By + Cy) / 2}
        fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="start"
      >{fv(BC)}</text>

      {/* Vertex dots */}
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <circle cx={Hx} cy={Hy} r={3} fill="#374151" />

      {/* Labels */}
      <text x={Ax - 12} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 14} fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 6}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Hx - 4}  y={Hy + 15} fontSize={12} fill="#374151" fontWeight="700">H</text>
    </svg>
  );
};

// ── Task 29: random triangle only ──
type PerpBisecBCConfig = { angA: number };

const PERP_BISEC_BC_POOL: PerpBisecBCConfig[] = [
  { angA: 40 },
  { angA: 52 },
  { angA: 64 },
  { angA: 76 },
  { angA: 88 },
  { angA: 100 },
  { angA: 112 },
];

function generatePerpBisecBCConfig(): PerpBisecBCConfig {
  return PERP_BISEC_BC_POOL[Math.floor(Math.random() * PERP_BISEC_BC_POOL.length)];
}

const PerpBisecBCDiagram: React.FC<{ config: PerpBisecBCConfig; demo?: boolean }> = ({ config }) => {
  const { angA } = config;
  const toRad = (d: number) => d * Math.PI / 180;

  // Build triangle in math coords (y-up), keeping angle B fixed at 30°
  const angB = 30;
  const angC = 180 - angA - angB;
  const c = 220;
  const AC = c * Math.sin(toRad(angB)) / Math.sin(toRad(angC));
  const mCx = AC * Math.cos(toRad(angA));
  const mCy = AC * Math.sin(toRad(angA));

  // D = midpoint of BC and M = intersection of s_CB with AB
  const mDx = (c + mCx) / 2;
  const mDy = mCy / 2;
  const BCvx = mCx - c;
  const BCvy = mCy;
  let pX = -BCvy;
  let pY = BCvx;
  if (pY > 0) {
    pX = BCvy;
    pY = -BCvx;
  }
  const tParam = -mDy / pY;
  const mMx = mDx + tParam * pX;
  const pLen = Math.sqrt(pX * pX + pY * pY);
  const upX = pX / pLen;
  const upY = pY / pLen;
  const extLen = 28;
  const mExtX = mDx - upX * extLen;
  const mExtY = mDy - upY * extLen;

  // SVG auto-scale with y-flip
  const W = 460, H = 300, pad = 50;
  const allMX = [0, c, mCx, mDx, mMx, mExtX];
  const allMY = [0, 0, mCy, mDy, 0, mExtY];
  const minX = Math.min(...allMX), maxX = Math.max(...allMX);
  const minY = Math.min(...allMY), maxY = Math.max(...allMY);
  const sc = Math.min((W - 2 * pad) / (maxX - minX || 1), (H - 2 * pad) / (maxY - minY || 1));
  const drawW = (maxX - minX) * sc, drawH = (maxY - minY) * sc;
  const leftPad = pad + (W - 2 * pad - drawW) / 2;
  const botPad  = pad + (H - 2 * pad - drawH) / 2;
  const tr = (mx: number, my: number): [number, number] => [
    (mx - minX) * sc + leftPad,
    H - ((my - minY) * sc + botPad),
  ];

  const [Ax, Ay] = tr(0, 0);
  const [Bx, By] = tr(c, 0);
  const [Cx, Cy] = tr(mCx, mCy);
  const [Dx, Dy] = tr(mDx, mDy);
  const [Mx, My] = tr(mMx, 0);
  const [ExtX, ExtY] = tr(mExtX, mExtY);

  const arcRb = 28;
  const BAang = Math.atan2(Ay - By, Ax - Bx);
  const BCang = Math.atan2(Cy - By, Cx - Bx);
  const bArcSx = Bx + arcRb * Math.cos(BAang);
  const bArcSy = By + arcRb * Math.sin(BAang);
  const bArcEx = Bx + arcRb * Math.cos(BCang);
  const bArcEy = By + arcRb * Math.sin(BCang);
  const bSweep = (Math.cos(BAang) * Math.sin(BCang) - Math.sin(BAang) * Math.cos(BCang)) > 0 ? 1 : 0;
  const bMid = (BAang + BCang) / 2;

  const cLblOffX = mCx < c / 2 ? -20 : 8;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="none" stroke="#1e40af" strokeWidth={1.8} />
      <line x1={Cx} y1={Cy} x2={Mx} y2={My} stroke="#334155" strokeWidth={1.6} />
      <line x1={Mx} y1={My} x2={ExtX} y2={ExtY} stroke="#374151" strokeWidth={1.5} strokeDasharray="6,3" />
      <path d={`M ${bArcSx},${bArcSy} A ${arcRb},${arcRb} 0 0,${bSweep} ${bArcEx},${bArcEy}`} fill="none" stroke="#374151" strokeWidth={1.4} />
      <text x={Bx + Math.cos(bMid) * (arcRb + 18)} y={By + Math.sin(bMid) * (arcRb + 18)} fontSize={13} fill="#374151" fontWeight="600" textAnchor="middle">30°</text>
      <text x={ExtX + 5} y={ExtY - 6} fontSize={11} fill="#374151" fontStyle="italic">s_CB</text>
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <circle cx={Dx} cy={Dy} r={3} fill="#374151" />
      <circle cx={Mx} cy={My} r={3} fill="#374151" />
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 8}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + cLblOffX} y={Cy - 8} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
      <text x={Mx - 7} y={My + 18} fontSize={13} fill="#374151" fontWeight="700">M</text>
      <text x={Dx + 8} y={Dy + 4} fontSize={13} fill="#374151" fontWeight="700">D</text>
    </svg>
  );
};

// ── Parallelogram ABCD: DL bisects ∠D, ∠ALD given, find ∠DAB ──────────────
// △ADL: ∠DAL + ∠ADL + ∠ALD = 180; ∠ADL=(∠ADC)/2=(180-∠DAB)/2
// ⇒ ∠DAL + (180-∠DAB)/2 + ∠ALD = 180 ⇒ ∠DAB/2 = 180 - 90 - ∠ALD = 90 - ∠ALD
// ∠DAB = 2*(90 - ∠ALD)  ... wait: ∠DAL=∠DAB, so:
// ∠DAB + (180-∠DAB)/2 + ∠ALD = 180 ⇒ ∠DAB - ∠DAB/2 = 180 - 90 - ∠ALD = 90 - ∠ALD
// ∠DAB/2 = 90 - ∠ALD ⇒ ∠DAB = 180 - 2*∠ALD
type ParallelDLConfig = { angALD: number };

const PARALLEL_DL_POOL: ParallelDLConfig[] = [
  { angALD: 65 },  // ∠DAB=50
  { angALD: 60 },  // ∠DAB=60
  { angALD: 70 },  // ∠DAB=40
  { angALD: 55 },  // ∠DAB=70
  { angALD: 75 },  // ∠DAB=30
];

function generateParallelDLConfig(): ParallelDLConfig {
  return PARALLEL_DL_POOL[Math.floor(Math.random() * PARALLEL_DL_POOL.length)];
}

const ParallelDLDiagram: React.FC<{ config: ParallelDLConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angALD } = config;
  const angDAB = 180 - 2 * angALD;
  const angADC = 180 - angDAB;
  const angADL = angADC / 2;
  const fv = (v: number) => demo ? '？' : `${v}°`;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 420, H = 200;

  // Parallelogram: A bottom-left, B bottom-right, C top-right, D top-left
  // Draw with slant matching image (D above-left of A)
  const Ax = 55,  Ay = 165;
  const Bx = 320, By = 165;
  const slant = 55; // horizontal offset for top side
  const ht = 100;   // height
  const Dx = Ax + slant, Dy = Ay - ht;
  const Cx = Bx + slant, Cy = Ay - ht;

  // L on AB: from A at ∠DAB along AD direction... actually L is foot of DL on AB
  // In △ADL, ∠DAL=angDAB, ∠ALD=angALD, ∠ADL=angADL
  // Use sine rule: AL/sin(angADL) = AD/sin(angALD)
  const ADlen = Math.sqrt((Dx - Ax) ** 2 + (Dy - Ay) ** 2);
  const AL_ratio = Math.sin(toRad(angADL)) / Math.sin(toRad(angALD));
  const ALpx = AL_ratio * ADlen; // in pixels along AB direction
  const ABlen = Bx - Ax;
  const Lx = Ax + Math.min(ALpx, ABlen * 0.85);
  const Ly = Ay;

  // Arc at A for ∠DAB (answer)
  const arcAr = 28;
  const ADang = Math.atan2(Dy - Ay, Dx - Ax);
  const ABang = 0; // horizontal
  const arcAsx = Ax + arcAr * Math.cos(ADang), arcAsy = Ay + arcAr * Math.sin(ADang);
  const arcAex = Ax + arcAr, arcAey = Ay;

  // Arc at L for ∠ALD
  const arcLr = 26;
  const LAang = Math.atan2(Ay - Ly, Ax - Lx); // toward A = Math.PI
  const LDang = Math.atan2(Dy - Ly, Dx - Lx);
  const arcLsx = Lx + arcLr * Math.cos(LAang), arcLsy = Ly + arcLr * Math.sin(LAang);
  const arcLex = Lx + arcLr * Math.cos(LDang), arcLey = Ly + arcLr * Math.sin(LDang);
  const angLmid = (LAang + LDang) / 2;

  // Arc at D for ∠ADC (one whole arc)
  const arcDr = 24;
  const DAang = Math.atan2(Ay - Dy, Ax - Dx);
  const DCang = Math.atan2(Cy - Dy, Cx - Dx);
  const arcDsx = Dx + arcDr * Math.cos(DAang), arcDsy = Dy + arcDr * Math.sin(DAang);
  const arcDex = Dx + arcDr * Math.cos(DCang), arcDey = Dy + arcDr * Math.sin(DCang);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Parallelogram */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy} ${Dx},${Dy}`}
        fill="rgba(59,130,246,0.07)" stroke="#1e40af" strokeWidth={1.7} />
      {/* DL line */}
      <line x1={Dx} y1={Dy} x2={Lx} y2={Ly} stroke="#374151" strokeWidth={1.5} />

      {/* Whole arc at D for ∠ADC */}
      <path d={`M ${arcDsx},${arcDsy} A ${arcDr},${arcDr} 0 0,0 ${arcDex},${arcDey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.3} />

      {/* Arc at L for ∠ALD */}
      <path d={`M ${arcLsx},${arcLsy} A ${arcLr},${arcLr} 0 0,1 ${arcLex},${arcLey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text
        x={Lx + Math.cos(angLmid) * (arcLr + 16)}
        y={Ly + Math.sin(angLmid) * (arcLr + 16)}
        fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle"
      >{angALD}°</text>

      {/* Arc at A for ∠DAB (answer) */}
      <path d={`M ${arcAsx},${arcAsy} A ${arcAr},${arcAr} 0 0,0 ${arcAex},${arcAey}`}
        fill="none" stroke="#dc2626" strokeWidth={1.5} />
      <text
        x={Ax + Math.cos((ADang + ABang) / 2) * (arcAr + 16)}
        y={Ay + Math.sin((ADang + ABang) / 2) * (arcAr + 16)}
        fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="middle"
      >{fv(angDAB)}</text>

      {/* Dots */}
      {[{x:Ax,y:Ay},{x:Bx,y:By},{x:Cx,y:Cy},{x:Dx,y:Dy},{x:Lx,y:Ly}].map((p,i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#374151" />
      ))}
      {/* Labels */}
      <text x={Ax - 14} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 14} fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 4}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Dx - 6}  y={Dy - 8}  fontSize={13} fill="#1e40af" fontWeight="700">D</text>
      <text x={Lx - 4}  y={Ly + 15} fontSize={12} fill="#374151" fontWeight="600">L</text>
    </svg>
  );
};

// ── Rectangular parallelepiped: mixed units, find volume in dm³ ──────────────
type BoxEdge = 'AB' | 'A1B1' | 'BC' | 'D1C1' | 'AA1' | 'BB1';

type BoxVolumeLabel = {
  text: string;
  edge: BoxEdge;
};

type BoxVolumeConfig = {
  vol: number;
  dmValues: [number, number, number];
  labels: [BoxVolumeLabel, BoxVolumeLabel, BoxVolumeLabel];
};

const BOX_VOLUME_DIM_POOL = [
  { widthDm: 2, depthDm: 3, heightDm: 5 },
  { widthDm: 3, depthDm: 2, heightDm: 4 },
  { widthDm: 5, depthDm: 4, heightDm: 2 },
  { widthDm: 4, depthDm: 5, heightDm: 3 },
  { widthDm: 6, depthDm: 2, heightDm: 3 },
  { widthDm: 2, depthDm: 7, heightDm: 2 },
  { widthDm: 3, depthDm: 6, heightDm: 2 },
  { widthDm: 5, depthDm: 2, heightDm: 6 },
];

function pickOne<T>(values: T[]): T {
  return values[Math.floor(Math.random() * values.length)];
}

function formatDmInRandomMetric(dm: number): string {
  const unit = pickOne(['dm', 'cm', 'mm'] as const);
  if (unit === 'dm') return `${dm} dm`;
  if (unit === 'cm') return `${dm * 10} cm`;
  return `${dm * 100} mm`;
}

function generateBoxVolumeConfig(): BoxVolumeConfig {
  const { widthDm, depthDm, heightDm } = pickOne(BOX_VOLUME_DIM_POOL);
  const widthEdge = pickOne(['AB', 'A1B1'] as const);
  const depthEdge = pickOne(['BC', 'D1C1'] as const);
  const heightEdge = pickOne(['AA1', 'BB1'] as const);

  return {
    vol: widthDm * depthDm * heightDm,
    dmValues: [widthDm, depthDm, heightDm],
    labels: [
      { text: formatDmInRandomMetric(widthDm), edge: widthEdge },
      { text: formatDmInRandomMetric(depthDm), edge: depthEdge },
      { text: formatDmInRandomMetric(heightDm), edge: heightEdge },
    ],
  };
}

const BoxVolumeDiagram: React.FC<{ config: BoxVolumeConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { labels, vol } = config;
  const fv = (v: number) => demo ? '？' : String(v);
  const W = 420, H = 280;
  // Isometric parallelepiped: front-bottom-left = A
  const ox = 95, oy = 205;
  const w = 160, h = 105;
  const dx = 48, dy = -28; // depth vector (back goes right-up)
  // Vertex layout:
  // Bottom face: A(front-left), B(front-right), C(back-right), D(back-left)
  // Top face:    A₁, B₁, C₁, D₁
  const A  = [ox,       oy      ];
  const B  = [ox+w,     oy      ];
  const C  = [ox+w+dx,  oy+dy   ];
  const D  = [ox+dx,    oy+dy   ];
  const A1 = [ox,       oy-h    ];
  const B1 = [ox+w,     oy-h    ];
  const C1 = [ox+w+dx,  oy-h+dy ];
  const D1 = [ox+dx,    oy-h+dy ];
  const poly = (pts: number[][], fill: string) =>
    <polygon points={pts.map(p => p.join(',')).join(' ')} fill={fill} stroke="#374151" strokeWidth={1.6} />;
  const ln = (p1: number[], p2: number[], dash?: string) =>
    <line x1={p1[0]} y1={p1[1]} x2={p2[0]} y2={p2[1]} stroke="#9ca3af" strokeWidth={1.1} strokeDasharray={dash} />;

  const edgeLabelPos = (edge: BoxEdge) => {
    switch (edge) {
      case 'AB':
        return { x: (A[0] + B[0]) / 2, y: A[1] + 17, anchor: 'middle' as const };
      case 'A1B1':
        return { x: (A1[0] + B1[0]) / 2, y: A1[1] - 10, anchor: 'middle' as const };
      case 'BC':
        return { x: (B[0] + C[0]) / 2 + 10, y: (B[1] + C[1]) / 2 + 12, anchor: 'start' as const };
      case 'D1C1':
        return { x: (D1[0] + C1[0]) / 2 + 8, y: (D1[1] + C1[1]) / 2 - 8, anchor: 'start' as const };
      case 'AA1':
        return { x: A1[0] - 12, y: (A[1] + A1[1]) / 2 + 4, anchor: 'end' as const };
      case 'BB1':
        return { x: B1[0] + 10, y: (B[1] + B1[1]) / 2 + 4, anchor: 'start' as const };
    }
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Only the 3 visible faces */}
      {poly([A,B,B1,A1], '#e0effe')}
      {poly([B,C,C1,B1], '#bfdbfe')}
      {poly([A1,B1,C1,D1], '#eff6ff')}
      {/* Hidden edges — D is the back-bottom-left vertex, invisible from this angle */}
      {ln(D, A,  '5,3')}
      {ln(D, C,  '5,3')}
      {ln(D, D1, '5,3')}
      {/* Dimension labels */}
      {labels.map((label, index) => {
        const pos = edgeLabelPos(label.edge);
        return (
          <text
            key={`${label.edge}-${index}`}
            x={pos.x}
            y={pos.y}
            fontSize={12}
            fill="#374151"
            textAnchor={pos.anchor}
          >
            {label.text}
          </text>
        );
      })}
      {/* Volume answer */}
      <text x={W/2} y={H-10} fontSize={15} fill="#dc2626" fontWeight="700" textAnchor="middle">V = {fv(vol)} dm³</text>
      {/* Vertex dots — D shown faded (hidden vertex) */}
      {[A,B,C,A1,B1,C1,D1].map((p,i) => <circle key={i} cx={p[0]} cy={p[1]} r={3} fill="#374151"/>)}
      <circle cx={D[0]} cy={D[1]} r={3} fill="#9ca3af"/>
      {/* Vertex labels */}
      <text x={A[0]-14}  y={A[1]+14}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={B[0]+6}   y={B[1]+14}  fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={C[0]+6}   y={C[1]+12}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={D[0]-14}  y={D[1]+14}  fontSize={13} fill="#9ca3af" fontWeight="600">D</text>
      <text x={A1[0]-16} y={A1[1]-6}  fontSize={13} fill="#1e40af" fontWeight="700">A₁</text>
      <text x={B1[0]+6}  y={B1[1]-6}  fontSize={13} fill="#1e40af" fontWeight="700">B₁</text>
      <text x={C1[0]+6}  y={C1[1]-6}  fontSize={13} fill="#1e40af" fontWeight="700">C₁</text>
      <text x={D1[0]-18} y={D1[1]-6}  fontSize={13} fill="#1e40af" fontWeight="700">D₁</text>
    </svg>
  );
};

// ── Season Survey bar chart: 200 people, 4 seasons, find k ─────────────
type SeasonSurveyConfig = {
  k: number; essen: number; addExtra: number;
  peNum: number; peDen: number;
  lyaNum: number; lyaDen: number;
  percent: number;
};
const SEASON_SURVEY_POOL: SeasonSurveyConfig[] = [
  { k:15, essen:50, addExtra:50, peNum:6,  peDen:5,  lyaNum:5, lyaDen:1, percent:25 },
  { k:14, essen:60, addExtra:40, peNum:14, peDen:15, lyaNum:5, lyaDen:1, percent:20 },
  { k:16, essen:40, addExtra:20, peNum:8,  peDen:5,  lyaNum:5, lyaDen:1, percent:10 },
  { k:17, essen:30, addExtra:60, peNum:34, peDen:15, lyaNum:5, lyaDen:1, percent:30 },
];
function generateSeasonSurveyConfig(): SeasonSurveyConfig {
  return SEASON_SURVEY_POOL[Math.floor(Math.random() * SEASON_SURVEY_POOL.length)];
}
const SeasonSurveyDiagram: React.FC<{ config: SeasonSurveyConfig }> = ({ config }) => {
  const { k, essen } = config;
  const counts = [k, 4*k, 5*k, essen];
  const maxVal = 5 * k;
  const cx = 55, cy = 20, cW = 220, cH = 160;
  const barW = 34;
  const gap = (cW - 4 * barW) / 5;
  const bx = (i: number) => cx + gap + i * (barW + gap);
  const bh = (v: number) => (v / maxVal) * cH;
  const by = (v: number) => cy + cH - bh(v);
  const dashLevels = Array.from(new Set([k, essen, 4*k, 5*k])).sort((a, b) => a - b);
  const laby = (v: number) => cy + cH - (v / maxVal) * cH;
  const seasons = ['Зима', 'Пролет', 'Лято', 'Есен'];
  const yLabel = (v: number) => v === k ? 'k' : v === 4*k ? '4k' : v === 5*k ? '5k' : String(v);
  return (
    <svg width={380} height={215} viewBox="0 0 380 215">
      <rect x={cx} y={cy} width={cW} height={cH} fill="#F9FAFB" stroke="#E5E7EB"/>
      {dashLevels.map(v => (
        <line key={v} x1={cx} y1={laby(v)} x2={cx+cW} y2={laby(v)} stroke="#9CA3AF" strokeWidth={1} strokeDasharray="5,3"/>
      ))}
      {dashLevels.map(v => (
        <text key={`l${v}`} x={cx-4} y={laby(v)+4} fontSize={10} fill="#4B5563" textAnchor="end">{yLabel(v)}</text>
      ))}
      <text x={cx-4} y={cy+cH+4} fontSize={10} fill="#4B5563" textAnchor="end">0</text>
      {counts.map((c, i) => (
        <rect key={i} x={bx(i)} y={by(c)} width={barW} height={bh(c)} fill="#3B82F6" rx={2}/>
      ))}
      {seasons.map((s, i) => (
        <text key={i} x={bx(i)+barW/2} y={cy+cH+14} fontSize={10} fill="#374151" textAnchor="middle">{s}</text>
      ))}
      <line x1={cx} y1={cy} x2={cx} y2={cy+cH} stroke="#374151" strokeWidth={1.5}/>
      <line x1={cx} y1={cy+cH} x2={cx+cW} y2={cy+cH} stroke="#374151" strokeWidth={1.5}/>
      <polygon points={`${cx},${cy} ${cx-3},${cy+7} ${cx+3},${cy+7}`} fill="#374151"/>
      <polygon points={`${cx+cW},${cy+cH} ${cx+cW-7},${cy+cH-3} ${cx+cW-7},${cy+cH+3}`} fill="#374151"/>
      <text x={13} y={cy+cH/2} fontSize={9} fill="#6B7280" textAnchor="middle"
        transform={`rotate(-90,13,${cy+cH/2})`}>Брой любими сезони</text>
    </svg>
  );
};

// ── Right triangles △ABC and △ABD sharing hypotenuse AB ────────────────
// C on perp bisector of AB → △ABC isosceles right (∠ACB=90°)
// ∠BAD:∠ABD = 1:5, sum=90° → ∠BAD=15°, ∠ABD=75°
// DM = AB/2 (median to hyp), DH = AB/4, area△ABC=AB²/4, area△ABD=AB²/8
type RightTriABConfig = { dm: number; ab: number; areaABC: number; areaABD: number };
const RIGHT_TRI_AB_POOL: RightTriABConfig[] = [
  { dm:4,  ab:8,  areaABC:16,  areaABD:8  },
  { dm:6,  ab:12, areaABC:36,  areaABD:18 },
  { dm:8,  ab:16, areaABC:64,  areaABD:32 },
  { dm:10, ab:20, areaABC:100, areaABD:50 },
];
function generateRightTriABConfig(): RightTriABConfig {
  return RIGHT_TRI_AB_POOL[Math.floor(Math.random() * RIGHT_TRI_AB_POOL.length)];
}
const RightTriABDiagram: React.FC<{ config: RightTriABConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { dm, ab } = config;
  const fv = (v: number) => demo ? '？' : String(v);
  // Fixed layout coordinates (shape is always same proportions)
  const W = 330, H = 210;
  const ax = 40, ay = 115;
  const bx = 265, by = 115;
  const mx = (ax + bx) / 2, my = ay;            // midpoint M
  const cx = mx, cy = 35;                        // C on perp bisector above M
  // D: ∠DAB=15° below AB, DH = AB/4 px
  const abPx = bx - ax;
  const dh = abPx / 4;                           // DH in px
  // HA = DH/tan(15°)
  const ha = dh / Math.tan(15 * Math.PI / 180);
  const hxC = ax + ha;                           // foot H x-coordinate
  const dy = ay + dh;                            // D y-coordinate
  const dx = hxC;                                // D x-coordinate (directly above H)
  // Right-angle arc+dot at C
  const arcR = 10;
  const CAx = ax - cx, CAy = ay - cy;
  const CAlen = Math.sqrt(CAx * CAx + CAy * CAy);
  const CBx = bx - cx, CBy = by - cy;
  const CBlen = Math.sqrt(CBx * CBx + CBx * 0 + CBy * CBy);
  const uCAx = CAx / CAlen, uCAy = CAy / CAlen;
  const uCBx = CBx / CBlen, uCBy = CBy / CBlen;
  const cArcSx = cx + arcR * uCAx, cArcSy = cy + arcR * uCAy;
  const cArcEx = cx + arcR * uCBx, cArcEy = cy + arcR * uCBy;
  const cSweep = (uCAx * uCBy - uCAy * uCBx) > 0 ? 1 : 0;
  const cDotX = cx + arcR / 2 * (uCAx + uCBx);
  const cDotY = cy + arcR / 2 * (uCAy + uCBy);

  // Right-angle arc+dot at D
  const DAx = ax - dx, DAy = ay - dy;
  const DAlen = Math.sqrt(DAx * DAx + DAy * DAy);
  const DBx = bx - dx, DBy = by - dy;
  const DBlen = Math.sqrt(DBx * DBx + DBy * DBy);
  const uDAx = DAx / DAlen, uDAy = DAy / DAlen;
  const uDBx = DBx / DBlen, uDBy = DBy / DBlen;
  const dArcSx = dx + arcR * uDAx, dArcSy = dy + arcR * uDAy;
  const dArcEx = dx + arcR * uDBx, dArcEy = dy + arcR * uDBy;
  const dSweep = (uDAx * uDBy - uDAy * uDBx) > 0 ? 1 : 0;
  const dDotX = dx + arcR / 2 * (uDAx + uDBx);
  const dDotY = dy + arcR / 2 * (uDAy + uDBy);
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} fontFamily="sans-serif">
      {/* Perpendicular bisector line (S_AB) */}
      <line x1={mx} y1={5} x2={mx} y2={H - 5} stroke="#9CA3AF" strokeWidth={1} strokeDasharray="5,3"/>
      <text x={mx+4} y={14} fontSize={11} fill="#6B7280">S_AB</text>
      {/* Triangle ABC */}
      <line x1={ax} y1={ay} x2={cx} y2={cy} stroke="#2563EB" strokeWidth={1.5}/>
      <line x1={bx} y1={by} x2={cx} y2={cy} stroke="#2563EB" strokeWidth={1.5}/>
      <line x1={ax} y1={ay} x2={bx} y2={by} stroke="#374151" strokeWidth={1.8}/>
      {/* Right angle at C */}
      <path d={`M ${cArcSx},${cArcSy} A ${arcR},${arcR} 0 0,${cSweep} ${cArcEx},${cArcEy}`}
        fill="none" stroke="#374151" strokeWidth={1.1}/>
      <circle cx={cDotX} cy={cDotY} r={2} fill="#374151"/>
      {/* Triangle ABD */}
      <line x1={ax} y1={ay} x2={dx} y2={dy} stroke="#059669" strokeWidth={1.5}/>
      <line x1={bx} y1={by} x2={dx} y2={dy} stroke="#059669" strokeWidth={1.5}/>
      {/* Altitude DH dashed */}
      <line x1={dx} y1={dy} x2={hxC} y2={ay} stroke="#9CA3AF" strokeWidth={1} strokeDasharray="4,3"/>
      {/* DM dashed */}
      <line x1={dx} y1={dy} x2={mx} y2={my} stroke="#DC2626" strokeWidth={1.2} strokeDasharray="4,3"/>
      {/* Right angle at D */}
      <path d={`M ${dArcSx},${dArcSy} A ${arcR},${arcR} 0 0,${dSweep} ${dArcEx},${dArcEy}`}
        fill="none" stroke="#374151" strokeWidth={1.1}/>
      <circle cx={dDotX} cy={dDotY} r={2} fill="#374151"/>
      {/* Labels */}
      <text x={ax-12} y={ay+5} fontSize={12} fill="#374151" fontWeight="600">A</text>
      <text x={bx+4}  y={ay+5} fontSize={12} fill="#374151" fontWeight="600">B</text>
      <text x={cx+4}  y={cy-3} fontSize={12} fill="#374151" fontWeight="600">C</text>
      <text x={dx+4}  y={dy+12} fontSize={12} fill="#374151" fontWeight="600">D</text>
      <text x={mx-4}  y={ay+14} fontSize={11} fill="#374151">M</text>
      <text x={hxC+4} y={ay+14} fontSize={11} fill="#374151">H</text>
      {/* DM label */}
      <text x={(dx+mx)/2+6} y={(dy+my)/2+4} fontSize={11} fill="#DC2626">{fv(dm)} cm</text>
      {/* AB label */}
      <text x={mx} y={ay-6} fontSize={11} fill="#374151" textAnchor="middle">{fv(ab)} cm</text>
    </svg>
  );
};

// ── Congruent triangles crossing: △ABC ≡ △PMT, BC∩MT=O ──────────────────
type CongrTriConfig = { angACB: number; angMOC: number; flipO?: boolean };

const CONGR_TRI_POOL: CongrTriConfig[] = [
  { angACB: 80, angMOC: 70 },
  { angACB: 80, angMOC: 60 },
  { angACB: 70, angMOC: 80 },
  { angACB: 60, angMOC: 80 },
  { angACB: 75, angMOC: 70 },
  { angACB: 65, angMOC: 60 },
  { angACB: 80, angMOC: 50 },
  { angACB: 70, angMOC: 60 },
  { angACB: 80, angMOC: 70,  flipO: true },
  { angACB: 80, angMOC: 60,  flipO: true },
  { angACB: 70, angMOC: 80,  flipO: true },
  { angACB: 60, angMOC: 80,  flipO: true },
  { angACB: 75, angMOC: 70,  flipO: true },
  { angACB: 65, angMOC: 60,  flipO: true },
  { angACB: 80, angMOC: 50,  flipO: true },
  { angACB: 70, angMOC: 60,  flipO: true },
];

function generateCongrTriConfig(): CongrTriConfig {
  return CONGR_TRI_POOL[Math.floor(Math.random() * CONGR_TRI_POOL.length)];
}

const CongrTriDiagram: React.FC<{ config: CongrTriConfig; demo?: boolean }> = ({ config }) => {
  const { angACB, angMOC, flipO = false } = config;
  const angABC = angMOC / 2;
  const angBAC = 180 - angACB - angABC;
  const W = 460, H = 290;
  const toRad = (d: number) => d * Math.PI / 180;

  // Base line: A, M, B, P  left to right
  const baseY = 255;
  const Ax = 40, Mx = 165, Bx = 280, Px = 420;
  const Ay = baseY, My = baseY, By = baseY, Py = baseY;

  // Triangle ABC: A, B on base, C above
  const dACx = Math.cos(toRad(angBAC)), dACy = -Math.sin(toRad(angBAC));
  const dBCx = -Math.cos(toRad(angABC)), dBCy = -Math.sin(toRad(angABC));
  const detABC = dACx * (-dBCy) - dACy * (-dBCx);
  const tABC = ((Bx - Ax) * (-dBCy) - (By - Ay) * (-dBCx)) / detABC;
  const Cx = Ax + tABC * dACx;
  const Cy = Ay + tABC * dACy;

  // Triangle PMT: P, M on base, T above
  const angMPT = angBAC;
  const dPTx = -Math.cos(toRad(angMPT)), dPTy = -Math.sin(toRad(angMPT));
  const dMTx = Math.cos(toRad(angABC)), dMTy = -Math.sin(toRad(angABC));
  const detPMT = dPTx * (-dMTy) - dPTy * (-dMTx);
  const tPMT = ((Mx - Px) * (-dMTy) - (My - Py) * (-dMTx)) / detPMT;
  const Tx = Px + tPMT * dPTx;
  const Ty = Py + tPMT * dPTy;

  // O = intersection of BC and MT
  const bcDx = Cx - Bx, bcDy = Cy - By;
  const mtDx = Tx - Mx, mtDy = Ty - My;
  const denom = bcDx * mtDy - bcDy * mtDx;
  const tBC = ((Mx - Bx) * mtDy - (My - By) * mtDx) / denom;
  const Ox = Bx + tBC * bcDx;
  const Oy = By + tBC * bcDy;

  // Extend BC and MT lines through O by extPx on each end
  const extPx = 18;
  const bcLen = Math.sqrt(bcDx * bcDx + bcDy * bcDy);
  const bcUx = bcDx / bcLen, bcUy = bcDy / bcLen;
  const mtLen = Math.sqrt(mtDx * mtDx + mtDy * mtDy);
  const mtUx = mtDx / mtLen, mtUy = mtDy / mtLen;

  // Arc helpers — sweep toward vertex using cross product
  const arcSweepToward = (u1x: number, u1y: number, u2x: number, u2y: number) =>
    (u1x * u2y - u1y * u2x) > 0 ? 1 : 0;

  // Arc for ∠ACB at C
  const arcCr = 26;
  const CAang = Math.atan2(Ay - Cy, Ax - Cx);
  const CBang = Math.atan2(By - Cy, Bx - Cx);
  const arcCsx = Cx + arcCr * Math.cos(CAang);
  const arcCsy = Cy + arcCr * Math.sin(CAang);
  const arcCex = Cx + arcCr * Math.cos(CBang);
  const arcCey = Cy + arcCr * Math.sin(CBang);
  const sweepC = arcSweepToward(Math.cos(CAang), Math.sin(CAang), Math.cos(CBang), Math.sin(CBang));

  // Arc for ∠MOC (or its vertical ∠BOT) at O
  const arcOr = 26;
  // Normal arms: M→O and C→O; Flipped arms: B→O and T→O (vertical angle)
  const arcO_ang1 = flipO
    ? Math.atan2(By - Oy, Bx - Ox)
    : Math.atan2(My - Oy, Mx - Ox);
  const arcO_ang2 = flipO
    ? Math.atan2(Ty - Oy, Tx - Ox)
    : Math.atan2(Cy - Oy, Cx - Ox);
  const arcOsx = Ox + arcOr * Math.cos(arcO_ang1);
  const arcOsy = Oy + arcOr * Math.sin(arcO_ang1);
  const arcOex = Ox + arcOr * Math.cos(arcO_ang2);
  const arcOey = Oy + arcOr * Math.sin(arcO_ang2);
  const sweepO = arcSweepToward(Math.cos(arcO_ang1), Math.sin(arcO_ang1), Math.cos(arcO_ang2), Math.sin(arcO_ang2));
  // Label at true midpoint of the arc (respects sweep direction)
  const arcO_delta = sweepO === 1
    ? (arcO_ang2 - arcO_ang1 < 0 ? arcO_ang2 - arcO_ang1 + 2 * Math.PI : arcO_ang2 - arcO_ang1)
    : (arcO_ang2 - arcO_ang1 > 0 ? arcO_ang2 - arcO_ang1 - 2 * Math.PI : arcO_ang2 - arcO_ang1);
  const arcO_bisAng = arcO_ang1 + arcO_delta / 2;
  const arcOLblX = Ox + Math.cos(arcO_bisAng) * (arcOr + 14);
  const arcOLblY = Oy + Math.sin(arcO_bisAng) * (arcOr + 14);

  // Arc for ∠BAC at A (answer)
  const arcAr = 30;
  const ABang = Math.atan2(By - Ay, Bx - Ax);
  const ACang2 = Math.atan2(Cy - Ay, Cx - Ax);
  const arcAsx = Ax + arcAr * Math.cos(ABang);
  const arcAsy = Ay + arcAr * Math.sin(ABang);
  const arcAex = Ax + arcAr * Math.cos(ACang2);
  const arcAey = Ay + arcAr * Math.sin(ACang2);
  const sweepA = arcSweepToward(Math.cos(ABang), Math.sin(ABang), Math.cos(ACang2), Math.sin(ACang2));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle ABC */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="#eff6ff" stroke="#1e40af" strokeWidth={1.8} />

      {/* Triangle PMT */}
      <polygon points={`${Px},${Py} ${Mx},${My} ${Tx},${Ty}`}
        fill="#f0fdf4" stroke="#15803d" strokeWidth={1.8} />

      {/* BC extended through O */}
      <line
        x1={Bx - bcUx * extPx} y1={By - bcUy * extPx}
        x2={Cx + bcUx * extPx} y2={Cy + bcUy * extPx}
        stroke="#1e40af" strokeWidth={1.8}
      />
      {/* MT extended through O */}
      <line
        x1={Mx - mtUx * extPx} y1={My - mtUy * extPx}
        x2={Tx + mtUx * extPx} y2={Ty + mtUy * extPx}
        stroke="#15803d" strokeWidth={1.8}
      />

      {/* ∠ACB arc at C */}
      <path d={`M ${arcCsx},${arcCsy} A ${arcCr},${arcCr} 0 0,${sweepC} ${arcCex},${arcCey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text
        x={Cx + Math.cos((CAang + CBang) / 2) * (arcCr + 14)}
        y={Cy + Math.sin((CAang + CBang) / 2) * (arcCr + 14)}
        fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle"
      >{angACB}°</text>

      {/* ∠MOC arc at O */}
      <path d={`M ${arcOsx},${arcOsy} A ${arcOr},${arcOr} 0 0,${sweepO} ${arcOex},${arcOey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text
        x={arcOLblX}
        y={arcOLblY}
        fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle"
      >{angMOC}°</text>

      {/* ∠BAC arc at A (answer) */}
      <path d={`M ${arcAsx},${arcAsy} A ${arcAr},${arcAr} 0 0,${sweepA} ${arcAex},${arcAey}`}
        fill="none" stroke="#dc2626" strokeWidth={1.5} />
      <text
        x={Ax + Math.cos((ABang + ACang2) / 2) * (arcAr + 14)}
        y={Ay + Math.sin((ABang + ACang2) / 2) * (arcAr + 14)}
        fontSize={12} fill="#dc2626" fontWeight="700" textAnchor="middle"
      >{angBAC}°</text>

      {/* O dot — larger and colored */}
      <circle cx={Ox} cy={Oy} r={5} fill="#374151" stroke="#fff" strokeWidth={1.5} />

      {/* Vertex labels */}
      <text x={Ax - 14} y={Ay + 6}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Mx - 4}  y={My + 16} fontSize={13} fill="#374151" fontWeight="600">M</text>
      <text x={Bx - 4}  y={By + 16} fontSize={13} fill="#374151" fontWeight="600">B</text>
      <text x={Px + 5}  y={Py + 6}  fontSize={13} fill="#15803d" fontWeight="700">P</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Tx + 5}  y={Ty - 6}  fontSize={13} fill="#15803d" fontWeight="700">T</text>
      <text x={Ox + 8}  y={Oy - 34}  fontSize={15} fill="#374151" fontWeight="700">O</text>
    </svg>
  );
};

// ── Perp-bisector meets AB: right ∠C, ∠B=30°, perp bisector of AC ⇒ CM=AC ─────
type PerpBisecCMConfig = { angB: number; AC: number };

const PERP_BISEC_POOL: PerpBisecCMConfig[] = [
  { angB: 30, AC: 2 },
  { angB: 30, AC: 4 },
  { angB: 30, AC: 6 },
  { angB: 30, AC: 8 },
];

function generatePerpBisecCMConfig(): PerpBisecCMConfig {
  return PERP_BISEC_POOL[Math.floor(Math.random() * PERP_BISEC_POOL.length)];
}

const PerpBisecCMDiagram: React.FC<{ config: PerpBisecCMConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angB, AC } = config;
  const fv = (v: number | string) => demo ? '？' : String(v);
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 420, H = 290;

  const angA = 90 - angB;
  const AB = AC / Math.sin(toRad(angB));
  const scale = 200 / AB;
  const ABpx = AB * scale;
  const ACpx = AC * scale;

  const Ax = 60, Ay = 250;
  const Bx = Ax + ABpx, By = Ay;
  const Cx = Ax + ACpx * Math.cos(toRad(angA));
  const Cy = Ay - ACpx * Math.sin(toRad(angA));

  // Perpendicular bisector of AC
  const Nx = (Ax + Cx) / 2, Ny = (Ay + Cy) / 2;
  const ACdx = Cx - Ax, ACdy = Cy - Ay;
  const AClen = Math.sqrt(ACdx * ACdx + ACdy * ACdy);
  const perpX = -ACdy / AClen, perpY = ACdx / AClen;
  const t = (Ay - Ny) / perpY;
  const Mx = Nx + t * perpX, My = Ay;

  // Extension of bisector above N
  const extLen = 18;
  const perpExtX = Nx - perpX * extLen, perpExtY = Ny - perpY * extLen;

  // Right-angle arc + dot at C
  const CBdx = Bx - Cx, CBdy = By - Cy;
  const CBlen = Math.sqrt(CBdx * CBdx + CBdy * CBdy);
  const arcRc = 11;
  const CAux = -ACdx / AClen, CAuy = -ACdy / AClen;
  const CBux = CBdx / CBlen, CBuy = CBdy / CBlen;
  const arcCsx = Cx + arcRc * CAux, arcCsy = Cy + arcRc * CAuy;
  const arcCex = Cx + arcRc * CBux, arcCey = Cy + arcRc * CBuy;
  const arcCSweep = (CAux * CBuy - CAuy * CBux) > 0 ? 1 : 0;
  const midCDX = CAux + CBux, midCDY = CAuy + CBuy;
  const midCLen = Math.sqrt(midCDX * midCDX + midCDY * midCDY);
  const dotCx = Cx + (arcRc * 0.65) * midCDX / midCLen;
  const dotCy = Cy + (arcRc * 0.65) * midCDY / midCLen;

  // ∠B arc
  const arcBr = 32;
  const BAang = Math.atan2(Ay - By, Ax - Bx);
  const BCang = Math.atan2(Cy - By, Cx - Bx);
  const arcBsx = Bx + arcBr * Math.cos(BAang), arcBsy = By + arcBr * Math.sin(BAang);
  const arcBex = Bx + arcBr * Math.cos(BCang), arcBey = By + arcBr * Math.sin(BCang);

  // AC label — centered on AC midpoint, offset outward (away from B)
  const acMidX = (Ax + Cx) / 2, acMidY = (Ay + Cy) / 2;
  const acLblX = acMidX - perpX * 26, acLblY = acMidY - perpY * 26;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />
      <line x1={perpExtX} y1={perpExtY} x2={Mx} y2={My}
        stroke="#6b7280" strokeWidth={1.5} strokeDasharray="5,3" />
      <line x1={Cx} y1={Cy} x2={Mx} y2={My}
        stroke="#dc2626" strokeWidth={1.6} strokeDasharray="5,3" />
      <path d={`M ${arcCsx},${arcCsy} A ${arcRc},${arcRc} 0 0,${arcCSweep} ${arcCex},${arcCey}`}
        fill="none" stroke="#374151" strokeWidth={1.4} />
      <circle cx={dotCx} cy={dotCy} r={1.8} fill="#374151" />
      <path d={`M ${arcBsx},${arcBsy} A ${arcBr},${arcBr} 0 0,1 ${arcBex},${arcBey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={Bx - arcBr + 10} y={By + 20} fontSize={12} fill="#374151" fontWeight="600">{angB}°</text>
      <text x={acLblX} y={acLblY - 5} fontSize={11} fill="#374151" textAnchor="middle">s AC</text>
      <text x={acLblX} y={acLblY + 9} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{fv(AC)}</text>
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
      <text x={Mx - 4}  y={My + 16} fontSize={13} fill="#374151" fontWeight="600">M</text>
    </svg>
  );
};

// ── Right-triangle perimeter: ∠ACB=90°, legs given, find perimeter ─────────────
type RightTriPerimConfig = { AC: number; CB: number };

// Only Pythagorean triples — whole-number hypotenuse guaranteed
const RIGHT_TRI_POOL: RightTriPerimConfig[] = [
  { AC:  3, CB:  4 },  // hyp=5,  perim=12
  { AC:  6, CB:  8 },  // hyp=10, perim=24
  { AC:  5, CB: 12 },  // hyp=13, perim=30
  { AC:  8, CB: 15 },  // hyp=17, perim=40
  { AC:  9, CB: 12 },  // hyp=15, perim=36
  { AC: 12, CB: 16 },  // hyp=20, perim=48
  { AC: 10, CB: 24 },  // hyp=26, perim=60
  { AC:  7, CB: 24 },  // hyp=25, perim=56
];

function generateRightTriPerimConfig(): RightTriPerimConfig {
  return RIGHT_TRI_POOL[Math.floor(Math.random() * RIGHT_TRI_POOL.length)];
}

const RightTriPerimDiagram: React.FC<{ config: RightTriPerimConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { AC, CB } = config;
  const hyp = Math.round(Math.sqrt(AC * AC + CB * CB));
  const W = 420, H = 280;
  const fv = (v: number) => demo ? '？' : String(v);

  // A bottom-left, B bottom-right, C top (right angle at C)
  const scale = Math.min(200 / Math.max(AC, CB), 18);
  const acPx = AC * scale;
  const cbPx = CB * scale;

  const Ax = 80, Ay = 240;
  const Bx = Ax + cbPx + acPx * 0.4, By = Ay;

  // C placed using angle at A: tan(A) = CB/AC
  const angA = Math.atan2(CB, AC);
  const Cx = Ax + acPx * Math.cos(angA);
  const Cy = Ay - acPx * Math.sin(angA);

  // Right-angle arc + dot at C
  const CAux = (Ax - Cx) / acPx, CAuy = (Ay - Cy) / acPx;
  const CBdist = Math.sqrt((Bx-Cx)**2+(By-Cy)**2);
  const CBux = (Bx - Cx) / CBdist, CBuy = (By - Cy) / CBdist;
  const arcR = 11;
  const arcStartX = Cx + arcR * CAux, arcStartY = Cy + arcR * CAuy;
  const arcEndX   = Cx + arcR * CBux, arcEndY   = Cy + arcR * CBuy;
  const arcSweep  = (CAux * CBuy - CAuy * CBux) > 0 ? 1 : 0;
  const midDX = CAux + CBux, midDY = CAuy + CBuy;
  const midDLen = Math.sqrt(midDX * midDX + midDY * midDY);
  const dotX = Cx + (arcR * 0.65) * midDX / midDLen;
  const dotY = Cy + (arcR * 0.65) * midDY / midDLen;

  // Label positions
  const acMidX = (Ax + Cx) / 2, acMidY = (Ay + Cy) / 2;
  const cbMidX = (Cx + Bx) / 2, cbMidY = (Cy + By) / 2;
  const abMidX = (Ax + Bx) / 2, abMidY = (Ay + By) / 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle */}
      <polygon
        points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8}
      />

      {/* Right-angle arc + dot at C */}
      <path
        d={`M ${arcStartX},${arcStartY} A ${arcR},${arcR} 0 0,${arcSweep} ${arcEndX},${arcEndY}`}
        fill="none" stroke="#374151" strokeWidth={1.4}
      />
      <circle cx={dotX} cy={dotY} r={1.8} fill="#374151" />

      {/* Side labels */}
      <text x={acMidX - 18} y={(acMidY + Ay) / 2 - 4} fontSize={13} fill="#374151" fontWeight="600" textAnchor="middle">{fv(AC)}</text>
      <text x={cbMidX + 14} y={(cbMidY + Cy) / 2} fontSize={13} fill="#374151" fontWeight="600" textAnchor="middle">{fv(CB)}</text>
      <text x={abMidX} y={abMidY + 16} fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="middle">{fv(hyp)}</text>

      {/* Vertex labels */}
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
    </svg>
  );
};

// ── Exterior angle diagram: ext∠C and ∠A given, find ∠ABC ───────────────────
// Exterior angle theorem: extC = angA + angABC => angABC = extC − angA
// flip=true mirrors the triangle (B on left, A on right)
type ExtAngleConfig = { extC: number; angA: number; flip?: boolean };

const EXT_ANGLE_POOL: ExtAngleConfig[] = [
  { extC: 150, angA: 60 },           // angABC = 90
  { extC: 140, angA: 50 },           // angABC = 90
  { extC: 130, angA: 40 },           // angABC = 90
  { extC: 150, angA: 50 },           // angABC = 100
  { extC: 120, angA: 60 },           // angABC = 60
  { extC: 140, angA: 80 },           // angABC = 60
  { extC: 130, angA: 70 },           // angABC = 60
  { extC: 150, angA: 90 },           // angABC = 60
  { extC: 160, angA: 70 },           // angABC = 90
  { extC: 140, angA: 60 },           // angABC = 80
  { extC: 130, angA: 50 },           // angABC = 80
  // flipped variants (triangle leans the other way)
  { extC: 150, angA: 60, flip: true },
  { extC: 140, angA: 50, flip: true },
  { extC: 120, angA: 60, flip: true },
  { extC: 130, angA: 40, flip: true },
  { extC: 160, angA: 70, flip: true },
  { extC: 150, angA: 80, flip: true },  // angABC = 70
  { extC: 145, angA: 65, flip: true },  // angABC = 80
  { extC: 135, angA: 55 },              // angABC = 80
  { extC: 125, angA: 45 },              // angABC = 80
  { extC: 155, angA: 75 },              // angABC = 80
  { extC: 145, angA: 55, flip: true },  // angABC = 90
  { extC: 135, angA: 75, flip: true },  // angABC = 60
];

function generateExtAngleConfig(): ExtAngleConfig {
  return EXT_ANGLE_POOL[Math.floor(Math.random() * EXT_ANGLE_POOL.length)];
}

const ExtAngleDiagram: React.FC<{ config: ExtAngleConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { extC, angA, flip = false } = config;
  const angABC = extC - angA;
  const W = 420, H = 290;
  const toRad = (d: number) => d * Math.PI / 180;
  const fv = (v: number) => demo ? '？' : String(v);

  // ── 1. Unit geometry (AB = 1 on horizontal baseline) ──
  // When flip=true, mirror everything by placing B on left and A on right
  const dAx = Math.cos(toRad(angA)), dAy = -Math.sin(toRad(angA));
  const dBx = -Math.cos(toRad(angABC)), dBy = -Math.sin(toRad(angABC));
  const det = dAx * (-dBy) - dAy * (-dBx);
  const t = (1 * (-dBy) - 0 * (-dBx)) / det;
  const cx0raw = t * dAx, cy0raw = t * dAy;

  // Mirror x-coordinates if flip
  const mx = (x: number) => flip ? 1 - x : x;
  const cx0 = mx(cx0raw), cy0 = cy0raw;

  const ef = 0.42; // extension length as fraction of AB
  // E: extension of BA beyond A  (A is at mx(0))
  const ex0 = mx(-ef), ey0 = 0;
  // F: extension of CA beyond A
  const acl = Math.sqrt(cx0raw ** 2 + cy0raw ** 2);
  const fx0 = mx(-cx0raw / acl * ef), fy0 = -cy0raw / acl * ef;
  // D: extension of BC beyond C
  const bcl = Math.sqrt((cx0raw - 1) ** 2 + cy0raw ** 2);
  const dx0 = mx(cx0raw + (cx0raw - 1) / bcl * ef), dy0 = cy0raw + cy0raw / bcl * ef;
  // G: extension of AC beyond C
  const gx0 = mx(cx0raw + cx0raw / acl * ef), gy0 = cy0raw + cy0raw / acl * ef;

  // A and B positions (flipped when needed)
  const ax0 = mx(0), ay0 = 0;
  const bx0 = mx(1), by0 = 0;

  // ── 2. Auto-fit to canvas ──
  const pad = 20;
  const iW = W - 2 * pad, iH = H - 2 * pad;
  const xs = [ax0, bx0, cx0, dx0, ex0, fx0, gx0];
  const ys = [ay0, by0, cy0, dy0, ey0, fy0, gy0];
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const sc = Math.min(iW / (xMax - xMin || 1), iH / (yMax - yMin || 1));
  const ox = pad + (iW - (xMax - xMin) * sc) / 2 - xMin * sc;
  const oy = pad + (iH - (yMax - yMin) * sc) / 2 - yMin * sc;
  const px = (x: number) => ox + x * sc;
  const py = (y: number) => oy + y * sc;

  const [Ax, Ay] = [px(ax0), py(ay0)];
  const [Bx, By] = [px(bx0), py(by0)];
  const [Cx, Cy] = [px(cx0),  py(cy0)];
  const [Dx, Dy] = [px(dx0),  py(dy0)];
  const [Ex, Ey] = [px(ex0),  py(ey0)];
  const [Fx, Fy] = [px(fx0),  py(fy0)];
  const [Gx, Gy] = [px(gx0),  py(gy0)];

  // ── 3. Arc helper: always picks the small arc; label along bisector ──
  // Arc radius = 28% of the scaled AB length, so arcs always touch the lines
  const arcR = sc * 0.28;
  const arc = (qx: number, qy: number, r: number, a1: number, a2: number) => {
    const c1 = Math.cos(a1), s1 = Math.sin(a1);
    const c2 = Math.cos(a2), s2 = Math.sin(a2);
    const sweep = (c1 * s2 - s1 * c2) > 0 ? 1 : 0;
    const bAng = Math.atan2(s1 + s2, c1 + c2); // bisector of the two unit vectors
    return {
      d: `M ${qx + r*c1},${qy + r*s1} A ${r},${r} 0 0,${sweep} ${qx + r*c2},${qy + r*s2}`,
      lx: qx + (r + 14) * Math.cos(bAng),
      ly: qy + (r + 14) * Math.sin(bAng),
    };
  };

  // Arc at A: vertical angle (= angA) between the two extensions
  const aA = arc(Ax, Ay, arcR, Math.atan2(Ey - Ay, Ex - Ax), Math.atan2(Fy - Ay, Fx - Ax));
  // Arc at C: exterior angle (= extC) between ray C→A and ray C→D
  const aC = arc(Cx, Cy, arcR, Math.atan2(Ay - Cy, Ax - Cx), Math.atan2(Dy - Cy, Dx - Cx));
  // Arc at B: interior angle (= angABC, the answer)
  const aB = arc(Bx, By, arcR, Math.atan2(Cy - By, Cx - Bx), Math.atan2(Ay - By, Ax - Bx));

  // C vertex label: push outward from centroid
  const cgx = (Ax + Bx + Cx) / 3, cgy = (Ay + By + Cy) / 3;
  const cLa = Math.atan2(Cy - cgy, Cx - cgx);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />

      {/* Extensions at A (solid) */}
      <line x1={Ax} y1={Ay} x2={Ex} y2={Ey} stroke="#374151" strokeWidth={1.6} />
      <line x1={Ax} y1={Ay} x2={Fx} y2={Fy} stroke="#374151" strokeWidth={1.6} />

      {/* Extensions at C (solid) */}
      <line x1={Cx} y1={Cy} x2={Dx} y2={Dy} stroke="#374151" strokeWidth={1.6} />
      <line x1={Cx} y1={Cy} x2={Gx} y2={Gy} stroke="#374151" strokeWidth={1.6} />

      {/* Arc at A: exterior vertical angle = angA */}
      <path d={aA.d} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={aA.lx} y={aA.ly} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{angA}°</text>

      {/* Arc at C: exterior angle = extC */}
      <path d={aC.d} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={aC.lx} y={aC.ly} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{extC}°</text>

      {/* Arc at B: interior angle = angABC (answer) */}
      <path d={aB.d} fill="none" stroke="#dc2626" strokeWidth={1.5} />
      <text x={aB.lx} y={aB.ly} fontSize={13} fill="#dc2626" fontWeight="700" textAnchor="middle">{fv(angABC)}°</text>

      {/* Vertex labels */}
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 7}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 14 * Math.cos(cLa)} y={Cy + 14 * Math.sin(cLa) + 5} fontSize={14} fill="#1e40af" fontWeight="700" textAnchor="middle">C</text>
    </svg>
  );
};

// ── Angle-ratio triangle: ∠ABC=b, ∠BAC:∠ACB = p:q, order sides ──────────────
type AngleRatioConfig = { angB: number; p: number; q: number };

// Each entry satisfies: (p+q) divides (180-angB) exactly
const ANGLE_RATIO_POOL: AngleRatioConfig[] = [
  { angB: 40, p: 3, q: 4 },  // angA=60, angC=80
  { angB: 40, p: 1, q: 3 },  // angA=35, angC=105
  { angB: 40, p: 2, q: 3 },  // angA=56, angC=84
  { angB: 50, p: 2, q: 3 },  // angA=52, angC=78
  { angB: 60, p: 1, q: 2 },  // angA=40, angC=80
  { angB: 60, p: 1, q: 3 },  // angA=30, angC=90
  { angB: 60, p: 2, q: 3 },  // angA=48, angC=72
  { angB: 30, p: 1, q: 2 },  // angA=50, angC=100
  { angB: 30, p: 2, q: 3 },  // angA=60, angC=90
  { angB: 80, p: 2, q: 3 },  // angA=40, angC=60
  { angB: 70, p: 2, q: 3 },  // angA=44, angC=66
  { angB: 20, p: 1, q: 3 },  // angA=40, angC=120
];

function generateAngleRatioConfig(): AngleRatioConfig {
  return ANGLE_RATIO_POOL[Math.floor(Math.random() * ANGLE_RATIO_POOL.length)];
}

function angleRatioOrdering(cfg: AngleRatioConfig) {
  const { angB, p, q } = cfg;
  const unit = (180 - angB) / (p + q);
  const angA = p * unit;  // angle at A → opposite BC
  const angC = q * unit;  // angle at C → opposite AB
  // opposite side: A→BC, B→AC, C→AB
  const sides = [
    { name: 'BC', opp: angA },
    { name: 'AC', opp: angB },
    { name: 'AB', opp: angC },
  ].sort((a, b) => a.opp - b.opp);
  return { angA, angC, sides };
}

const AngleRatioDiagram: React.FC<{ config: AngleRatioConfig }> = ({ config }) => {
  const { angB, p, q } = config;
  const W = 420, H = 290;
  const toRad = (d: number) => d * Math.PI / 180;
  const { angA } = angleRatioOrdering(config);

  // Place A bottom-left, B bottom-right, compute C from A using angA
  const Ax = 55, Ay = 255;
  const Bx = 355, By = 255;

  // Ray from A at angle angA, ray from B at angle angB → find C
  // Easier: place C via ray from A at angle=angA and ray from B at angle=(180-angB)
  // Ray from A: direction = angA above horizontal right
  // Ray from B: direction = angB above horizontal left
  const dAx = Math.cos(toRad(angA)), dAy = -Math.sin(toRad(angA));
  const dBx = -Math.cos(toRad(angB)), dBy = -Math.sin(toRad(angB));
  // Ax + t*dAx = Bx + s*dBx  =>  t*dAx - s*dBx = Bx - Ax
  // Ay + t*dAy = By + s*dBy  =>  t*dAy - s*dBy = By - Ay
  const det = dAx * (-dBy) - dAy * (-dBx);
  const t = ((Bx - Ax) * (-dBy) - (By - Ay) * (-dBx)) / det;
  const Cx = Ax + t * dAx;
  const Cy = Ay + t * dAy;

  // Angle arc at B
  const arcR = 36;
  const arcBEnd = { x: Bx + arcR * Math.cos(toRad(180 - angB)), y: By - arcR * Math.sin(toRad(angB)) };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Triangle */}
      <polygon
        points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8}
      />

      {/* Angle arc at B */}
      <path
        d={`M ${Bx - arcR},${By} A ${arcR},${arcR} 0 0,1 ${arcBEnd.x},${arcBEnd.y}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5}
      />
      <text x={Bx - arcR - 16} y={By - 10} fontSize={12} fill="#374151" fontWeight="600">{angB}°</text>

      {/* Angle arc at A */}
      {(() => {
        const arcAR = 36;
        const arcAEnd = { x: Ax + arcAR * Math.cos(toRad(angA)), y: Ay - arcAR * Math.sin(toRad(angA)) };
        return (
          <>
            <path
              d={`M ${Ax + arcAR},${Ay} A ${arcAR},${arcAR} 0 0,0 ${arcAEnd.x},${arcAEnd.y}`}
              fill="none" stroke="#7c3aed" strokeWidth={1.5}
            />
            <text x={Ax + arcAR + 4} y={Ay - 8} fontSize={12} fill="#374151" fontStyle="italic">{p}x</text>
          </>
        );
      })()}

      {/* Angle arc at C */}
      {(() => {
        const arcCR = 36;
        // C's angle is angC = 180 - angA - angB
        // Directions from C: toward A and toward B
        const CAx = Ax - Cx, CAy = Ay - Cy;
        const CAang = Math.atan2(CAy, CAx);
        const CBx2 = Bx - Cx, CBy2 = By - Cy;
        const CBang = Math.atan2(CBy2, CBx2);
        const arcCSx = Cx + arcCR * Math.cos(CAang);
        const arcCSy = Cy + arcCR * Math.sin(CAang);
        const arcCEx = Cx + arcCR * Math.cos(CBang);
        const arcCEy = Cy + arcCR * Math.sin(CBang);
        const midAng = (CAang + CBang) / 2;
        const dotX = Cx + (arcCR + 14) * Math.cos(midAng);
        const dotY = Cy + (arcCR + 14) * Math.sin(midAng);
        return (
          <>
            <path
              d={`M ${arcCSx},${arcCSy} A ${arcCR},${arcCR} 0 0,0 ${arcCEx},${arcCEy}`}
              fill="none" stroke="#7c3aed" strokeWidth={1.5}
            />
            <text x={dotX} y={dotY} fontSize={12} fill="#374151" fontStyle="italic" textAnchor="middle">{q}x</text>
          </>
        );
      })()}

      {/* Vertex labels */}
      <text x={Ax - 14} y={Ay + 6} fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6} fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 9} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
    </svg>
  );
};

// ── Parallel lines x-angle: a∥b, find x = angLeft − angBottom ──────────────
// angLeft shown at upper-left pocket of transversal on b (obtuse)
// angBottom shown inside the notch at line a
// x = angLeft − angBottom  (exterior angle of the formed triangle)
type ParallelXConfig = { angLeft: number; angBottom: number };
// x = (180 − angLeft) + angBottom  (exterior angle of the formed triangle)
// i.e. the arm angle at b equals the sum of the two non-adjacent interior angles
const PARALLEL_X_DEDUPED: ParallelXConfig[] = [
  { angLeft: 114, angBottom: 21 },  // x = 66+21 = 87
  { angLeft: 120, angBottom: 30 },  // x = 60+30 = 90
  { angLeft: 130, angBottom: 25 },  // x = 50+25 = 75
  { angLeft: 110, angBottom: 35 },  // x = 70+35 = 105
  { angLeft: 125, angBottom: 20 },  // x = 55+20 = 75
  { angLeft: 115, angBottom: 20 },  // x = 65+20 = 85
  { angLeft: 130, angBottom: 15 },  // x = 50+15 = 65
  { angLeft: 120, angBottom: 15 },  // x = 60+15 = 75
  { angLeft: 110, angBottom: 20 },  // x = 70+20 = 90
  { angLeft: 140, angBottom: 25 },  // x = 40+25 = 65
  { angLeft: 135, angBottom: 30 },  // x = 45+30 = 75
  { angLeft: 128, angBottom: 22 },  // x = 52+22 = 74
];

function generateParallelXConfig(): ParallelXConfig {
  const pool = PARALLEL_X_DEDUPED;
  return pool[Math.floor(Math.random() * pool.length)];
}

// ── Bottom cross: two parallel lines, V-shaped transversal, find ε given β and γ ──
// Geometry: apex between lines → ε = (180 − β) + γ  (= α + γ where α = supplement of β)
interface BottomCrossConfig {
  beta: number;   // obtuse angle at upper intersection (left side)
  gamma: number;  // acute angle at lower intersection (right side)
  epsilon: number;
}

function generateBottomCrossConfig(): BottomCrossConfig {
  const betaOptions  = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150];
  const gammaOptions = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65];
  const beta  = betaOptions[Math.floor(Math.random() * betaOptions.length)];
  const gamma = gammaOptions[Math.floor(Math.random() * gammaOptions.length)];
  const epsilon = (180 - beta) + gamma;
  return { beta, gamma, epsilon };
}

export const ParallelXDiagram: React.FC<{ config: ParallelXConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { angLeft, angBottom } = config;
  const x = (180 - angLeft) + angBottom;  // exterior angle theorem on the formed triangle
  const W = 420, H = 260;
  const fv = (v: number) => demo ? '？' : String(v);
  const toRad = (d: number) => d * Math.PI / 180;

  // Line b: y=60, from x=30 to x=390
  // Line a: y=210, from x=30 to x=390
  const bY = 65, aY = 205;

  // Transversal hits line b at Tx=160, line a at Ax=220
  const Tbx = 160, Tby = bY;
  const Tax = 220, Tay = aY;

  // Direction of transversal (pointing up-left from a to b)
  const tdx = Tbx - Tax, tdy = Tby - Tay;
  const tLen = Math.sqrt(tdx * tdx + tdy * tdy);
  const tuX = tdx / tLen, tuY = tdy / tLen;  // unit vec from a toward b

  // The right arm from Tb: makes angle x with transversal toward right
  // transversal direction angle from horizontal = atan2(-tdy, tdx)
  const transAng = Math.atan2(-tdy, tdx) * 180 / Math.PI;  // angle above horizontal going right
  // x arm goes to the right at angle (transAng - x) from horizontal
  const xArmAng = transAng - x;
  const xArmLen = 170;
  const xArmEx = Tbx + xArmLen * Math.cos(toRad(xArmAng));
  const xArmEy = Tby - xArmLen * Math.sin(toRad(xArmAng));

  // Extend transversal below line b (upward past b) for the left side
  const extLen = 60;
  const extTbx = Tbx - tuX * extLen;
  const extTby = Tby - tuY * extLen;

  // Arc for angLeft at Tb (between left-of-b and transversal, on left side)
  const arcR = 44;
  // angLeft is the obtuse angle to the LEFT of the transversal on line b
  // left direction of b = 180°, transversal goes down-right from Tb = atan2(tdy, tdx)
  const transDown = Math.atan2(tdy, tdx);  // pointing from b-intersection downward toward a
  const leftDir   = Math.PI;               // ← along line b
  // arc sweeps from leftDir to transDown (clockwise = positive y direction)
  const arcLsx = Tbx + arcR * Math.cos(leftDir);
  const arcLsy = Tby + arcR * Math.sin(leftDir);
  const arcLex = Tbx + arcR * Math.cos(transDown);
  const arcLey = Tby + arcR * Math.sin(transDown);

  // Arc for angBottom at Tax on line a (interior notch: between transversal-up and right-of-a)
  const arcB = 34;
  const transUp = Math.atan2(-tdy, -tdx);  // pointing from a upward toward b
  const rightDir = 0;                       // → along line a
  const arcBsx = Tax + arcB * Math.cos(transUp);
  const arcBsy = Tay + arcB * Math.sin(transUp);
  const arcBex = Tax + arcB * Math.cos(rightDir);
  const arcBey = Tay + arcB * Math.sin(rightDir);

  // Arc for x at Tb between transversal-down and x-arm
  const arcX = 30;
  const arcXsx = Tbx + arcX * Math.cos(transDown);
  const arcXsy = Tby + arcX * Math.sin(transDown);
  const xArmRad = toRad(xArmAng);
  const arcXex = Tbx + arcX * Math.cos(-xArmRad);
  const arcXey = Tby + arcX * Math.sin(-xArmRad);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Line b */}
      <line x1={30} y1={bY} x2={390} y2={bY} stroke="#1e40af" strokeWidth={2} />
      <text x={32} y={bY - 8} fontSize={13} fill="#1e40af" fontWeight="700">b</text>

      {/* Line a */}
      <line x1={30} y1={aY} x2={390} y2={aY} stroke="#1e40af" strokeWidth={2} />
      <text x={32} y={aY + 16} fontSize={13} fill="#1e40af" fontWeight="700">a</text>

      {/* Transversal: from below a up to above b */}
      <line
        x1={Tax + (Tax - Tbx) * 0.18} y1={Tay + (Tay - Tby) * 0.18}
        x2={extTbx} y2={extTby}
        stroke="#374151" strokeWidth={1.8}
      />

      {/* x arm from Tb going right */}
      <line x1={Tbx} y1={Tby} x2={xArmEx} y2={xArmEy} stroke="#374151" strokeWidth={1.8} />

      {/* angLeft arc */}
      <path
        d={`M ${arcLsx},${arcLsy} A ${arcR},${arcR} 0 0,1 ${arcLex},${arcLey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5}
      />
      <text x={Tbx - arcR - 18} y={Tby + 16} fontSize={12} fill="#374151" fontWeight="600">{angLeft}°</text>

      {/* angBottom arc */}
      <path
        d={`M ${arcBsx},${arcBsy} A ${arcB},${arcB} 0 0,0 ${arcBex},${arcBey}`}
        fill="none" stroke="#7c3aed" strokeWidth={1.5}
      />
      <text x={Tax + 8} y={Tay + 16} fontSize={12} fill="#374151" fontWeight="600">{angBottom}°</text>

      {/* x arc */}
      <path
        d={`M ${arcXsx},${arcXsy} A ${arcX},${arcX} 0 0,0 ${arcXex},${arcXey}`}
        fill="none" stroke="#dc2626" strokeWidth={1.5}
      />
      <text
        x={Tbx + arcX + 4}
        y={Tby + arcX * 0.5 + 4}
        fontSize={13} fill="#dc2626" fontWeight="700"
      >{demo ? '？' : `${fv(x)}°`}</text>
    </svg>
  );
};

// ── Linear system: x+y=a, x-y=b, find x·y ─────────────────────────────
type LinearSystemConfig = { a: number; b: number; x: number; y: number; xy: number; opts: number[]; correctIdx: number };
const LINEAR_SYSTEM_POOL: LinearSystemConfig[] = [
  { a:10, b:4,  x:7,  y:3, xy:21, opts:[18,21,24,28], correctIdx:1 },
  { a:12, b:6,  x:9,  y:3, xy:27, opts:[24,27,30,36], correctIdx:1 },
  { a:14, b:4,  x:9,  y:5, xy:45, opts:[40,42,45,50], correctIdx:2 },
  { a:8,  b:2,  x:5,  y:3, xy:15, opts:[12,15,18,20], correctIdx:1 },
  { a:16, b:6,  x:11, y:5, xy:55, opts:[50,54,55,60], correctIdx:2 },
  { a:18, b:4,  x:11, y:7, xy:77, opts:[70,72,77,88], correctIdx:2 },
];
function generateLinearSystemConfig(): LinearSystemConfig {
  return LINEAR_SYSTEM_POOL[Math.floor(Math.random() * LINEAR_SYSTEM_POOL.length)];
}

// ── Cube flower-pot (volume) diagram ────────────────────────────────────
type CubePotConfig = {
  perim: number;    // base perimeter in dm  (= 4 × side)
  side: number;     // side length in dm
  fracNum: number;
  fracDen: number;
  answer: number;   // liters of soil
};

const CUBE_POT_POOL: CubePotConfig[] = [
  { perim:  8, side: 2, fracNum: 1, fracDen: 2, answer:  4 },
  { perim:  8, side: 2, fracNum: 3, fracDen: 4, answer:  6 },
  { perim: 12, side: 3, fracNum: 1, fracDen: 3, answer:  9 },
  { perim: 12, side: 3, fracNum: 2, fracDen: 3, answer: 18 },
  { perim: 16, side: 4, fracNum: 1, fracDen: 4, answer: 16 },
  { perim: 16, side: 4, fracNum: 1, fracDen: 2, answer: 32 },
];

function generateCubePotConfig(): CubePotConfig {
  return CUBE_POT_POOL[Math.floor(Math.random() * CUBE_POT_POOL.length)];
}

const CubePotDiagram: React.FC<{ config: CubePotConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { perim, fracNum, fracDen } = config;
  const W = 380, H = 270;
  const fv = (v: number) => demo ? '？' : String(v);

  // Isometric 3-face cube
  const cx = 185, cy = 138;
  const fw = 130, fh = 110;   // front face width & height
  const dx = 52,  dy = 28;    // depth projection offset

  // Front face corners
  const flbx = cx - fw / 2, flby = cy + fh / 2;
  const frbx = cx + fw / 2, frby = cy + fh / 2;
  const frtx = cx + fw / 2, frty = cy - fh / 2;
  const fltx = cx - fw / 2, flty = cy - fh / 2;

  // Depth-offset corners
  const brtx = frtx + dx, brty = frty - dy;
  const brbx = frbx + dx, brby = frby - dy;
  const bltx = fltx + dx, blty = flty - dy;

  // Soil fill level on the front face
  const fillFrac = fracNum / fracDen;
  const soilTopY = flby - fillFrac * fh;

  // Left side annotation
  const annX    = fltx - 22;
  const annMidY = (flty + flby) / 2;

  // Bottom perimeter annotation
  const annY = flby + 18;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <defs>
        <clipPath id="cubeFrontClip">
          <polygon points={`${flbx},${flby} ${frbx},${frby} ${frtx},${frty} ${fltx},${flty}`} />
        </clipPath>
      </defs>

      {/* Right face */}
      <polygon
        points={`${frtx},${frty} ${brtx},${brty} ${brbx},${brby} ${frbx},${frby}`}
        fill="#a87550" stroke="#6b3f1f" strokeWidth={1.5}
      />
      {/* Top face */}
      <polygon
        points={`${fltx},${flty} ${bltx},${blty} ${brtx},${brty} ${frtx},${frty}`}
        fill="#d9a96a" stroke="#6b3f1f" strokeWidth={1.5}
      />
      {/* Front face */}
      <polygon
        points={`${flbx},${flby} ${frbx},${frby} ${frtx},${frty} ${fltx},${flty}`}
        fill="#c48a50" stroke="#6b3f1f" strokeWidth={1.5}
      />
      {/* Soil fill overlay clipped to front face */}
      <rect
        x={flbx} y={soilTopY} width={fw} height={flby - soilTopY}
        fill="rgba(90,55,20,0.42)" clipPath="url(#cubeFrontClip)"
      />
      {/* Soil surface dashed line */}
      <line
        x1={flbx} y1={soilTopY} x2={frbx} y2={soilTopY}
        stroke="#3d1f00" strokeWidth={1.5} strokeDasharray="5,3"
      />
      {/* Fraction label above soil line */}
      <text x={cx} y={soilTopY - 5} fontSize={11} textAnchor="middle" fill="#3d1f00" fontWeight="600">
        {fracNum}/{fracDen}
      </text>

      {/* Left side dimension annotation */}
      <line x1={annX} y1={flty} x2={annX} y2={flby} stroke="#374151" strokeWidth={1.2} />
      <line x1={annX - 4} y1={flty} x2={annX + 4} y2={flty} stroke="#374151" strokeWidth={1.2} />
      <line x1={annX - 4} y1={flby} x2={annX + 4} y2={flby} stroke="#374151" strokeWidth={1.2} />
      <text x={annX - 11} y={annMidY + 4} fontSize={13} fill="#374151" textAnchor="middle" fontStyle="italic">a</text>

      {/* Bottom perimeter annotation */}
      <line x1={flbx} y1={annY} x2={frbx} y2={annY} stroke="#374151" strokeWidth={1.2} />
      <line x1={flbx} y1={annY - 4} x2={flbx} y2={annY + 4} stroke="#374151" strokeWidth={1.2} />
      <line x1={frbx} y1={annY - 4} x2={frbx} y2={annY + 4} stroke="#374151" strokeWidth={1.2} />
      <text x={(flbx + frbx) / 2} y={annY + 14} fontSize={12} fill="#374151" textAnchor="middle">
        4a = {fv(perim)} dm
      </text>
    </svg>
  );
};

// ── External angle bisector AL ∥ BC diagram ────────────────────────────
type ExtBisectorConfig = { BC: number; AB: number };

function generateExtBisectorConfig(): ExtBisectorConfig {
  // BC even so (P − BC)/2 = AB is always a whole number
  const bcOpts = [4, 6, 8, 10];
  const abOpts = [6, 7, 8, 9, 10, 11, 12];
  const BC = bcOpts[Math.floor(Math.random() * bcOpts.length)];
  const AB = abOpts[Math.floor(Math.random() * abOpts.length)];
  return { BC, AB };
}

const ExtBisectorDiagram: React.FC<{ config: ExtBisectorConfig; demo?: boolean }> = ({ config, demo = false }) => {
  const { BC } = config;
  const W = 400, H = 270;
  const toRad = (d: number) => d * Math.PI / 180;
  const toDeg = (r: number) => r * 180 / Math.PI;

  // Fixed shape: △ABC isosceles AC=AB, angle at A = 40°
  const aA = 40;
  const Ax = 120, Ay = 240;
  const Bx = Ax + 210, By = 240;
  const Cx = Ax + 210 * Math.cos(toRad(aA));
  const Cy = Ay  - 210 * Math.sin(toRad(aA));

  // AL direction = BC direction (parallel)
  const dBCx = Cx - Bx, dBCy = Cy - By;
  const dBClen = Math.sqrt(dBCx * dBCx + dBCy * dBCy);
  const nBCx = dBCx / dBClen, nBCy = dBCy / dBClen;
  const Lx = Ax + nBCx * 85, Ly = Ay + nBCy * 85;

  // Arc at A: clockwise from ext-BA (180°) to ray-AC (360°−aA)
  const AR = 22;
  const arcS = 180, arcE = 360 - aA; // 180° → 320° CW = 140° span, AL at 250°
  const arcSx = Ax + AR * Math.cos(toRad(arcS));
  const arcSy = Ay + AR * Math.sin(toRad(arcS));
  const arcEx = Ax + AR * Math.cos(toRad(arcE));
  const arcEy = Ay + AR * Math.sin(toRad(arcE));
  const arcPath = `M ${arcSx.toFixed(1)} ${arcSy.toFixed(1)} A ${AR} ${AR} 0 0 1 ${arcEx.toFixed(1)} ${arcEy.toFixed(1)}`;

  // Two small tick marks at midpoints of each arc half to show bisection
  const tickR = AR + 5, tkHalf = 5;
  const mkTick = (angleDeg: number) => {
    const cr = toRad(angleDeg);
    const cx = Ax + tickR * Math.cos(cr), cy = Ay + tickR * Math.sin(cr);
    const px = -Math.sin(cr), py = Math.cos(cr);
    return `M ${(cx - px * tkHalf).toFixed(1)} ${(cy - py * tkHalf).toFixed(1)} L ${(cx + px * tkHalf).toFixed(1)} ${(cy + py * tkHalf).toFixed(1)}`;
  };

  const BCmidX = (Bx + Cx) / 2, BCmidY = (By + Cy) / 2;
  const BCangle = toDeg(Math.atan2(Cy - By, Cx - Bx)); // ~−100°
  const labelOffX = 14 * Math.cos(toRad(BCangle + 90));
  const labelOffY = 14 * Math.sin(toRad(BCangle + 90));
  const LLabelX = Lx - nBCx * 24 + nBCy * 12;
  const LLabelY = Ly - nBCy * 24 - nBCx * 12;
  const f = (v: number) => demo ? '?' : `${v}`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', margin: '0 auto' }}>
      {/* Extended base line left of A */}
      <line x1={Ax - 55} y1={Ay} x2={Bx} y2={By} stroke="#1e3a5f" strokeWidth={1.5} />
      {/* BC */}
      <line x1={Bx} y1={By} x2={Cx} y2={Cy} stroke="#1e3a5f" strokeWidth={2} />
      {/* AC */}
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#1e3a5f" strokeWidth={2} />
      {/* Ray AL (blue) */}
      <line x1={Ax} y1={Ay} x2={Lx} y2={Ly} stroke="#2563eb" strokeWidth={2} />
      {/* Arrowhead at L */}
      <polygon
        points={`${Lx.toFixed(1)},${Ly.toFixed(1)} ${(Lx - nBCx * 10 + nBCy * 4).toFixed(1)},${(Ly - nBCy * 10 - nBCx * 4).toFixed(1)} ${(Lx - nBCx * 10 - nBCy * 4).toFixed(1)},${(Ly - nBCy * 10 + nBCx * 4).toFixed(1)}`}
        fill="#2563eb"
      />
      {/* Arc at A */}
      <path d={arcPath} fill="none" stroke="#374151" strokeWidth={1.4} />
      {/* Bisector tick marks */}
      <path d={mkTick(215)} stroke="#374151" strokeWidth={1.4} fill="none" />
      <path d={mkTick(285)} stroke="#374151" strokeWidth={1.4} fill="none" />
      {/* BC length label */}
      <text
        x={(BCmidX + labelOffX).toFixed(1)}
        y={(BCmidY + labelOffY).toFixed(1)}
        fontSize={13} fill="#e11d48" textAnchor="middle" dominantBaseline="middle"
      >{f(BC)}</text>
      {/* Vertex labels */}
      <text x={Ax - 10} y={Ay + 16} fontSize={14} fontWeight="bold" fill="#1e3a5f" textAnchor="middle">A</text>
      <text x={Bx + 12} y={By + 6}  fontSize={14} fontWeight="bold" fill="#1e3a5f">B</text>
      <text x={Cx + 8}  y={Cy + 4}  fontSize={14} fontWeight="bold" fill="#1e3a5f">C</text>
      <text x={LLabelX.toFixed(1)} y={LLabelY.toFixed(1)} fontSize={14} fontWeight="bold" fill="#2563eb" textAnchor="middle" dominantBaseline="middle">L</text>
    </svg>
  );
};

const PlaygroundPage: React.FC = () => {
  const [mathInput, setMathInput] = useState('Въведи текст с формули тук. Например: $a^2 + b^2 = c^2$');
  const [demoMode, setDemoMode] = useState(false);

  // Generated once per page load – shared between both renderers
  const [pieSlices] = useState<PieSlice[]>(() => generatePieSlices());
  const [triConfig] = useState<TriangleConfig>(() => generateTriangleConfig());
  const [parallelConfig] = useState<ParallelLinesConfig>(() => generateParallelLinesConfig());
  const [extBisConfig] = useState<ExtBisectorConfig>(() => generateExtBisectorConfig());
  const [circumConfig]  = useState<CircumcenterConfig>(() => generateCircumcenterConfig());
  const [cubePotConfig]  = useState<CubePotConfig>(() => generateCubePotConfig());
  const [eqTriPerpConfig]  = useState<EqTriPerpConfig>(() => generateEqTriPerpConfig());
  const [isoscChainConfig]  = useState<IsoscChainConfig>(() => generateIsoscChainConfig());
  const [angleRatioConfig]    = useState<AngleRatioConfig>(() => generateAngleRatioConfig());
  const [extAngleConfig]       = useState<ExtAngleConfig>(() => generateExtAngleConfig());
  const [rightTriPerimConfig]  = useState<RightTriPerimConfig>(() => generateRightTriPerimConfig());
  const [perpBisecCMConfig]    = useState<PerpBisecCMConfig>(() => generatePerpBisecCMConfig());
  const [congrTriConfig]       = useState<CongrTriConfig>(() => generateCongrTriConfig());
  const [rhombusCOMConfig]     = useState<RhombusCOMConfig>(() => generateRhombusCOMConfig());
  const [barChartCleaningConfig] = useState<BarChartCleaningConfig>(() => generateBarChartCleaningConfig());
  const [coordGridConfig]        = useState<CoordGridConfig>(() => generateCoordGridConfig());
  const [clubRatioConfig]        = useState<ClubRatioConfig>(() => generateClubRatioConfig());
  const [angleBisecODConfig]     = useState<AngleBisecODConfig>(() => generateAngleBisecODConfig());
  const [intersectLinesConfig]   = useState<IntersectLinesConfig>(() => generateIntersectLinesConfig());
  const [extAngBConfig]          = useState<ExtAngBConfig>(() => generateExtAngBConfig());
  const [isoscAltConfig]         = useState<IsoscAltConfig>(() => generateIsoscAltConfig());
  const [perpBisecBCConfig]      = useState<PerpBisecBCConfig>(() => generatePerpBisecBCConfig());
  const [parallelDLConfig]       = useState<ParallelDLConfig>(() => generateParallelDLConfig());
  const [boxVolumeConfig]        = useState<BoxVolumeConfig>(() => generateBoxVolumeConfig());
  const [parallelogramABCDConfig] = useState<ParallelogramABCDConfig>(() => ({
    angBAD: 45, ratioDAC: 1, ratioBAC: 3,
    m: 2 + Math.floor(Math.random() * 8),
    n: 2 + Math.floor(Math.random() * 8),
  }));
  const [seasonSurveyConfig]     = useState<SeasonSurveyConfig>(() => generateSeasonSurveyConfig());
  const [rightTriABConfig]       = useState<RightTriABConfig>(() => generateRightTriABConfig());
  const [_parallelXConfig]     = useState<ParallelXConfig>(() => generateParallelXConfig());
  const [bottomCrossPlane] = useState<'left' | 'right'>(() => (Math.random() < 0.5 ? 'left' : 'right'));
  const [bottomCrossConfig] = useState<BottomCrossConfig>(() => generateBottomCrossConfig());
  const [linearSystemConfig]   = useState<LinearSystemConfig>(() => generateLinearSystemConfig());
  const [linearSystemConfig35] = useState<LinearSystemConfig>(() => generateLinearSystemConfig());
  const [task34Answer, setTask34Answer] = useState('');
  const [task34Checking, setTask34Checking] = useState(false);
  const [task34Feedback, setTask34Feedback] = useState<{ correct: boolean; message: string } | null>(null);
  const [task34ShowCameraQr, setTask34ShowCameraQr] = useState(false);
  const [taskUploadChannelId] = useState<string>(() => getOrCreateTaskUploadChannelId());
  const [task34PhoneGrade, setTask34PhoneGrade] = useState<TaskGradeResult | null>(null);
  const [task34LastUploadUrl, setTask34LastUploadUrl] = useState<string | null>(null);
  const [task35Answer, setTask35Answer] = useState('');
  const [task35Checking, setTask35Checking] = useState(false);
  const [task35Feedback, setTask35Feedback] = useState<{ correct: boolean; message: string } | null>(null);
  const [task35ShowCameraQr, setTask35ShowCameraQr] = useState(false);
  const [task35PhoneGrade, setTask35PhoneGrade] = useState<TaskGradeResult | null>(null);
  const [task35LastUploadUrl, setTask35LastUploadUrl] = useState<string | null>(null);
  const [task34LanHost, setTask34LanHost] = useState<string>(() => {
    const saved = localStorage.getItem('task34_lan_host') || '';
    if (saved.trim()) return saved.trim();
    return isLocalHostName(window.location.hostname) ? '' : window.location.hostname;
  });
  const [task34LanPort, setTask34LanPort] = useState<string>(() => {
    const saved = localStorage.getItem('task34_lan_port') || '';
    if (saved.trim()) return saved.trim();
    return '5173';
  });
  const [pts] = useState<{ A: Point; B: Point; C: Point }>(() => generateDistinctPoints());
  const [symConfig] = useState<SymConfig>(() => generateSymConfig());

  const jsxContainerRef = useRef<HTMLDivElement>(null);
  const symJsxContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const jsxBoardRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const symJsxBoardRef = useRef<any>(null);

  const seedTaskUploadContexts = async () => {
    const payloads = [
      {
        channel_id: taskUploadChannelId,
        problem_number: 34,
        a: linearSystemConfig.a,
        b: linearSystemConfig.b,
        correct_xy: String(linearSystemConfig.xy),
      },
      {
        channel_id: taskUploadChannelId,
        problem_number: 35,
        a: linearSystemConfig35.a,
        b: linearSystemConfig35.b,
        correct_xy: String(linearSystemConfig35.xy),
      },
    ];

    for (const payload of payloads) {
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
          await setTaskContext(payload);
          break;
        } catch {
          if (attempt < 3) await wait(350);
        }
      }
    }
  };

  useEffect(() => {
    const stop = watchMobileChannel(taskUploadChannelId, {
      onUpload: (upload) => {
        if (upload.problem_number === 34) setTask34LastUploadUrl(upload.file_url);
        else if (upload.problem_number === 35) setTask35LastUploadUrl(upload.file_url);
      },
      onGrade: (grade) => {
        if (grade.problem_number === 34) {
          if (grade.file_url) setTask34LastUploadUrl(grade.file_url);
          setTask34PhoneGrade(grade);
          setTask34Feedback({
            correct: grade.is_correct,
            message: `${grade.feedback}\n\nОценка: ${grade.score}/100 (от телефон).`,
          });
          return;
        }

        if (grade.problem_number === 35) {
          if (grade.file_url) setTask35LastUploadUrl(grade.file_url);
          setTask35PhoneGrade(grade);
          setTask35Feedback({
            correct: grade.is_correct,
            message: `${grade.feedback}\n\nОценка: ${grade.score}/100 (от телефон).`,
          });
        }
      },
    });

    return stop;
  }, [taskUploadChannelId]);

  useEffect(() => {
    let disposed = false;

    // Clear backend upload history on mount so stale uploads from a previous
    // session don't reappear after a page refresh.
    clearChannelHistory(taskUploadChannelId).catch(() => {});

    const syncLatestUploads = async () => {
      try {
        const latest = await getLatestMobileUploads(taskUploadChannelId, 30);
        if (disposed) return;

        const latest34 = latest.find((item) => item.problem_number === 34);
        const latest35 = latest.find((item) => item.problem_number === 35);

        if (latest34?.file_url) setTask34LastUploadUrl(latest34.file_url);
        if (latest35?.file_url) setTask35LastUploadUrl(latest35.file_url);
      } catch {
        // Keep silent: SSE remains the primary path, this is just a resilience fallback.
      }
    };

    syncLatestUploads();
    const intervalId = window.setInterval(syncLatestUploads, 2000);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, [taskUploadChannelId]);


  useEffect(() => {
    if (!task34LanHost.trim()) return;
    localStorage.setItem('task34_lan_host', task34LanHost.trim());
  }, [task34LanHost]);

  useEffect(() => {
    if (!task34LanPort.trim()) return;
    localStorage.setItem('task34_lan_port', task34LanPort.trim());
  }, [task34LanPort]);

  // ── JSXGraph ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const CSS_ID = 'jsxgraph-css';
    if (!document.getElementById(CSS_ID)) {
      const link = document.createElement('link');
      link.id = CSS_ID;
      link.rel = 'stylesheet';
      link.href = 'https://jsxgraph.uni-bayreuth.de/distrib/jsxgraph.css';
      document.head.appendChild(link);
    }

    function initBoard() {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const JXG = (window as any).JXG;
      if (!JXG || !jsxContainerRef.current) return;

      if (jsxBoardRef.current) {
        JXG.JSXGraph.freeBoard(jsxBoardRef.current);
        jsxBoardRef.current = null;
      }

      const board = JXG.JSXGraph.initBoard('jsx-board', {
        boundingbox: [-5, 5, 5, -5],
        axis: true,
        showCopyright: false,
        showNavigation: true,
        grid: true,
      });

      const labelStyle = { fontSize: 14, fontWeight: 'bold', offset: [8, 8] };
      board.create('point', pts.A, { name: 'A', size: 5, fillColor: '#e11d48', strokeColor: '#be123c', label: labelStyle });
      board.create('point', pts.B, { name: 'B', size: 5, fillColor: '#2563eb', strokeColor: '#1d4ed8', label: labelStyle });
      board.create('point', pts.C, { name: 'C', size: 5, fillColor: '#16a34a', strokeColor: '#15803d', label: labelStyle });

      jsxBoardRef.current = board;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((window as any).JXG) {
      initBoard();
    } else {
      const SCRIPT_ID = 'jsxgraph-script';
      let script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
      if (!script) {
        script = document.createElement('script');
        script.id = SCRIPT_ID;
        script.src = 'https://jsxgraph.uni-bayreuth.de/distrib/jsxgraphcore.js';
        document.head.appendChild(script);
      }
      script.addEventListener('load', initBoard, { once: true });
    }

    return () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const JXG = (window as any).JXG;
      if (jsxBoardRef.current && JXG) {
        JXG.JSXGraph.freeBoard(jsxBoardRef.current);
        jsxBoardRef.current = null;
      }
    };
  }, [pts]);

  // ── Symmetry JSXGraph ──────────────────────────────────────────────────────
  useEffect(() => {
    function initSymBoard() {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const JXG = (window as any).JXG;
      if (!JXG || !symJsxContainerRef.current) return;

      if (symJsxBoardRef.current) {
        JXG.JSXGraph.freeBoard(symJsxBoardRef.current);
        symJsxBoardRef.current = null;
      }

      const board = JXG.JSXGraph.initBoard('jsx-sym-board', {
        boundingbox: [-5, 5, 5, -5],
        axis: true,
        showCopyright: false,
        showNavigation: true,
        grid: true,
      });

      const { A, B, C, sourceLabel, axis } = symConfig;
      const src = sourceLabel === 'A' ? A : B;
      const labelStyle = { fontSize: 14, fontWeight: 'bold', offset: [8, 8] };

      board.create('point', [A[0], A[1]], { name: 'A', size: 5, fillColor: '#e11d48', strokeColor: '#be123c', label: labelStyle });
      board.create('point', [B[0], B[1]], { name: 'B', size: 5, fillColor: '#2563eb', strokeColor: '#1d4ed8', label: labelStyle });
      board.create('point', [C[0], C[1]], {
        name: 'C', size: 5, fillColor: 'white', strokeColor: '#16a34a', strokeWidth: 2,
        label: { ...labelStyle, color: '#16a34a' },
      });

      // Dashed perpendicular from source → foot on axis → C
      const foot: Point = axis === 'Ox' ? [src[0], 0] : [0, src[1]];
      board.create('segment', [[src[0], src[1]], [foot[0], foot[1]]], { strokeColor: '#a855f7', strokeWidth: 1.5, dash: 3 });
      board.create('segment', [[foot[0], foot[1]], [C[0], C[1]]], { strokeColor: '#a855f7', strokeWidth: 1.5, dash: 3 });
      board.create('point', [foot[0], foot[1]], { name: '', size: 3, fillColor: '#a855f7', strokeColor: '#a855f7', fixed: true });

      symJsxBoardRef.current = board;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((window as any).JXG) {
      initSymBoard();
    } else {
      const SCRIPT_ID = 'jsxgraph-script';
      const script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
      if (script) script.addEventListener('load', initSymBoard, { once: true });
    }

    return () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const JXG = (window as any).JXG;
      if (symJsxBoardRef.current && JXG) {
        JXG.JSXGraph.freeBoard(symJsxBoardRef.current);
        symJsxBoardRef.current = null;
      }
    };
  }, [symConfig]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-violet-50">
      <AppNavbar backTo="/nvo/practice" backLabel="Към НВО тренировка" />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <section className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-black text-gray-900 dark:text-slate-100">🧪 Playground</h1>
            <p className="text-xs text-gray-400">Обнови страницата за нови случайни стойности</p>
          </div>
          <button
            onClick={() => setDemoMode(d => !d)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold transition-colors ${
              demoMode
                ? 'bg-amber-100 border-amber-300 text-amber-800'
                : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <span>{demoMode ? '🎭' : '📖'}</span>
            {demoMode ? 'Демо режим' : 'Нормален режим'}
          </button>
        </section>

        {demoMode && (
          <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-sm text-amber-800">
            <span className="text-lg">🎭</span>
            <span>Демо режим – всички случайни стойности са заменени с <span className="inline-block bg-amber-200 text-amber-900 rounded px-1 font-mono font-bold text-xs">？</span> – стойностите се сменят при всяко обновяване на страницата.</span>
          </div>
        )}

        {/* Coordinate sections – side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Coordinate system – A, B, C */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-base">📐</span>
              <h2 className="text-sm font-bold text-gray-900">Координатна система – A, B, C</h2>
            </div>
            <div className="flex flex-wrap gap-3 text-sm font-mono">
              {demoMode ? (
                <>
                  <span className="text-rose-400 font-semibold">A(<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>,{'\u00A0'}<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>)</span>
                  <span className="text-blue-400 font-semibold">B(<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>,{'\u00A0'}<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>)</span>
                  <span className="text-green-400 font-semibold">C(<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>,{'\u00A0'}<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>)</span>
                </>
              ) : (
                <>
                  <span className="text-rose-600 font-semibold">A({pts.A[0]},{'\u00A0'}{pts.A[1]})</span>
                  <span className="text-blue-600 font-semibold">B({pts.B[0]},{'\u00A0'}{pts.B[1]})</span>
                  <span className="text-green-600 font-semibold">C({pts.C[0]},{'\u00A0'}{pts.C[1]})</span>
                </>
              )}
            </div>
          </div>
          <div id="jsx-board" ref={jsxContainerRef} style={{ width: '100%', height: '430px' }} />
        </section>

        {/* Symmetry coordinate section */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-base">🪞</span>
              <h2 className="text-sm font-bold text-gray-900">Симетрия спрямо ос</h2>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              {demoMode ? (
                <>
                  <span className="font-mono text-rose-400 font-semibold">A(<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>,{'\u00A0'}<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>)</span>
                  <span className="font-mono text-blue-400 font-semibold">B(<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>,{'\u00A0'}<span className="bg-amber-100 text-amber-700 rounded px-0.5">？</span>)</span>
                  <span className="text-xs text-gray-400">
                    C е симетрично на <span className="bg-amber-100 text-amber-700 rounded px-1 font-mono font-bold text-xs">？</span> спрямо <span className="bg-amber-100 text-amber-700 rounded px-1 font-mono font-bold text-xs">？</span>
                  </span>
                </>
              ) : (
                <>
                  <span className="font-mono text-rose-600 font-semibold">A({symConfig.A[0]},{'\u00A0'}{symConfig.A[1]})</span>
                  <span className="font-mono text-blue-600 font-semibold">B({symConfig.B[0]},{'\u00A0'}{symConfig.B[1]})</span>
                  <span className="text-xs text-gray-500">
                    C е симетрично на <strong className="text-violet-700">{symConfig.sourceLabel}</strong> спрямо <strong className="text-violet-700">{symConfig.axis}</strong>
                  </span>
                </>
              )}
            </div>
          </div>
          <div id="jsx-sym-board" ref={symJsxContainerRef} style={{ width: '100%', height: '430px' }} />
        </section>

        </div>

        {/* Parallel Lines with Transversals */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2 flex-wrap">
            <span className="text-xl">📏</span>
            <h2 className="text-base font-bold text-gray-900">Успоредни прави <em>a</em> ∥ <em>b</em></h2>
            <span className="text-xs text-gray-400 ml-1">намери γ</span>
            <span className="ml-auto flex items-center gap-3 text-sm font-mono flex-wrap justify-end">
              <span className="text-blue-700">α = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${parallelConfig.alphaFlavor === 'acute' ? parallelConfig.angle1 : 180 - parallelConfig.angle1}°`}</span>
              <span className="text-violet-700">β = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${(parallelConfig.betaFlavor === 'upper' || parallelConfig.betaFlavor === 'lower') ? parallelConfig.angle1 + parallelConfig.angle2 : 180 - parallelConfig.angle1 - parallelConfig.angle2}°`}</span>
              <span className="text-gray-400">│</span>
              <span className="text-red-600">γ = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${parallelConfig.gammaFlavor === 'acute' ? parallelConfig.angle2 : 180 - parallelConfig.angle2}°`}</span>
            </span>
          </div>
          <div className="p-6">
            <ParallelLinesDiagram config={parallelConfig} />
          </div>
        </section>

        {/* Isosceles Triangle Diagram */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2 flex-wrap">
            <span className="text-xl">📐</span>
            <h2 className="text-base font-bold text-gray-900">Равнобедрен триъгълник ABC (AC = BC)</h2>
            <span className="text-xs text-gray-400 ml-1">
              симетрала на {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1 font-mono font-bold text-xs">？</span> : triConfig.bisectorSide} пресича противоположното бедро в F
            </span>
            <span className="ml-auto flex items-center gap-3 text-sm font-mono flex-wrap justify-end">
              <span className="font-bold text-indigo-700">α = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${triConfig.angleC}°`}</span>
              <span className="text-gray-400">│</span>
              <span className="text-violet-700">∠A = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${90 - (triConfig.bisectorSide === 'AC' ? 3 : 1) * triConfig.angleC / 2}°`}</span>
              <span className="text-violet-700">∠B = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${90 - (triConfig.bisectorSide === 'AC' ? 1 : 3) * triConfig.angleC / 2}°`}</span>
              <span className="text-violet-700">∠F = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : `${2 * triConfig.angleC}°`}</span>
            </span>
          </div>
          <div className="p-6">
            <IsoscelesTriangleDiagram config={triConfig} demo={demoMode} />
          </div>
        </section>

        {/* Pie Chart */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <span className="text-xl">🥧</span>
            <h2 className="text-base font-bold text-gray-900">Кръгова диаграма</h2>
            <span className="text-xs text-gray-400 ml-1">
              {demoMode ? <><span className="bg-amber-100 text-amber-700 rounded px-1 font-mono font-bold text-xs">？</span> части</> : `${pieSlices.length} части`} · едната е 90° · едната е <strong>x</strong> · обнови за нови стойности
            </span>
          </div>
          <PieChartSection slices={pieSlices} demo={demoMode} />
        </section>

        {/* Math Notation Sandbox */}
        {/* External Angle Bisector */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2 flex-wrap">
            <span className="text-xl">📐</span>
            <h2 className="text-base font-bold text-gray-900">Лъчът AL е ъглополовяща на външния ъгъл при A, AL ∥ BC</h2>
            <span className="ml-auto flex items-center gap-3 text-sm font-mono flex-wrap justify-end">
              <span className="text-red-600">BC = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？</span> : `${extBisConfig.BC}`} cm</span>
              <span className="text-gray-700">Периметър = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？</span> : `${2 * extBisConfig.AB + extBisConfig.BC}`} cm</span>
              <span className="text-gray-400">│</span>
              <span className="text-green-700 font-bold">AB = {demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？</span> : `${extBisConfig.AB}`} cm</span>
            </span>
          </div>
          <div className="p-6">
            <ExtBisectorDiagram config={extBisConfig} demo={demoMode} />
          </div>
        </section>

        {/* Circumcenter / perpendicular bisectors */}
        {(() => {
          const { angOBA, angOCA } = circumConfig;
          const angBOC = 2 * (angOBA + angOCA);
          const f = (v: number) => demoMode ? <span className="bg-amber-100 text-amber-700 rounded px-1">？°</span> : <>{v}°</>;
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2 flex-wrap">
                <span className="text-xl">🔵</span>
                <h2 className="text-base font-bold text-gray-900">Симетрали на AB и AC се пресичат в O</h2>
                <span className="ml-auto flex items-center gap-3 text-sm font-mono flex-wrap justify-end">
                  <span className="text-indigo-700">∠OCA = {f(angOCA)}</span>
                  <span className="text-indigo-700">∠OBA = {f(angOBA)}</span>
                  <span className="text-gray-400">│</span>
                  <span className="text-green-700 font-bold">∠BOC = {f(angBOC)}</span>
                </span>
              </div>
              <div className="p-6">
                <CircumcenterDiagram config={circumConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Cube flower-pot volume ── */}
        {(() => {
          const { perim, side, fracNum, fracDen, answer } = cubePotConfig;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🪴</span>
                <h2 className="text-base font-bold text-gray-900">Задача 13 — Обем на куб (цветарник)</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>Обиколка на основата: <span className="font-bold text-blue-700">{fv(perim)} dm</span></span>
                <span>│</span>
                <span>Страна: <span className="font-bold text-blue-700">{fv(side)} dm</span></span>
                <span>│</span>
                <span>Запълване: <span className="font-bold">{fracNum}/{fracDen}</span> от обема</span>
                <span>│</span>
                <span>Почва: <span className="font-bold text-green-700">{fv(answer)} L</span></span>
              </div>
              <div className="p-6">
                <CubePotDiagram config={cubePotConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Equilateral triangle – PM ⊥ AC ── */}
        {(() => {
          const { AP, MB } = eqTriPerpConfig;
          const AB = 2 * AP + MB;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 14 — Равностранен триъгълник, перпендикуляр от страна</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>AP = <span className="font-bold text-blue-700">{fv(AP)} cm</span></span>
                <span>│</span>
                <span>MB = <span className="font-bold text-blue-700">{fv(MB)} cm</span></span>
                <span>│</span>
                <span>AB = <span className="font-bold text-green-700">{fv(AB)} cm</span></span>
              </div>
              <div className="p-6">
                <EqTriPerpDiagram config={eqTriPerpConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Isosceles chain: AC = CF = BF ── */}
        {(() => {
          const { k } = isoscChainConfig;
          const angACB = 180 - 3 * k;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔺</span>
                <h2 className="text-base font-bold text-gray-900">Задача 15 — AC = CF = BF, намери ∠ACB</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>∠A = (x + {k})°</span>
                <span>│</span>
                <span>∠FBC = x°</span>
                <span>│</span>
                <span>x = <span className="font-bold text-blue-700">{fv(k)}°</span></span>
                <span>│</span>
                <span>∠ACB = <span className="font-bold text-green-700">{fv(angACB)}°</span></span>
              </div>
              <div className="p-6">
                <IsoscChainDiagram config={isoscChainConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Angle-ratio triangle: order sides ── */}
        {(() => {
          const { angB, p, q } = angleRatioConfig;
          const { angA, angC, sides } = angleRatioOrdering(angleRatioConfig);
          const fv = (v: number) => demoMode ? '？' : String(v);
          const ordering = sides.map(s => s.name).join(' < ');
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 16 — Неравенство на страните (ъгъл ↔ страна)</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>∠ABC = <span className="font-bold">{angB}°</span></span>
                <span>│</span>
                <span>∠BAC : ∠ACB = {p} : {q}</span>
                <span>│</span>
                <span>∠A = <span className="font-bold text-blue-700">{fv(angA)}°</span></span>
                <span>│</span>
                <span>∠C = <span className="font-bold text-blue-700">{fv(angC)}°</span></span>
                <span>│</span>
                <span>Неравенство: <span className="font-bold text-green-700">{demoMode ? '？ < ？ < ？' : ordering}</span></span>
              </div>
              <div className="p-6">
                <AngleRatioDiagram config={angleRatioConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── Exterior angle triangle ── */}
        {(() => {
          const { extC, angA } = extAngleConfig;
          const angABC = extC - angA;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔺</span>
                <h2 className="text-base font-bold text-gray-900">Задача 17 — Външен ъгъл на триъгълник, намери ∠ABC</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>Външен ъгъл C = <span className="font-bold">{extC}°</span></span>
                <span>│</span>
                <span>∠A = <span className="font-bold">{angA}°</span></span>
                <span>│</span>
                <span>∠ABC = <span className="font-bold text-green-700">{fv(angABC)}°</span></span>
              </div>
              <div className="p-6">
                <ExtAngleDiagram config={extAngleConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Right triangle perimeter ── */}
        {(() => {
          const { AC, CB } = rightTriPerimConfig;
          const hyp = Math.round(Math.sqrt(AC * AC + CB * CB));
          const perim = AC + CB + hyp;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 18 — Правоъгълен триъгълник, периметър</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>AC = <span className="font-bold">{fv(AC)} cm</span></span>
                <span>│</span>
                <span>CB = <span className="font-bold">{fv(CB)} cm</span></span>
                <span>│</span>
                <span>AB = <span className="font-bold text-red-600">{fv(hyp)} cm</span></span>
                <span>│</span>
                <span>Периметър = <span className="font-bold text-green-700">{fv(perim)} cm</span></span>
              </div>
              <div className="p-6">
                <RightTriPerimDiagram config={rightTriPerimConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Perp bisector of AC meets AB at M, find CM ── */}
        {(() => {
          const { angB, AC } = perpBisecCMConfig;
          const CM = AC;  // always = AC when ∠B=30°
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 19 — Симетрала на AC пресича AB в M, намери CM</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>∠ACB = 90°</span>
                <span>│</span>
                <span>∠ABC = <span className="font-bold">{angB}°</span></span>
                <span>│</span>
                <span>AC = <span className="font-bold">{fv(AC)} cm</span></span>
                <span>│</span>
                <span>CM = <span className="font-bold text-green-700">{fv(CM)} cm</span></span>
              </div>
              <div className="p-6">
                <PerpBisecCMDiagram config={perpBisecCMConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Congruent triangles: △ABC ≡ △PMT, BC∩MT=O, find ∠BAC ── */}
        {(() => {
          const { angACB, angMOC } = congrTriConfig;
          const angABC = angMOC / 2;
          const angBAC = 180 - angACB - angABC;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 20 — Съвпадающи △ABC ≡ △PMT, BC∩MT = O</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>∠ACB = <span className="font-bold">{angACB}°</span></span>
                <span>│</span>
                <span>∠MOC = <span className="font-bold">{angMOC}°</span></span>
                <span>│</span>
                <span>∠ABC = <span className="font-bold text-blue-700">{fv(angABC)}°</span></span>
                <span>│</span>
                <span>∠BAC = <span className="font-bold text-green-700">{fv(angBAC)}°</span></span>
              </div>
              <div className="p-6">
                <CongrTriDiagram config={congrTriConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── Rhombus ABCD: ∠COM ── */}
        {(() => {
          const { angADB } = rhombusCOMConfig;
          const angCOM = 90 - angADB;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔷</span>
                <h2 className="text-base font-bold text-gray-900">Задача 21 — Ромб ABCD, O=център, M=средата на BC</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm">
                <span>∠ADB = <span className="font-bold">{angADB}°</span></span>
                <span>│</span>
                <span>∠DAB = <span className="font-bold">{180 - 2 * angADB}°</span></span>
                <span>│</span>
                <span>∠COM = <span className="font-bold text-green-700">{fv(angCOM)}°</span></span>
              </div>
              <div className="p-6">
                <RhombusCOMDiagram config={rhombusCOMConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Bar chart: operators cleaning floor ── */}
        {(() => {
          const { t1, t2 } = barChartCleaningConfig;
          const ansA = t1 * t2 / (4 * (t1 + t2));
          const ansB = 2 * t1 * t2 / (2 * t2 + 3 * t1);
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📊</span>
                <h2 className="text-base font-bold text-gray-900">Задача 22 — Двама оператори почистват пода</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm leading-relaxed text-gray-700">
                <p>На диаграмата е представено времето (в минути), за което всеки оператор сам почиства пода.</p>
                <p className="mt-1"><strong>А)</strong> За колко минути двамата заедно ще почистят <strong>25%</strong> от пода? → <span className="font-bold text-green-700">{fv(ansA)} мин</span></p>
                <p className="mt-1"><strong>Б)</strong> За колко минути двамата заедно ще почистят целия под, ако вторият оператор намали с <strong>1/3</strong> времето си? → <span className="font-bold text-green-700">{fv(ansB)} мин</span></p>
              </div>
              <div className="p-6">
                <BarChartCleaningDiagram config={barChartCleaningConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── Coordinate grid: M, N, P ── */}
        {(() => {
          const { Mx, My, Nx, Ny, Px, Py } = coordGridConfig;
          const area = Math.abs(Mx * (Ny - Py) + Nx * (Py - My) + Px * (My - Ny)) / 2;
          const Qx = -Nx, Qy = -Ny;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🗓️</span>
                <h2 className="text-base font-bold text-gray-900">Задача 23 — Координатна система, точки M, N и P</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                <span>А) M(<span className="font-bold">{fv(Mx)}</span>; <span className="font-bold">{fv(My)}</span>), N(<span className="font-bold">{fv(Nx)}</span>; <span className="font-bold">{fv(Ny)}</span>), P(<span className="font-bold">{fv(Px)}</span>; <span className="font-bold">{fv(Py)}</span>)</span>
                <span>Б) Q(<span className="font-bold text-blue-700">{fv(Qx)}</span>; <span className="font-bold text-blue-700">{fv(Qy)}</span>) — симетрична на N спрямо O</span>
                <span>В) S(△MNP) = <span className="font-bold text-green-700">{fv(area)} cm²</span></span>
              </div>
              <div className="p-6">
                <CoordGridDiagram config={coordGridConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── Club ratio bar chart ── */}
        {(() => {
          const { data, answerYear, answerLabel } = clubRatioConfig;
          const fv = (v: string) => demoMode ? '？' : v;
          const options = [
            { label: 'А', year: data[0].year },
            { label: 'Б', year: data[1].year },
            { label: 'В', year: data[2].year },
            { label: 'Г', year: data[3].year },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📊</span>
                <h2 className="text-base font-bold text-gray-900">Задача 24 — отношение Умник / Атлет</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700">Определете годината, в която отношението Клуб „Умник“ : Клуб „Атлет“ е най-голямо.</p>
                <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
                  {options.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.year === answerYear
                          ? 'text-green-700'
                          : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {o.year}{!demoMode && o.year === answerYear ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-xs text-gray-500">Отговор: <span className="font-bold text-green-700">{fv(answerLabel + ') ' + String(answerYear))}</span></p>
              </div>
              <div className="p-6">
                <ClubRatioDiagram config={clubRatioConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── O on line AC, OD bisects ∠BOC, find ∠AOB ── */}
        {(() => {
          const { angBOD } = angleBisecODConfig;
          const angBOC = 2 * angBOD;
          const angAOB = 180 - angBOC;
          const fv = (v: number) => demoMode ? '？' : `${v}°`;
          const opts = [
            { label: 'А', val: angBOC },
            { label: 'Б', val: 180 - angBOD },
            { label: 'В', val: angBOD },
            { label: 'Г', val: angAOB },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📏</span>
                <h2 className="text-base font-bold text-gray-900">Задача 25 — O лежи на AC, OD е ъглополовяща на ∠BOC, намерете ∠AOB</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">Дадено: ∠BOD = <strong>{angBOD}°</strong>. Търсете мярката на ∠AOB:</p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === angAOB ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === angAOB ? '？' : `${o.val}°`}{!demoMode && o.val === angAOB ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-xs text-gray-500">∠AOB = <span className="font-bold text-green-700">{fv(angAOB)}</span></p>
              </div>
              <div className="p-6">
                <AngleBisecODDiagram config={angleBisecODConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Intersecting lines a and b: find smaller angle ── */}
        {(() => {
          const { k1, k2 } = intersectLinesConfig;
          const x = (180 - k1 - k2) / 3;
          const ang1 = 2 * x + k1;
          const ang2 = x + k2;
          const smaller = Math.min(ang1, ang2);
          const fv = (v: number) => demoMode ? '？' : `${v}°`;
          const opts = [
            { label: 'А', val: 180 - ang2 },
            { label: 'Б', val: ang2 > ang1 ? ang2 : ang1 },
            { label: 'В', val: smaller },
            { label: 'Г', val: x },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">✕</span>
                <h2 className="text-base font-bold text-gray-900">Задача 26 — Прави a и b се пресичат, намерете по-малкия ъгъл</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">Углите: <strong>2x+{k1}°</strong> и <strong>x+{k2}°</strong> са суплементарни → x = <span className="font-bold text-blue-700">{fv(x)}</span></p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === smaller ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === smaller ? '？' : `${o.val}°`}{!demoMode && o.val === smaller ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
              </div>
              <div className="p-6">
                <IntersectLinesDiagram config={intersectLinesConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Exterior angle at B of △ABC ── */}
        {(() => {
          const { angA, angC } = extAngBConfig;
          const angB = 180 - angA - angC;
          const extB = angA + angC;
          const fv = (v: number) => demoMode ? '？' : `${v}°`;
          const opts = [
            { label: 'А', val: angB },
            { label: 'Б', val: 180 - angA },
            { label: 'В', val: angC },
            { label: 'Г', val: extB },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 27 — Външен ъгъл при върха B на △ABC</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">∠A = <strong>{angA}°</strong>, ∠C = <strong>{angC}°</strong> → ∠B = {angB}°, външен ъгъл = <span className="font-bold text-green-700">{fv(extB)}</span></p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === extB ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === extB ? '？' : `${o.val}°`}{!demoMode && o.val === extB ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
              </div>
              <div className="p-6">
                <ExtAngBDiagram config={extAngBConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Isosceles △ABC, altitude CH, find BC ── */}
        {(() => {
          const { AH, ratioP, ratioQ } = isoscAltConfig;
          const HC = AH * ratioQ / ratioP;
          const BC = Math.round(Math.sqrt(AH * AH + HC * HC));
          const fv = (v: number) => demoMode ? '？' : `${v} cm`;
          const opts = [
            { label: 'А', val: AH },
            { label: 'Б', val: HC },
            { label: 'В', val: BC },
            { label: 'Г', val: AH + HC },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 28 — Равнобедрен △ABC (AC=BC), височина CH, намерете BC</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">
                  AH = <strong>{AH} cm</strong>, AH:HC = <strong>{ratioP}:{ratioQ}</strong> → HC = {HC} cm, HB = AH = {AH} cm
                </p>
                <p className="text-gray-700 mb-1">BC = √({AH}² + {HC}²) = <span className="font-bold text-green-700">{fv(BC)}</span></p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === BC ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === BC ? '？' : `${o.val} cm`}{!demoMode && o.val === BC ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
              </div>
              <div className="p-6">
                <IsoscAltDiagram config={isoscAltConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Task 29: random triangle only ── */}
        {(() => {
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 29 — Намерете CM</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-0">На страната CB е построена симетралата s_CB, която пресича AB в M и CB в D.</p>
                <p className="text-gray-700 mt-1">Ако ∠ABC = 30°, намерете дължината на CM.</p>
              </div>
              <div className="p-6">
                <PerpBisecBCDiagram config={perpBisecBCConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Parallelogram ABCD: DL bisects ∠D, find ∠DAB ── */}
        {(() => {
          const { angALD } = parallelDLConfig;
          const angDAB = 180 - 2 * angALD;
          const fv = (v: number) => demoMode ? '？' : `${v}°`;
          const opts = [
            { label: 'А', val: angDAB },
            { label: 'Б', val: angDAB + 10 },
            { label: 'В', val: angALD },
            { label: 'Г', val: 180 - angDAB },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔷</span>
                <h2 className="text-base font-bold text-gray-900">Задача 30 — Успоредник ABCD, DL е ъглополовяща на ∠D, намерете ∠DAB</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">∠ALD = <strong>{angALD}°</strong>. В △ADL: ∠DAB + (180−∠DAB)/2 + {angALD}° = 180° ⇒ ∠DAB = <span className="font-bold text-green-700">{fv(angDAB)}</span></p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === angDAB ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === angDAB ? '？' : `${o.val}°`}{!demoMode && o.val === angDAB ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
              </div>
              <div className="p-6">
                <ParallelDLDiagram config={parallelDLConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Box volume with unit conversion ── */}
        {(() => {
          const { dmValues, labels, vol } = boxVolumeConfig;
          const [dm1, dm2, dm3] = dmValues;
          const [label1, label2, label3] = labels;
          const fv = (v: number) => demoMode ? '？' : String(v);
          const opts = [
            { label: 'А', val: vol / 10 },
            { label: 'Б', val: vol },
            { label: 'В', val: vol * 10 },
            { label: 'Г', val: vol * 100 },
          ];
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📦</span>
                <h2 className="text-base font-bold text-gray-900">Задача 31 — Обем на правоъгълен паралелепипед в dm³</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">
                  Измерения: <strong>{label1.text}</strong>, <strong>{label2.text}</strong>, <strong>{label3.text}</strong>
                </p>
                <p className="text-gray-700 mb-1">
                  В dm: {label1.text} = <strong>{dm1} dm</strong>, {label2.text} = <strong>{dm2} dm</strong>, {label3.text} = <strong>{dm3} dm</strong>
                </p>
                <p className="text-gray-700 mb-1">
                  V = {dm1} × {dm2} × {dm3} = <span className="font-bold text-green-700">{fv(vol)} dm³</span>
                </p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {opts.map(o => (
                    <span key={o.label}
                      className={`font-semibold ${
                        !demoMode && o.val === vol ? 'text-green-700' : 'text-gray-700'
                      }`}
                    >
                      {o.label}) {demoMode && o.val === vol ? '？' : o.val}{!demoMode && o.val === vol ? ' ✓' : ''}
                    </span>
                  ))}
                </div>
              </div>
              <div className="p-6">
                <BoxVolumeDiagram config={boxVolumeConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Season Survey: 200 people, 4 seasons, find k ── */}
        {(() => {
          const { k, essen, addExtra, peNum, peDen, lyaNum, lyaDen, percent } = seasonSurveyConfig;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📊</span>
                <h2 className="text-base font-bold text-gray-900">Задача 32 — Сезони (200 анкетирани)</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm">
                <p className="text-gray-700 mb-1">
                  Зима = <em>k</em>; Пролет = <em>4k</em>; Лято = <em>5k</em>; Есен = {essen}. Общо = 200.
                </p>
                <p className="text-gray-700 mb-1">
                  А) k = <strong className="text-green-700">{fv(k)}</strong>
                </p>
                <p className="text-gray-700 mb-1">
                  Б) Пролет : Есен = <strong className="text-green-700">{demoMode ? '？/？' : `${peNum}/${peDen}`}</strong>{'  '}
                  Лято : Зима = <strong className="text-green-700">{demoMode ? '？/？' : `${lyaNum}/${lyaDen}`}</strong>
                </p>
                <p className="text-gray-700">
                  В) +{addExtra} анкетирани → <strong className="text-green-700">{fv(percent)}%</strong> увеличение
                </p>
              </div>
              <div className="p-6">
                <SeasonSurveyDiagram config={seasonSurveyConfig} />
              </div>
            </section>
          );
        })()}

        {/* ── Right triangles △ABC and △ABD sharing hypotenuse AB ── */}
        {(() => {
          const { dm, ab, areaABC, areaABD } = rightTriABConfig;
          const fv = (v: number) => demoMode ? '？' : String(v);
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">📐</span>
                <h2 className="text-base font-bold text-gray-900">Задача 33 — △ABC и △ABD с обща хипотенуза AB</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm space-y-1">
                <p className="text-gray-700">
                  C — на симетралата на AB; ∠BAD:∠ABD = 1:5; DM = {dm} cm (M е средата на AB)
                </p>
                <p className="text-gray-700">
                  А) DM = AB/2 ⇒ AB = 2×{dm} = <strong className="text-green-700">{fv(ab)} cm</strong>
                </p>
                <p className="text-gray-700">
                  Б) △ABC — равностранно правоъгълно (AC=BC, ∠ACB=90°) ⇒ S = AB²/4 = <strong className="text-green-700">{fv(areaABC)} cm²</strong>
                </p>
                <p className="text-gray-700">
                  В) ∠BAD + ∠ABD = 90°, разпределение 1:5 ⇒ <strong className="text-green-700">{demoMode ? '？' : '15°'}</strong>
                </p>
                <p className="text-gray-700">
                  Г) DH = AB/4; S△ABD = ½×AB×DH = AB²/8 = <strong className="text-green-700">{fv(areaABD)} cm²</strong>
                </p>
              </div>
              <div className="p-6">
                <RightTriABDiagram config={rightTriABConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* ── Linear system ── */}
        {(() => {
          const { a, b, x, y, xy, opts } = linearSystemConfig;
          const labels = ['А', 'Б', 'В', 'Г'];
          const currentHostIsLocal = isLocalHostName(window.location.hostname);
          const resolvedHost = currentHostIsLocal ? task34LanHost.trim() : window.location.hostname;
          const resolvedPort = task34LanPort.trim() || window.location.port || '5173';
          const qrOrigin = resolvedHost ? `${window.location.protocol}//${resolvedHost}:${resolvedPort}` : window.location.origin;
          const mobilePairUrl = `${qrOrigin}/mobile-capture?channel=${encodeURIComponent(taskUploadChannelId)}`;
          const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(mobilePairUrl)}`;
          const handleCheck = async () => {
            if (!task34Answer.trim()) return;
            setTask34Checking(true);
            setTask34Feedback(null);
            try {
              const prompt = `Задача: системата $x + y = ${a}$, $x - y = ${b}$. Намери $x \\cdot y$.

Отговор на ученика: "${task34Answer.trim()}"
Правилен отговор: $x = ${x}$, $y = ${y}$, $x \\cdot y = ${xy}$

Без поздрав. Само кратко обяснение: ако отговорът е верен — потвърди с едно изречение. Ако е сгрешен — обясни грешката и покажи решението стъпка по стъпка с LaTeX ($...$ за inline). Отговаряй само на български.`;
              const reply = await sendChatMessage([{ role: 'user', content: prompt }]);
              const isCorrect = new RegExp(`\\b${xy}\\b`).test(task34Answer.trim());
              setTask34Feedback({ correct: isCorrect, message: reply });
            } catch {
              setTask34Feedback({ correct: false, message: 'Грешка при проверката. Моля, опитай пак.' });
            } finally {
              setTask34Checking(false);
            }
          };
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔢</span>
                <h2 className="text-base font-bold text-gray-900">Задача 34 — Система линейни уравнения</h2>
              </div>
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-100">
                <p className="text-sm text-gray-700 mb-3">Дадена е системата. Намерете стойността на <strong>x · y</strong>:</p>
                <div className="inline-flex flex-col gap-1 bg-white border border-gray-200 rounded-xl px-6 py-4 text-lg font-mono shadow-sm">
                  <span>x + y = <strong>{a}</strong></span>
                  <span>x − y = <strong>{b}</strong></span>
                </div>
                {/* MCQ shortcuts */}
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-xs text-gray-400 self-center">Бърз избор:</span>
                  {opts.map((opt, i) => (
                    <button key={i}
                      onClick={() => { setTask34Answer(String(opt)); setTask34Feedback(null); }}
                      className="px-3 py-1 rounded-lg border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-violet-50 hover:border-violet-300"
                    >
                      {labels[i]}) {opt}
                    </button>
                  ))}
                </div>
                {/* Free-form answer input */}
                <div className="mt-4 flex gap-2 items-center">
                  <input
                    type="text"
                    value={task34Answer}
                    onChange={e => { setTask34Answer(e.target.value); setTask34Feedback(null); }}
                    onKeyDown={e => e.key === 'Enter' && handleCheck()}
                    placeholder="Напр. '21' или 'x=7, y=3, x·y=21'"
                    className="flex-1 rounded-xl border border-gray-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                  />
                  <button
                    onClick={handleCheck}
                    disabled={task34Checking || !task34Answer.trim()}
                    className="px-4 py-2 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {task34Checking ? 'Проверявам...' : 'Провери'}
                  </button>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      const next = !task34ShowCameraQr;
                      setTask34ShowCameraQr(next);
                      if (next) {
                        void seedTaskUploadContexts();
                      }
                    }}
                    className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
                  >
                    {task34ShowCameraQr ? 'Hide Camera QR' : 'Upload From Camera'}
                  </button>
                  <span className="text-xs text-gray-500">Scan on phone, submit answer there, AI grades and syncs here.</span>
                </div>

                {task34ShowCameraQr && (
                  <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                    <p className="text-sm font-semibold text-emerald-800">Phone Pairing for Task 34</p>
                    <p className="text-xs text-emerald-700 mt-1">Channel: <span className="font-mono">{taskUploadChannelId}</span></p>
                    {currentHostIsLocal && (
                      <div className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2">
                        <p className="text-xs text-amber-800 mb-1">Desktop is on localhost. Enter LAN IP for phone QR:</p>
                        <input
                          type="text"
                          value={task34LanHost}
                          onChange={(e) => setTask34LanHost(e.target.value)}
                          placeholder="192.168.1.10"
                          className="w-full rounded-md border border-amber-300 px-2 py-1 text-xs"
                        />
                        <p className="text-xs text-amber-800 mt-2 mb-1">Frontend port (usually 5173):</p>
                        <input
                          type="text"
                          value={task34LanPort}
                          onChange={(e) => setTask34LanPort(e.target.value)}
                          placeholder="5173"
                          className="w-full rounded-md border border-amber-300 px-2 py-1 text-xs"
                        />
                      </div>
                    )}
                    {!currentHostIsLocal && window.location.port !== task34LanPort.trim() && (
                      <p className="text-xs text-amber-700 mt-2">QR uses port {task34LanPort.trim()} (current page port is {window.location.port || 'default'}).</p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-4">
                      <img src={qrUrl} alt="Task 34 phone QR" className="h-40 w-40 rounded-lg border border-emerald-200 bg-white p-1" />
                      <div className="min-w-0 flex-1">
                        <a href={mobilePairUrl} target="_blank" rel="noreferrer" className="block break-all text-xs text-blue-700 underline">{mobilePairUrl}</a>
                        <p className="mt-2 text-xs text-emerald-800">Open this link on phone and choose Problem 34 or 35 for upload.</p>
                      </div>
                    </div>
                  </div>
                )}
                {/* Phone upload / grade result — visible regardless of QR panel state */}
                {task34LastUploadUrl && (
                  <div className={`mt-3 rounded-lg border p-3 text-sm ${task34PhoneGrade ? (task34PhoneGrade.is_correct ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50') : 'border-blue-200 bg-blue-50 text-blue-800'}`}>
                    {!task34PhoneGrade && <p className="font-semibold text-blue-800 mb-2">📷 Photo received — grading…</p>}
                    {task34PhoneGrade && (
                      <p className={`font-semibold mb-2 ${task34PhoneGrade.is_correct ? 'text-emerald-900' : 'text-red-900'}`}>
                        📱 Phone grade (Task 34): {task34PhoneGrade.score}/100 — Answer: {task34PhoneGrade.submitted_answer}
                      </p>
                    )}
                    <img src={task34LastUploadUrl} alt="uploaded task 34" className="max-h-48 rounded border" />
                  </div>
                )}
                {/* AI feedback */}
                {task34Feedback && (
                  <div className={`mt-4 rounded-xl p-4 text-sm ${
                    task34Feedback.correct ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
                  }`}>
                    <p className="font-semibold mb-1">{task34Feedback.correct ? '✅ Вярно!' : '❌ Не съвсем.'}</p>
                    <div className="leading-relaxed">{renderMathText(task34Feedback.message)}</div>
                  </div>
                )}
              </div>
            </section>
          );
        })()}

        {/* ── Linear system #2 ── */}
        {(() => {
          const { a, b, x, y, xy, opts } = linearSystemConfig35;
          const labels = ['А', 'Б', 'В', 'Г'];
          const currentHostIsLocal = isLocalHostName(window.location.hostname);
          const resolvedHost = currentHostIsLocal ? task34LanHost.trim() : window.location.hostname;
          const resolvedPort = task34LanPort.trim() || window.location.port || '5173';
          const qrOrigin = resolvedHost ? `${window.location.protocol}//${resolvedHost}:${resolvedPort}` : window.location.origin;
          const mobilePairUrl = `${qrOrigin}/mobile-capture?channel=${encodeURIComponent(taskUploadChannelId)}`;
          const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(mobilePairUrl)}`;
          const handleCheck = async () => {
            if (!task35Answer.trim()) return;
            setTask35Checking(true);
            setTask35Feedback(null);
            try {
              const prompt = `Задача: системата $x + y = ${a}$, $x - y = ${b}$. Намери $x \\cdot y$.

Отговор на ученика: "${task35Answer.trim()}"
Правилен отговор: $x = ${x}$, $y = ${y}$, $x \\cdot y = ${xy}$

Без поздрав. Само кратко обяснение: ако отговорът е верен — потвърди с едно изречение. Ако е сгрешен — обясни грешката и покажи решението стъпка по стъпка с LaTeX ($...$ за inline). Отговаряй само на български.`;
              const reply = await sendChatMessage([{ role: 'user', content: prompt }]);
              const isCorrect = new RegExp(`\\b${xy}\\b`).test(task35Answer.trim());
              setTask35Feedback({ correct: isCorrect, message: reply });
            } catch {
              setTask35Feedback({ correct: false, message: 'Грешка при проверката. Моля, опитай пак.' });
            } finally {
              setTask35Checking(false);
            }
          };
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔢</span>
                <h2 className="text-base font-bold text-gray-900">Задача 35 — Система линейни уравнения</h2>
              </div>
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-100">
                <p className="text-sm text-gray-700 mb-3">Дадена е системата. Намерете стойността на <strong>x · y</strong>:</p>
                <div className="inline-flex flex-col gap-1 bg-white border border-gray-200 rounded-xl px-6 py-4 text-lg font-mono shadow-sm">
                  <span>x + y = <strong>{a}</strong></span>
                  <span>x − y = <strong>{b}</strong></span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-xs text-gray-400 self-center">Бърз избор:</span>
                  {opts.map((opt, i) => (
                    <button key={i}
                      onClick={() => { setTask35Answer(String(opt)); setTask35Feedback(null); }}
                      className="px-3 py-1 rounded-lg border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-violet-50 hover:border-violet-300"
                    >
                      {labels[i]}) {opt}
                    </button>
                  ))}
                </div>
                <div className="mt-4 flex gap-2 items-center">
                  <input
                    type="text"
                    value={task35Answer}
                    onChange={e => { setTask35Answer(e.target.value); setTask35Feedback(null); }}
                    onKeyDown={e => e.key === 'Enter' && handleCheck()}
                    placeholder="Напр. '21' или 'x=7, y=3, x·y=21'"
                    className="flex-1 rounded-xl border border-gray-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                  />
                  <button
                    onClick={handleCheck}
                    disabled={task35Checking || !task35Answer.trim()}
                    className="px-4 py-2 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {task35Checking ? 'Проверявам...' : 'Провери'}
                  </button>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      const next = !task35ShowCameraQr;
                      setTask35ShowCameraQr(next);
                      if (next) {
                        void seedTaskUploadContexts();
                      }
                    }}
                    className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
                  >
                    {task35ShowCameraQr ? 'Hide Camera QR' : 'Upload From Camera'}
                  </button>
                  <span className="text-xs text-gray-500">Scan on phone, submit answer there, AI grades and syncs here.</span>
                </div>

                {task35ShowCameraQr && (
                  <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                    <p className="text-sm font-semibold text-emerald-800">Phone Pairing for Task 35</p>
                    <p className="text-xs text-emerald-700 mt-1">Channel: <span className="font-mono">{taskUploadChannelId}</span></p>
                    {currentHostIsLocal && (
                      <div className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2">
                        <p className="text-xs text-amber-800 mb-1">Desktop is on localhost. Enter LAN IP for phone QR:</p>
                        <input
                          type="text"
                          value={task34LanHost}
                          onChange={(e) => setTask34LanHost(e.target.value)}
                          placeholder="192.168.1.10"
                          className="w-full rounded-md border border-amber-300 px-2 py-1 text-xs"
                        />
                        <p className="text-xs text-amber-800 mt-2 mb-1">Frontend port (usually 5173):</p>
                        <input
                          type="text"
                          value={task34LanPort}
                          onChange={(e) => setTask34LanPort(e.target.value)}
                          placeholder="5173"
                          className="w-full rounded-md border border-amber-300 px-2 py-1 text-xs"
                        />
                      </div>
                    )}
                    {!currentHostIsLocal && window.location.port !== task34LanPort.trim() && (
                      <p className="text-xs text-amber-700 mt-2">QR uses port {task34LanPort.trim()} (current page port is {window.location.port || 'default'}).</p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-4">
                      <img src={qrUrl} alt="Task 35 phone QR" className="h-40 w-40 rounded-lg border border-emerald-200 bg-white p-1" />
                      <div className="min-w-0 flex-1">
                        <a href={mobilePairUrl} target="_blank" rel="noreferrer" className="block break-all text-xs text-blue-700 underline">{mobilePairUrl}</a>
                        <p className="mt-2 text-xs text-emerald-800">Open this link on phone and choose Problem 34 or 35 for upload.</p>
                      </div>
                    </div>
                  </div>
                )}
                {/* Phone upload / grade result — visible regardless of QR panel state */}
                {task35LastUploadUrl && (
                  <div className={`mt-3 rounded-lg border p-3 text-sm ${task35PhoneGrade ? (task35PhoneGrade.is_correct ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50') : 'border-blue-200 bg-blue-50 text-blue-800'}`}>
                    {!task35PhoneGrade && <p className="font-semibold text-blue-800 mb-2">📷 Photo received — grading…</p>}
                    {task35PhoneGrade && (
                      <p className={`font-semibold mb-2 ${task35PhoneGrade.is_correct ? 'text-emerald-900' : 'text-red-900'}`}>
                        📱 Phone grade (Task 35): {task35PhoneGrade.score}/100 — Answer: {task35PhoneGrade.submitted_answer}
                      </p>
                    )}
                    <img src={task35LastUploadUrl} alt="uploaded task 35" className="max-h-48 rounded border" />
                  </div>
                )}
                {task35Feedback && (
                  <div className={`mt-4 rounded-xl p-4 text-sm ${
                    task35Feedback.correct ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
                  }`}>
                    <p className="font-semibold mb-1">{task35Feedback.correct ? '✅ Вярно!' : '❌ Не съвсем.'}</p>
                    <div className="leading-relaxed">{renderMathText(task35Feedback.message)}</div>
                  </div>
                )}
              </div>
            </section>
          );
        })()}

        {/* New Zadacha: two horizontal parallel lines */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <span className="text-xl">📏</span>
            <h2 className="text-base font-bold text-gray-900">Нова задача — две успоредни хоризонтални прави</h2>
          </div>
          <div className="p-6">
            <svg viewBox="0 0 560 180" width="100%" height="180" style={{ display: 'block', margin: '0 auto' }}>
              <line x1="60" y1="60" x2="500" y2="60" stroke="#1e3a5f" strokeWidth="3" />
              <line x1="60" y1="120" x2="500" y2="120" stroke="#1e3a5f" strokeWidth="3" />
              {bottomCrossPlane === 'left' ? (
                <>
                  <line x1="140" y1="24" x2="285" y2="90" stroke="#1e3a5f" strokeWidth="2.5" />
                  <line x1="285" y1="90" x2="140" y2="156" stroke="#1e3a5f" strokeWidth="2.5" />
                  <path d="M203 60 A16 16 0 0 0 233.6 66.6" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <path d="M235 120 A16 16 0 0 0 233.6 113.4" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <path d="M270.4 83.4 A18 18 0 0 0 270.4 96.6" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <text x="206" y="57" fontSize="14" fill="#1e3a5f" fontWeight="700">{bottomCrossConfig.beta}°</text>
                  <text x="238" y="118" fontSize="14" fill="#1e3a5f" fontWeight="700">{bottomCrossConfig.gamma}°</text>
                  <text x="259" y="92" fontSize="14" fill="#1e3a5f" fontWeight="700">x</text>
                </>
              ) : (
                <>
                  <line x1="430" y1="24" x2="285" y2="90" stroke="#1e3a5f" strokeWidth="2.5" />
                  <line x1="285" y1="90" x2="430" y2="156" stroke="#1e3a5f" strokeWidth="2.5" />
                  <path d="M367 60 A16 16 0 0 1 336.4 66.6" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <path d="M335 120 A16 16 0 0 1 336.4 113.4" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <path d="M301.4 82.5 A18 18 0 0 1 301.4 97.5" fill="none" stroke="#1e3a5f" strokeWidth="1.8" />
                  <text x="338" y="57" fontSize="14" fill="#1e3a5f" fontWeight="700">{bottomCrossConfig.beta}°</text>
                  <text x="306" y="118" fontSize="14" fill="#1e3a5f" fontWeight="700">{bottomCrossConfig.gamma}°</text>
                  <text x="309" y="92" fontSize="14" fill="#1e3a5f" fontWeight="700">x</text>
                </>
              )}
              <circle cx="285" cy="90" r="3.8" fill="#1e3a5f" />
              <text x="510" y="64" fontSize="16" fill="#1e3a5f" fontWeight="700">a</text>
              <text x="510" y="124" fontSize="16" fill="#1e3a5f" fontWeight="700">b</text>
            </svg>
            <div className="mt-4 text-sm text-gray-800 leading-relaxed">
              <p>
                Правите <strong>a</strong> и <strong>b</strong> са успоредни.{' '}
                Дадено: β = {bottomCrossConfig.beta}°, γ = {bottomCrossConfig.gamma}°. Намери x.
              </p>
              <p className="mt-2 text-xs text-gray-500">
                Решение: x = (180° − β) + γ = (180° − {bottomCrossConfig.beta}°) + {bottomCrossConfig.gamma}° ={' '}
                <span className="font-semibold">x = {bottomCrossConfig.epsilon}°</span>
              </p>
            </div>
          </div>
        </section>

        {/* ── Parallelogram ABCD: DK ⊥ AB, DL ⊥ AC ── */}
        {(() => {
          const { m, n } = parallelogramABCDConfig;
          const fv = (v: number) => demoMode ? '？' : String(v);
          const answer = m + n;
          return (
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <span className="text-xl">🔷</span>
                <h2 className="text-base font-bold text-gray-900">Задача — Успоредник ABCD, DK ⊥ AB, DL ⊥ AC</h2>
              </div>
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 text-sm space-y-1">
                <p className="text-gray-700">∠BAD = 45°, ∠BAC = 15°, ∠DAC = 30°.</p>
                <p className="text-gray-700">AF = m = <strong>{fv(m)}</strong>, CH = n = <strong>{fv(n)}</strong>. Намерете AC.</p>
                <p className="text-gray-700">Решение: AF + FH + HC = AC ⇒ m + (m+n − m) = m + n = <span className="font-bold text-green-700">{demoMode ? '？' : `${answer}`}</span></p>
              </div>
              <div className="p-6">
                <ParallelogramABCDDiagram config={parallelogramABCDConfig} demo={demoMode} />
              </div>
            </section>
          );
        })()}

        {/* Math Notation Sandbox */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <span className="text-xl">✏️</span>
            <h2 className="text-base font-bold text-gray-900">Математическа нотация</h2>
            <span className="text-xs text-gray-400 ml-1">Използвай $…$ за inline LaTeX, $$…$$ за display</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-100">
            <div className="p-6 flex flex-col gap-3">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Вход</label>
              <textarea
                value={mathInput}
                onChange={(e) => setMathInput(e.target.value)}
                rows={8}
                className="w-full resize-y rounded-xl border border-gray-200 p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-violet-400"
                placeholder="Въведи текст с LaTeX формули..."
                spellCheck={false}
              />
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_SNIPPETS.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => setMathInput(s.text)}
                    className="px-3 py-1 rounded-lg bg-violet-50 text-violet-700 text-xs font-medium hover:bg-violet-100 border border-violet-200"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-6 flex flex-col gap-3">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Преглед</label>
              <div className="flex-1 min-h-[12rem] rounded-xl border border-gray-100 bg-slate-50 p-4 text-base leading-relaxed text-gray-800">
                {renderMathText(mathInput)}
              </div>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
};

export default PlaygroundPage;
