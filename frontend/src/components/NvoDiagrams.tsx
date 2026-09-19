/**
 * NvoDiagrams.tsx
 * Exports all playground SVG diagram components used in NVO exam questions.
 * Each component receives a typed config and an optional demo flag.
 * NO answer values are displayed - diagrams show only problem setup.
 */
import React from 'react';
import SceneRenderer, { type Scene } from './SceneRenderer';

// ─── Type definitions ──────────────────────────────────────────────────────────

export type RhombusCOMConfig = { angADB: number };

export type IntersectLinesConfig = { k1: number; k2: number; aAng: number; bAng: number };

export type ExtAngBConfig = { angA: number; angC: number; extAt: 'A' | 'B' | 'C'; givenExt: 'A' | 'B' | 'C' };

export type IsoscAltConfig = { AH: number; ratioP: number; ratioQ: number };

export type PerpBisecBCConfig = { angB: number; MD: number; angA: number };

export type ParallelDLConfig = { angALD: number };

export type BoxEdge = 'AB' | 'A1B1' | 'BC' | 'D1C1' | 'AA1' | 'BB1';
export type BoxVolumeLabel = { text: string; edge: BoxEdge };
export type BoxVolumeConfig = {
  vol: number;
  dmValues: [number, number, number];
  labels: [BoxVolumeLabel, BoxVolumeLabel, BoxVolumeLabel];
};

export type RightTriABConfig = {
  dm: number; ab: number; areaABC: number;
  // legacy field (ratio 1:5 only)
  areaABD?: number;
  // new fields (all ratios)
  ratio_p?: number; ratio_q?: number; angle_bad?: number; areaABD_str?: string;
};

export type ParallelogramABCDConfig = {
  angBAD: number; ratioDAC: number; ratioBAC: number; m: number; n: number;
};

export type CongrTriConfig = { angACB: number; angMOC: number; flipO?: boolean };

export type PerpBisecCMConfig = { angB: number; AC: number };

export type RightTriPerimConfig = { AC: number; CB: number };

// ─── RhombusCOMDiagram ─────────────────────────────────────────────────────────

export const RhombusCOMDiagram: React.FC<{ config: RhombusCOMConfig; demo?: boolean }> = ({ config }) => {
  const { angADB } = config;
  const angDAB = 180 - 2 * angADB;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 440, H = 290;
  const beta = toRad(angDAB);
  const side = 160;
  const relBx = side, relBy = 0;
  const relDx = side * Math.cos(beta), relDy = -side * Math.sin(beta);
  const relCx = side + relDx, relCy = relDy;
  const relMinX = Math.min(0, relBx, relCx, relDx);
  const relMaxX = Math.max(0, relBx, relCx, relDx);
  const relMinY = Math.min(0, relBy, relCy, relDy);
  const relMaxY = Math.max(0, relBy, relCy, relDy);
  const pad = 50;
  const Ax = pad - relMinX + (W - pad * 2 - (relMaxX - relMinX)) / 2;
  const Ay = pad - relMinY + (H - pad * 2 - (relMaxY - relMinY)) / 2;
  const Bx = Ax + relBx, By = Ay + relBy;
  const Dx = Ax + relDx, Dy = Ay + relDy;
  const Cx = Ax + relCx, Cy = Ay + relCy;
  const Ox = (Ax + Cx) / 2, Oy = (Ay + Cy) / 2;
  const Mx = (Bx + Cx) / 2, My = (By + Cy) / 2;
  const arcDr = 32;
  const DAang = Math.atan2(Ay - Dy, Ax - Dx);
  const DBang = Math.atan2(By - Dy, Bx - Dx);
  const arcDsx = Dx + arcDr * Math.cos(DAang), arcDsy = Dy + arcDr * Math.sin(DAang);
  const arcDex = Dx + arcDr * Math.cos(DBang), arcDey = Dy + arcDr * Math.sin(DBang);
  const arcOr = 28;
  const OCang = Math.atan2(Cy - Oy, Cx - Ox);
  const OMang = Math.atan2(My - Oy, Mx - Ox);
  const arcOsx = Ox + arcOr * Math.cos(OCang), arcOsy = Oy + arcOr * Math.sin(OCang);
  const arcOex = Ox + arcOr * Math.cos(OMang), arcOey = Oy + arcOr * Math.sin(OMang);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy} ${Dx},${Dy}`} fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#6b7280" strokeWidth={1.3} strokeDasharray="5,3" />
      <line x1={Bx} y1={By} x2={Dx} y2={Dy} stroke="#6b7280" strokeWidth={1.3} strokeDasharray="5,3" />
      <line x1={Ox} y1={Oy} x2={Mx} y2={My} stroke="#dc2626" strokeWidth={1.6} strokeDasharray="4,3" />
      <path d={`M ${arcDsx},${arcDsy} A ${arcDr},${arcDr} 0 0,0 ${arcDex},${arcDey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={Dx + Math.cos((DAang + DBang) / 2 + Math.PI) * (arcDr + 14)} y={Dy + Math.sin((DAang + DBang) / 2 + Math.PI) * (arcDr + 14)} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{angADB}°</text>
      <path d={`M ${arcOsx},${arcOsy} A ${arcOr},${arcOr} 0 0,0 ${arcOex},${arcOey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <circle cx={Ox} cy={Oy} r={5} fill="#1e40af" stroke="#fff" strokeWidth={1.5} />
      <circle cx={Mx} cy={My} r={3} fill="#374151" />
      <text x={Ax - 16} y={Ay + 6}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 2}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Dx - 6}  y={Dy - 10} fontSize={13} fill="#1e40af" fontWeight="700">D</text>
      <text x={Ox + 8}  y={Oy - 8}  fontSize={15} fill="#1e40af" fontWeight="700">O</text>
      <text x={Mx + 6}  y={My + 4}  fontSize={12} fill="#374151">M</text>
    </svg>
  );
};

// ─── IntersectLinesDiagram ─────────────────────────────────────────────────────

export const IntersectLinesDiagram: React.FC<{ config: IntersectLinesConfig; demo?: boolean }> = ({ config }) => {
  const { k1, k2, aAng, bAng } = config;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 360, H = 230;
  const Ix = 195, Iy = 140;
  const rayLen = 120;
  const aRx = Ix + rayLen * Math.cos(toRad(aAng)), aRy = Iy - rayLen * Math.sin(toRad(aAng));
  const aLx = Ix - rayLen * Math.cos(toRad(aAng)), aLy = Iy + rayLen * Math.sin(toRad(aAng));
  const bUx = Ix + rayLen * Math.cos(toRad(bAng)), bUy = Iy - rayLen * Math.sin(toRad(bAng));
  const bDx = Ix - rayLen * Math.cos(toRad(bAng)), bDy = Iy + rayLen * Math.sin(toRad(bAng));
  const arc1r = 44;
  const arc1sa = toRad(aAng), arc1ea = toRad(bAng);
  const arc1sx = Ix + arc1r * Math.cos(arc1sa), arc1sy = Iy - arc1r * Math.sin(arc1sa);
  const arc1ex = Ix + arc1r * Math.cos(arc1ea), arc1ey = Iy - arc1r * Math.sin(arc1ea);
  const arc1midRad = (arc1sa + arc1ea) / 2;
  const arc1labR = arc1r + 22;
  const arc2r = 38;
  const arc2sa = toRad(aAng);
  const arc2ea = toRad(bAng + 180);
  const arc2sx = Ix + arc2r * Math.cos(arc2sa), arc2sy = Iy - arc2r * Math.sin(arc2sa);
  const arc2ex = Ix + arc2r * Math.cos(arc2ea), arc2ey = Iy - arc2r * Math.sin(arc2ea);
  const arc2midRad = arc2sa - (arc2sa - (arc2ea - 2 * Math.PI)) / 2;
  const arc2labR = arc2r + 22;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <line x1={aLx} y1={aLy} x2={aRx} y2={aRy} stroke="#374151" strokeWidth={1.8} />
      <line x1={bDx} y1={bDy} x2={bUx} y2={bUy} stroke="#374151" strokeWidth={1.8} />
      <path d={`M ${arc1sx},${arc1sy} A ${arc1r},${arc1r} 0 0,0 ${arc1ex},${arc1ey}`} fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text x={Ix + arc1labR * Math.cos(arc1midRad)} y={Iy - arc1labR * Math.sin(arc1midRad)} fontSize={12} fill="#374151" textAnchor="middle">{`2x+${k1}°`}</text>
      <path d={`M ${arc2sx},${arc2sy} A ${arc2r},${arc2r} 0 0,1 ${arc2ex},${arc2ey}`} fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text x={Ix + arc2labR * Math.cos(arc2midRad)} y={Iy - arc2labR * Math.sin(arc2midRad)} fontSize={12} fill="#374151" textAnchor="middle">{`x+${k2}°`}</text>
      <circle cx={Ix} cy={Iy} r={3} fill="#374151" />
      <text x={bUx + 6} y={bUy - 4} fontSize={13} fill="#1e40af" fontWeight="700">b</text>
      <text x={aLx + 4} y={aLy + 14} fontSize={13} fill="#1e40af" fontWeight="700">a</text>
    </svg>
  );
};

// ─── ExtAngBDiagram ────────────────────────────────────────────────────────────

export const ExtAngBDiagram: React.FC<{ config: ExtAngBConfig; demo?: boolean }> = ({ config }) => {
  const { angA, angC, extAt, givenExt } = config;
  const angB = 180 - angA - angC;
  const thirdV = (['A', 'B', 'C'] as const).find(v => v !== extAt && v !== givenExt)!;
  const extAngOf = (v: 'A' | 'B' | 'C') => v === 'A' ? 180 - angA : v === 'B' ? 180 - angB : 180 - angC;
  const intAngOf = (v: 'A' | 'B' | 'C') => v === 'A' ? angA : v === 'B' ? angB : angC;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 420, H = 240, pad = 48, base = 200, extLen = 65;
  const tanA = Math.tan(toRad(angA));
  const tanBv = Math.tan(toRad(angB));
  const rCx = (base * tanBv) / (tanA + tanBv);
  const rCy = -(rCx * tanA);
  const relExtTip = (v: 'A' | 'B' | 'C'): [number, number] => {
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
  const vPos = (v: 'A' | 'B' | 'C'): [number, number] => v === 'A' ? [Ax, Ay] : v === 'B' ? [Bx, By] : [Cx, Cy];
  const extAdjV = (v: 'A' | 'B' | 'C'): 'A' | 'B' | 'C' => v === 'A' ? 'C' : 'A';
  const arcR = 26, arcRext = 28;
  const intArcEl = (v: 'A' | 'B' | 'C') => {
    const [Vx, Vy] = vPos(v);
    const others = (['A', 'B', 'C'] as const).filter(x => x !== v) as ['A' | 'B' | 'C', 'A' | 'B' | 'C'];
    const [U1x, U1y] = vPos(others[0]);
    const [U2x, U2y] = vPos(others[1]);
    const d1 = Math.atan2(U1y - Vy, U1x - Vx);
    const d2 = Math.atan2(U2y - Vy, U2x - Vx);
    const sx = Vx + arcR * Math.cos(d1), sy = Vy + arcR * Math.sin(d1);
    const ex2 = Vx + arcR * Math.cos(d2), ey2 = Vy + arcR * Math.sin(d2);
    const sweep = (Math.cos(d1) * Math.sin(d2) - Math.sin(d1) * Math.cos(d2)) > 0 ? 1 : 0;
    const mid = (d1 + d2) / 2;
    return (<g key={`int-${v}`}>
      <path d={`M ${sx},${sy} A ${arcR},${arcR} 0 0,${sweep} ${ex2},${ey2}`} fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text x={Vx + (arcR + 16) * Math.cos(mid)} y={Vy + (arcR + 16) * Math.sin(mid)} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{intAngOf(v)}°</text>
    </g>);
  };
  const extArcEl = (v: 'A' | 'B' | 'C', etx: number, ety: number, label: string, color: string) => {
    const [Vx, Vy] = vPos(v);
    const [Wx, Wy] = vPos(extAdjV(v));
    const d1 = Math.atan2(Wy - Vy, Wx - Vx);
    const d2 = Math.atan2(ety - Vy, etx - Vx);
    const sx = Vx + arcRext * Math.cos(d1), sy = Vy + arcRext * Math.sin(d1);
    const epx = Vx + arcRext * Math.cos(d2), epy = Vy + arcRext * Math.sin(d2);
    const sweep = (Math.cos(d1) * Math.sin(d2) - Math.sin(d1) * Math.cos(d2)) > 0 ? 1 : 0;
    const mid = (d1 + d2) / 2;
    return (<g key={`ext-${v}`}>
      <path d={`M ${sx},${sy} A ${arcRext},${arcRext} 0 0,${sweep} ${epx},${epy}`} fill="none" stroke={color} strokeWidth={1.5} />
      <text x={Vx + (arcRext + 20) * Math.cos(mid)} y={Vy + (arcRext + 20) * Math.sin(mid)} fontSize={13} fill={color} fontWeight="700" textAnchor="middle">{label}</text>
    </g>);
  };
  const [eAtVx, eAtVy] = vPos(extAt);
  const [eGivVx, eGivVy] = vPos(givenExt);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="rgba(59,130,246,0.08)" stroke="#1e40af" strokeWidth={1.7} />
      <line x1={eAtVx} y1={eAtVy} x2={ExtAtX} y2={ExtAtY} stroke="#374151" strokeWidth={1.7} />
      <line x1={eGivVx} y1={eGivVy} x2={ExtGivX} y2={ExtGivY} stroke="#374151" strokeWidth={1.7} />
      {extArcEl(extAt, ExtAtX, ExtAtY, `${extAngOf(extAt)}°`, '#7c3aed')}
      {extArcEl(givenExt, ExtGivX, ExtGivY, `${extAngOf(givenExt)}°`, '#7c3aed')}
      {intArcEl(thirdV)}
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <text x={Ax - 12} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx - 6} y={By + 16} fontSize={13} fill="#1e40af" fontWeight="700" textAnchor="middle">B</text>
      <text x={Cx + 8} y={Cy - 6} fontSize={13} fill="#1e40af" fontWeight="700">C</text>
    </svg>
  );
};

// ─── IsoscAltDiagram ───────────────────────────────────────────────────────────

export const IsoscAltDiagram: React.FC<{ config: IsoscAltConfig; demo?: boolean }> = ({ config }) => {
  const { AH, ratioP, ratioQ } = config;
  const HC = AH * ratioQ / ratioP;
  const HB = AH;
  const W = 380, H = 240, pad = 44;
  const totalAB = 2 * AH;
  const scX = (W - pad * 2) / totalAB;
  const scY = (H - pad * 2) / HC;
  const sc = Math.min(scX, scY, 30);
  const tx = (W - totalAB * sc) / 2;
  const ty = pad + HC * sc;
  const Ax = tx, Ay = ty;
  const Hx = tx + AH * sc, Hy = ty;
  const Bx = tx + totalAB * sc, By = ty;
  const Cx = Hx, Cy = ty - HC * sc;
  const arcR = 10;
  const arcSx = Hx, arcSy = Hy - arcR;
  const arcEx = Hx + arcR, arcEy = Hy;
  const dotX = Hx + arcR / 2, dotY = Hy - arcR / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="rgba(59,130,246,0.08)" stroke="#1e40af" strokeWidth={1.7} />
      <line x1={Cx} y1={Cy} x2={Hx} y2={Hy} stroke="#6b7280" strokeWidth={1.5} strokeDasharray="5,3" />
      <path d={`M ${arcSx},${arcSy} A ${arcR},${arcR} 0 0,1 ${arcEx},${arcEy}`} fill="none" stroke="#374151" strokeWidth={1.3} />
      <circle cx={dotX} cy={dotY} r={2.2} fill="#374151" />
      <text x={(Ax + Hx) / 2} y={Ay + 16} fontSize={12} fill="#374151" textAnchor="middle">{AH}</text>
      <text x={(Hx + Bx) / 2} y={Ay + 16} fontSize={12} fill="#374151" textAnchor="middle">{HB}</text>
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <circle cx={Hx} cy={Hy} r={3} fill="#374151" />
      <text x={Ax - 12} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 14} fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 6}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Hx - 4}  y={Hy + 15} fontSize={12} fill="#374151" fontWeight="700">H</text>
    </svg>
  );
};

// ─── PerpBisecBCDiagram ────────────────────────────────────────────────────────

export const PerpBisecBCDiagram: React.FC<{ config: PerpBisecBCConfig; demo?: boolean }> = ({ config }) => {
  const { angA } = config;
  const toRad = (d: number) => d * Math.PI / 180;
  const angB = 30;
  const angC = 180 - angA - angB;
  const c = 220;
  const AC = c * Math.sin(toRad(angB)) / Math.sin(toRad(angC));
  const mCx = AC * Math.cos(toRad(angA));
  const mCy = AC * Math.sin(toRad(angA));
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
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="none" stroke="#1e40af" strokeWidth={1.8} />
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

// ─── ParallelDLDiagram ─────────────────────────────────────────────────────────

export const ParallelDLDiagram: React.FC<{ config: ParallelDLConfig; demo?: boolean }> = ({ config }) => {
  const { angALD } = config;
  const angDAB = 180 - 2 * angALD;
  const angADC = 180 - angDAB;
  const angADL = angADC / 2;
  const toRad = (d: number) => d * Math.PI / 180;
  const W = 420, H = 200;
  const Ax = 55, Ay = 165;
  const Bx = 320, By = 165;
  const slant = 55, ht = 100;
  const Dx = Ax + slant, Dy = Ay - ht;
  const Cx = Bx + slant, Cy = Ay - ht;
  const ADlen = Math.sqrt((Dx - Ax) ** 2 + (Dy - Ay) ** 2);
  const AL_ratio = Math.sin(toRad(angADL)) / Math.sin(toRad(angALD));
  const ALpx = AL_ratio * ADlen;
  const ABlen = Bx - Ax;
  const Lx = Ax + Math.min(ALpx, ABlen * 0.85);
  const Ly = Ay;
  const arcAr = 28;
  const ADang = Math.atan2(Dy - Ay, Dx - Ax);
  const arcAsx = Ax + arcAr * Math.cos(ADang), arcAsy = Ay + arcAr * Math.sin(ADang);
  const arcAex = Ax + arcAr, arcAey = Ay;
  const arcLr = 26;
  const LAang = Math.atan2(Ay - Ly, Ax - Lx);
  const LDang = Math.atan2(Dy - Ly, Dx - Lx);
  const arcLsx = Lx + arcLr * Math.cos(LAang), arcLsy = Ly + arcLr * Math.sin(LAang);
  const arcLex = Lx + arcLr * Math.cos(LDang), arcLey = Ly + arcLr * Math.sin(LDang);
  const angLmid = (LAang + LDang) / 2;
  const arcDr = 24;
  const DAang = Math.atan2(Ay - Dy, Ax - Dx);
  const DCang = Math.atan2(Cy - Dy, Cx - Dx);
  const arcDsx = Dx + arcDr * Math.cos(DAang), arcDsy = Dy + arcDr * Math.sin(DAang);
  const arcDex = Dx + arcDr * Math.cos(DCang), arcDey = Dy + arcDr * Math.sin(DCang);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy} ${Dx},${Dy}`} fill="rgba(59,130,246,0.07)" stroke="#1e40af" strokeWidth={1.7} />
      <line x1={Dx} y1={Dy} x2={Lx} y2={Ly} stroke="#374151" strokeWidth={1.5} />
      <path d={`M ${arcDsx},${arcDsy} A ${arcDr},${arcDr} 0 0,0 ${arcDex},${arcDey}`} fill="none" stroke="#7c3aed" strokeWidth={1.3} />
      <path d={`M ${arcLsx},${arcLsy} A ${arcLr},${arcLr} 0 0,1 ${arcLex},${arcLey}`} fill="none" stroke="#7c3aed" strokeWidth={1.4} />
      <text x={Lx + Math.cos(angLmid) * (arcLr + 16)} y={Ly + Math.sin(angLmid) * (arcLr + 16)} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{angALD}°</text>
      <path d={`M ${arcAsx},${arcAsy} A ${arcAr},${arcAr} 0 0,0 ${arcAex},${arcAey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      {[{ x: Ax, y: Ay }, { x: Bx, y: By }, { x: Cx, y: Cy }, { x: Dx, y: Dy }, { x: Lx, y: Ly }].map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#374151" />
      ))}
      <text x={Ax - 14} y={Ay + 14} fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 14} fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 6}  y={Cy - 4}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Dx - 6}  y={Dy - 8}  fontSize={13} fill="#1e40af" fontWeight="700">D</text>
      <text x={Lx - 4}  y={Ly + 15} fontSize={12} fill="#374151" fontWeight="600">L</text>
    </svg>
  );
};

// ─── BoxVolumeDiagram ──────────────────────────────────────────────────────────

export const BoxVolumeDiagram: React.FC<{ config: BoxVolumeConfig; demo?: boolean }> = ({ config }) => {
  const { labels } = config;
  const W = 420, H = 280;
  const ox = 95, oy = 205;
  const w = 160, h = 105;
  const ddx = 48, ddy = -28;
  const A  = [ox,         oy      ];
  const B  = [ox + w,     oy      ];
  const C  = [ox + w + ddx, oy + ddy];
  const D  = [ox + ddx,   oy + ddy];
  const A1 = [ox,         oy - h  ];
  const B1 = [ox + w,     oy - h  ];
  const C1 = [ox + w + ddx, oy - h + ddy];
  const D1 = [ox + ddx,   oy - h + ddy];
  const poly = (pts: number[][], fill: string) =>
    <polygon points={pts.map(p => p.join(',')).join(' ')} fill={fill} stroke="#374151" strokeWidth={1.6} />;
  const ln = (p1: number[], p2: number[], dash?: string) =>
    <line x1={p1[0]} y1={p1[1]} x2={p2[0]} y2={p2[1]} stroke="#9ca3af" strokeWidth={1.1} strokeDasharray={dash} />;
  const edgeLabelPos = (edge: BoxEdge) => {
    switch (edge) {
      case 'AB':   return { x: (A[0] + B[0]) / 2, y: A[1] + 17, anchor: 'middle' as const };
      case 'A1B1': return { x: (A1[0] + B1[0]) / 2, y: A1[1] - 10, anchor: 'middle' as const };
      case 'BC':   return { x: (B[0] + C[0]) / 2 + 10, y: (B[1] + C[1]) / 2 + 12, anchor: 'start' as const };
      case 'D1C1': return { x: (D1[0] + C1[0]) / 2 + 8, y: (D1[1] + C1[1]) / 2 - 8, anchor: 'start' as const };
      case 'AA1':  return { x: A1[0] - 12, y: (A[1] + A1[1]) / 2 + 4, anchor: 'end' as const };
      case 'BB1':  return { x: B1[0] + 10, y: (B[1] + B1[1]) / 2 + 4, anchor: 'start' as const };
    }
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {poly([A, B, B1, A1], '#e0effe')}
      {poly([B, C, C1, B1], '#bfdbfe')}
      {poly([A1, B1, C1, D1], '#eff6ff')}
      {ln(D, A, '5,3')}
      {ln(D, C, '5,3')}
      {ln(D, D1, '5,3')}
      {labels.map((label, index) => {
        const pos = edgeLabelPos(label.edge);
        return <text key={`${label.edge}-${index}`} x={pos.x} y={pos.y} fontSize={12} fill="#374151" textAnchor={pos.anchor}>{label.text}</text>;
      })}
      {[A, B, C, A1, B1, C1, D1].map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={3} fill="#374151" />)}
      <circle cx={D[0]} cy={D[1]} r={3} fill="#9ca3af" />
      <text x={A[0] - 14}  y={A[1] + 14}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={B[0] + 6}   y={B[1] + 14}  fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={C[0] + 6}   y={C[1] + 12}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={D[0] - 14}  y={D[1] + 14}  fontSize={13} fill="#9ca3af" fontWeight="600">D</text>
      <text x={A1[0] - 16} y={A1[1] - 6}  fontSize={13} fill="#1e40af" fontWeight="700">A₁</text>
      <text x={B1[0] + 6}  y={B1[1] - 6}  fontSize={13} fill="#1e40af" fontWeight="700">B₁</text>
      <text x={C1[0] + 6}  y={C1[1] - 6}  fontSize={13} fill="#1e40af" fontWeight="700">C₁</text>
      <text x={D1[0] - 18} y={D1[1] - 6}  fontSize={13} fill="#1e40af" fontWeight="700">D₁</text>
    </svg>
  );
};

// ─── RightTriABDiagram ─────────────────────────────────────────────────────────

export const RightTriABDiagram: React.FC<{ config: RightTriABConfig; demo?: boolean }> = () => {
  const W = 330, H = 210;
  const ax = 40, ay = 115;
  const bx = 265, by = 115;
  const mx = (ax + bx) / 2, my = ay;
  const cx = mx, cy = 35;
  const abPx = bx - ax;
  const dh = abPx / 4;
  const ha = dh / Math.tan(15 * Math.PI / 180);
  const hxC = ax + ha;
  const dy = ay + dh;
  const dx = hxC;
  const arcR = 10;
  const CAx = ax - cx, CAy = ay - cy;
  const CAlen = Math.sqrt(CAx * CAx + CAy * CAy);
  const CBx = bx - cx, CBy = by - cy;
  const CBlen = Math.sqrt(CBx * CBx + CBy * CBy);
  const uCAx = CAx / CAlen, uCAy = CAy / CAlen;
  const uCBx = CBx / CBlen, uCBy = CBy / CBlen;
  const cArcSx = cx + arcR * uCAx, cArcSy = cy + arcR * uCAy;
  const cArcEx = cx + arcR * uCBx, cArcEy = cy + arcR * uCBy;
  const cSweep = (uCAx * uCBy - uCAy * uCBx) > 0 ? 1 : 0;
  const cDotX = cx + arcR / 2 * (uCAx + uCBx);
  const cDotY = cy + arcR / 2 * (uCAy + uCBy);
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
      <line x1={mx} y1={5} x2={mx} y2={H - 5} stroke="#9CA3AF" strokeWidth={1} strokeDasharray="5,3" />
      <text x={mx + 4} y={14} fontSize={11} fill="#6B7280">S_AB</text>
      <line x1={ax} y1={ay} x2={cx} y2={cy} stroke="#2563EB" strokeWidth={1.5} />
      <line x1={bx} y1={by} x2={cx} y2={cy} stroke="#2563EB" strokeWidth={1.5} />
      <line x1={ax} y1={ay} x2={bx} y2={by} stroke="#374151" strokeWidth={1.8} />
      <path d={`M ${cArcSx},${cArcSy} A ${arcR},${arcR} 0 0,${cSweep} ${cArcEx},${cArcEy}`} fill="none" stroke="#374151" strokeWidth={1.1} />
      <circle cx={cDotX} cy={cDotY} r={2} fill="#374151" />
      <line x1={ax} y1={ay} x2={dx} y2={dy} stroke="#059669" strokeWidth={1.5} />
      <line x1={bx} y1={by} x2={dx} y2={dy} stroke="#059669" strokeWidth={1.5} />
      <line x1={dx} y1={dy} x2={hxC} y2={ay} stroke="#9CA3AF" strokeWidth={1} strokeDasharray="4,3" />
      <line x1={dx} y1={dy} x2={mx} y2={my} stroke="#DC2626" strokeWidth={1.2} strokeDasharray="4,3" />
      <path d={`M ${dArcSx},${dArcSy} A ${arcR},${arcR} 0 0,${dSweep} ${dArcEx},${dArcEy}`} fill="none" stroke="#374151" strokeWidth={1.1} />
      <circle cx={dDotX} cy={dDotY} r={2} fill="#374151" />
      <text x={ax - 12} y={ay + 5}  fontSize={12} fill="#374151" fontWeight="600">A</text>
      <text x={bx + 4}  y={ay + 5}  fontSize={12} fill="#374151" fontWeight="600">B</text>
      <text x={cx + 4}  y={cy - 3}  fontSize={12} fill="#374151" fontWeight="600">C</text>
      <text x={dx + 4}  y={dy + 12} fontSize={12} fill="#374151" fontWeight="600">D</text>
      <text x={mx - 4}  y={ay + 14} fontSize={11} fill="#374151">M</text>
      <text x={hxC + 4} y={ay + 14} fontSize={11} fill="#374151">H</text>
    </svg>
  );
};

// ─── CongrTriDiagram ───────────────────────────────────────────────────────────

export const CongrTriDiagram: React.FC<{ config: CongrTriConfig; demo?: boolean }> = ({ config }) => {
  const { angACB, angMOC, flipO = false } = config;
  const angABC = angMOC / 2;
  const angBAC = 180 - angACB - angABC;
  const W = 460, H = 290;
  const toRad = (d: number) => d * Math.PI / 180;
  const baseY = 255;
  const Ax = 40, Mx = 165, Bx = 280, Px = 420;
  const Ay = baseY, My = baseY, By = baseY, Py = baseY;
  const dACx = Math.cos(toRad(angBAC)), dACy = -Math.sin(toRad(angBAC));
  const dBCx = -Math.cos(toRad(angABC)), dBCy = -Math.sin(toRad(angABC));
  const detABC = dACx * (-dBCy) - dACy * (-dBCx);
  const tABC = ((Bx - Ax) * (-dBCy) - (By - Ay) * (-dBCx)) / detABC;
  const Cx = Ax + tABC * dACx;
  const Cy = Ay + tABC * dACy;
  const angMPT = angBAC;
  const dPTx = -Math.cos(toRad(angMPT)), dPTy = -Math.sin(toRad(angMPT));
  const dMTx = Math.cos(toRad(angABC)), dMTy = -Math.sin(toRad(angABC));
  const detPMT = dPTx * (-dMTy) - dPTy * (-dMTx);
  const tPMT = ((Mx - Px) * (-dMTy) - (My - Py) * (-dMTx)) / detPMT;
  const Tx = Px + tPMT * dPTx;
  const Ty = Py + tPMT * dPTy;
  const bcDx = Cx - Bx, bcDy = Cy - By;
  const mtDx = Tx - Mx, mtDy = Ty - My;
  const denom = bcDx * mtDy - bcDy * mtDx;
  const tBC = ((Mx - Bx) * mtDy - (My - By) * mtDx) / denom;
  const Ox = Bx + tBC * bcDx;
  const Oy = By + tBC * bcDy;
  const extPx = 18;
  const bcLen = Math.sqrt(bcDx * bcDx + bcDy * bcDy);
  const bcUx = bcDx / bcLen, bcUy = bcDy / bcLen;
  const mtLen = Math.sqrt(mtDx * mtDx + mtDy * mtDy);
  const mtUx = mtDx / mtLen, mtUy = mtDy / mtLen;
  const arcSweepToward = (u1x: number, u1y: number, u2x: number, u2y: number) =>
    (u1x * u2y - u1y * u2x) > 0 ? 1 : 0;
  const arcCr = 26;
  const CAang = Math.atan2(Ay - Cy, Ax - Cx);
  const CBang = Math.atan2(By - Cy, Bx - Cx);
  const arcCsx = Cx + arcCr * Math.cos(CAang);
  const arcCsy = Cy + arcCr * Math.sin(CAang);
  const arcCex = Cx + arcCr * Math.cos(CBang);
  const arcCey = Cy + arcCr * Math.sin(CBang);
  const sweepC = arcSweepToward(Math.cos(CAang), Math.sin(CAang), Math.cos(CBang), Math.sin(CBang));
  const arcOr = 26;
  const arcO_ang1 = flipO ? Math.atan2(By - Oy, Bx - Ox) : Math.atan2(My - Oy, Mx - Ox);
  const arcO_ang2 = flipO ? Math.atan2(Ty - Oy, Tx - Ox) : Math.atan2(Cy - Oy, Cx - Ox);
  const arcOsx = Ox + arcOr * Math.cos(arcO_ang1);
  const arcOsy = Oy + arcOr * Math.sin(arcO_ang1);
  const arcOex = Ox + arcOr * Math.cos(arcO_ang2);
  const arcOey = Oy + arcOr * Math.sin(arcO_ang2);
  const sweepO = arcSweepToward(Math.cos(arcO_ang1), Math.sin(arcO_ang1), Math.cos(arcO_ang2), Math.sin(arcO_ang2));
  const arcO_delta = sweepO === 1
    ? (arcO_ang2 - arcO_ang1 < 0 ? arcO_ang2 - arcO_ang1 + 2 * Math.PI : arcO_ang2 - arcO_ang1)
    : (arcO_ang2 - arcO_ang1 > 0 ? arcO_ang2 - arcO_ang1 - 2 * Math.PI : arcO_ang2 - arcO_ang1);
  const arcO_bisAng = arcO_ang1 + arcO_delta / 2;
  const arcOLblX = Ox + Math.cos(arcO_bisAng) * (arcOr + 14);
  const arcOLblY = Oy + Math.sin(arcO_bisAng) * (arcOr + 14);
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
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="#eff6ff" stroke="#1e40af" strokeWidth={1.8} />
      <polygon points={`${Px},${Py} ${Mx},${My} ${Tx},${Ty}`} fill="#f0fdf4" stroke="#15803d" strokeWidth={1.8} />
      <line x1={Bx - bcUx * extPx} y1={By - bcUy * extPx} x2={Cx + bcUx * extPx} y2={Cy + bcUy * extPx} stroke="#1e40af" strokeWidth={1.8} />
      <line x1={Mx - mtUx * extPx} y1={My - mtUy * extPx} x2={Tx + mtUx * extPx} y2={Ty + mtUy * extPx} stroke="#15803d" strokeWidth={1.8} />
      <path d={`M ${arcCsx},${arcCsy} A ${arcCr},${arcCr} 0 0,${sweepC} ${arcCex},${arcCey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={Cx + Math.cos((CAang + CBang) / 2) * (arcCr + 14)} y={Cy + Math.sin((CAang + CBang) / 2) * (arcCr + 14)} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{angACB}°</text>
      <path d={`M ${arcOsx},${arcOsy} A ${arcOr},${arcOr} 0 0,${sweepO} ${arcOex},${arcOey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={arcOLblX} y={arcOLblY} fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{angMOC}°</text>
      <path d={`M ${arcAsx},${arcAsy} A ${arcAr},${arcAr} 0 0,${sweepA} ${arcAex},${arcAey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <circle cx={Ox} cy={Oy} r={5} fill="#374151" stroke="#fff" strokeWidth={1.5} />
      <text x={Ax - 14} y={Ay + 6}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Mx - 4}  y={My + 16} fontSize={13} fill="#374151" fontWeight="600">M</text>
      <text x={Bx - 4}  y={By + 16} fontSize={13} fill="#374151" fontWeight="600">B</text>
      <text x={Px + 5}  y={Py + 6}  fontSize={13} fill="#15803d" fontWeight="700">P</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Tx + 5}  y={Ty - 6}  fontSize={13} fill="#15803d" fontWeight="700">T</text>
      <text x={Ox + 8}  y={Oy - 34} fontSize={15} fill="#374151" fontWeight="700">O</text>
    </svg>
  );
};

// ─── PerpBisecCMDiagram ────────────────────────────────────────────────────────

export const PerpBisecCMDiagram: React.FC<{ config: PerpBisecCMConfig; demo?: boolean }> = ({ config }) => {
  const { angB, AC } = config;
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
  const Nx = (Ax + Cx) / 2, Ny = (Ay + Cy) / 2;
  const ACdx = Cx - Ax, ACdy = Cy - Ay;
  const AClen = Math.sqrt(ACdx * ACdx + ACdy * ACdy);
  const perpX = -ACdy / AClen, perpY = ACdx / AClen;
  const tParam = (Ay - Ny) / perpY;
  const Mx = Nx + tParam * perpX, My = Ay;
  const extLen = 18;
  const perpExtX = Nx - perpX * extLen, perpExtY = Ny - perpY * extLen;
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
  const arcBr = 32;
  const BAang = Math.atan2(Ay - By, Ax - Bx);
  const BCang = Math.atan2(Cy - By, Cx - Bx);
  const arcBsx = Bx + arcBr * Math.cos(BAang), arcBsy = By + arcBr * Math.sin(BAang);
  const arcBex = Bx + arcBr * Math.cos(BCang), arcBey = By + arcBr * Math.sin(BCang);
  const acMidX = (Ax + Cx) / 2, acMidY = (Ay + Cy) / 2;
  const acLblX = acMidX - perpX * 26, acLblY = acMidY - perpY * 26;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />
      <line x1={perpExtX} y1={perpExtY} x2={Mx} y2={My} stroke="#6b7280" strokeWidth={1.5} strokeDasharray="5,3" />
      <line x1={Cx} y1={Cy} x2={Mx} y2={My} stroke="#dc2626" strokeWidth={1.6} strokeDasharray="5,3" />
      <path d={`M ${arcCsx},${arcCsy} A ${arcRc},${arcRc} 0 0,${arcCSweep} ${arcCex},${arcCey}`} fill="none" stroke="#374151" strokeWidth={1.4} />
      <circle cx={dotCx} cy={dotCy} r={1.8} fill="#374151" />
      <path d={`M ${arcBsx},${arcBsy} A ${arcBr},${arcBr} 0 0,1 ${arcBex},${arcBey}`} fill="none" stroke="#7c3aed" strokeWidth={1.5} />
      <text x={Bx - arcBr + 10} y={By + 20} fontSize={12} fill="#374151" fontWeight="600">{angB}°</text>
      <text x={acLblX} y={acLblY - 5}  fontSize={11} fill="#374151" textAnchor="middle">s AC</text>
      <text x={acLblX} y={acLblY + 9}  fontSize={12} fill="#374151" fontWeight="600" textAnchor="middle">{AC}</text>
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <circle cx={Mx} cy={My} r={3} fill="#374151" />
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
      <text x={Mx - 4}  y={My + 16} fontSize={13} fill="#374151" fontWeight="600">M</text>
    </svg>
  );
};

// ─── RightTriPerimDiagram ──────────────────────────────────────────────────────

export const RightTriPerimDiagram: React.FC<{ config: RightTriPerimConfig; demo?: boolean }> = ({ config }) => {
  const { AC, CB } = config;
  const W = 420, H = 280;
  const scale = Math.min(200 / Math.max(AC, CB), 18);
  const acPx = AC * scale;
  const cbPx = CB * scale;
  const Ax = 80, Ay = 240;
  const Bx = Ax + cbPx + acPx * 0.4, By = Ay;
  const angA = Math.atan2(CB, AC);
  const Cx = Ax + acPx * Math.cos(angA);
  const Cy = Ay - acPx * Math.sin(angA);
  const CAux = (Ax - Cx) / acPx, CAuy = (Ay - Cy) / acPx;
  const CBdist = Math.sqrt((Bx - Cx) ** 2 + (By - Cy) ** 2);
  const CBux = (Bx - Cx) / CBdist, CBuy = (By - Cy) / CBdist;
  const arcR = 11;
  const arcStartX = Cx + arcR * CAux, arcStartY = Cy + arcR * CAuy;
  const arcEndX   = Cx + arcR * CBux, arcEndY   = Cy + arcR * CBuy;
  const arcSweep  = (CAux * CBuy - CAuy * CBux) > 0 ? 1 : 0;
  const midDX = CAux + CBux, midDY = CAuy + CBuy;
  const midDLen = Math.sqrt(midDX * midDX + midDY * midDY);
  const dotX = Cx + (arcR * 0.65) * midDX / midDLen;
  const dotY = Cy + (arcR * 0.65) * midDY / midDLen;
  const acMidX = (Ax + Cx) / 2, acMidY = (Ay + Cy) / 2;
  const cbMidX = (Cx + Bx) / 2, cbMidY = (Cy + By) / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy}`} fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />
      <path d={`M ${arcStartX},${arcStartY} A ${arcR},${arcR} 0 0,${arcSweep} ${arcEndX},${arcEndY}`} fill="none" stroke="#374151" strokeWidth={1.4} />
      <circle cx={dotX} cy={dotY} r={1.8} fill="#374151" />
      <text x={acMidX - 18} y={(acMidY + Ay) / 2 - 4} fontSize={13} fill="#374151" fontWeight="600" textAnchor="middle">{AC}</text>
      <text x={cbMidX + 14} y={(cbMidY + Cy) / 2} fontSize={13} fill="#374151" fontWeight="600" textAnchor="middle">{CB}</text>
      <circle cx={Ax} cy={Ay} r={3} fill="#374151" />
      <circle cx={Bx} cy={By} r={3} fill="#374151" />
      <circle cx={Cx} cy={Cy} r={3} fill="#374151" />
      <text x={Ax - 16} y={Ay + 6}  fontSize={14} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 6}  y={By + 6}  fontSize={14} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx - 4}  y={Cy - 10} fontSize={14} fill="#1e40af" fontWeight="700">C</text>
    </svg>
  );
};

// ─── ParallelogramABCDDiagram ──────────────────────────────────────────────────
// Fixed geometry: ∠BAD=45°, ∠BAC=15°, ∠DAC=30°
// Constructions: altitude DK ⊥ AB, diagonal AC, D→H→L where DL ⊥ AC

export const ParallelogramABCDDiagram: React.FC<{ config: ParallelogramABCDConfig; demo?: boolean }> = ({ config }) => {
  const { m, n } = config;
  const W = 500, H = 300;
  // Hard-coded pixel coordinates for ∠BAD=45°, ∠BAC=15°
  const Ax = 55,  Ay = 250;
  const Bx = 320, By = 250;
  const Dx = 152, Dy = 153;   // A + AD*(cos45°, -sin45°)
  const Cx = 417, Cy = 153;   // B + (D-A)
  const Kx = 152, Ky = 250;   // foot of D on AB
  const Fx = 152, Fy = 224;   // DK ∩ AC
  const Hx = 170, Hy = 219;   // foot of D on AC
  const Lx = 178, Ly = 250;   // DL ∩ AB

  const rightAngle = (ox: number, oy: number, ax: number, ay: number, bx: number, by: number, sz = 7) => {
    const lenA = Math.hypot(ax - ox, ay - oy);
    const lenB = Math.hypot(bx - ox, by - oy);
    const uax = (ax - ox) / lenA * sz, uay = (ay - oy) / lenA * sz;
    const ubx = (bx - ox) / lenB * sz, uby = (by - oy) / lenB * sz;
    return `M ${ox + uax},${oy + uay} L ${ox + uax + ubx},${oy + uay + uby} L ${ox + ubx},${oy + uby}`;
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily="sans-serif">
      {/* Parallelogram */}
      <polygon points={`${Ax},${Ay} ${Bx},${By} ${Cx},${Cy} ${Dx},${Dy}`}
        fill="#f0f9ff" stroke="#1e40af" strokeWidth={1.8} />
      {/* Diagonal AC */}
      <line x1={Ax} y1={Ay} x2={Cx} y2={Cy} stroke="#6b7280" strokeWidth={1.3} strokeDasharray="5,3" />
      {/* Altitude DK */}
      <line x1={Dx} y1={Dy} x2={Kx} y2={Ky} stroke="#059669" strokeWidth={1.6} />
      {/* Right angle at K */}
      <path d={rightAngle(Kx, Ky, Kx - 1, Ky - 10, Kx + 10, Ky)} fill="none" stroke="#059669" strokeWidth={1.2} />
      {/* Line D→H extended to L (perpendicular to AC) */}
      <line x1={Dx} y1={Dy} x2={Lx} y2={Ly} stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4,3" />
      {/* Right angle at H: arc+dot between AC direction and DL direction */}
      {(() => {
        const arcR = 10;
        // Unit vector along AC (A→C)
        const acLen = Math.hypot(Cx - Ax, Cy - Ay);
        const acUx = (Cx - Ax) / acLen, acUy = (Cy - Ay) / acLen;
        // Unit vector along DL away from H toward D
        const dlLen = Math.hypot(Dx - Lx, Dy - Ly);
        const dlUx = (Dx - Lx) / dlLen, dlUy = (Dy - Ly) / dlLen;
        // Arc start: H + arcR along AC direction (toward C)
        const sx = Hx + arcR * acUx, sy = Hy + arcR * acUy;
        // Arc end: H + arcR along DL direction (toward D)
        const ex = Hx + arcR * dlUx, ey = Hy + arcR * dlUy;
        // Dot at midpoint of the two arm tips
        const dotX = Hx + (arcR * 0.65) * (acUx + dlUx);
        const dotY = Hy + (arcR * 0.65) * (acUy + dlUy);
        return (
          <g>
            <path d={`M ${sx.toFixed(2)},${sy.toFixed(2)} A ${arcR},${arcR} 0 0,0 ${ex.toFixed(2)},${ey.toFixed(2)}`}
              fill="none" stroke="#dc2626" strokeWidth={1.3} />
            <circle cx={dotX} cy={dotY} r={2} fill="#dc2626" />
          </g>
        );
      })()}
      {/* m label on AF segment — offset below the diagonal */}
      {(() => {
        const acLen = Math.hypot(Cx - Ax, Cy - Ay);
        const perpX = -(Cy - Ay) / acLen, perpY = (Cx - Ax) / acLen; // perpendicular pointing "below" AC
        const mx = (Ax + Fx) / 2 + perpX * 14, my = (Ay + Fy) / 2 + perpY * 14;
        const angleDeg = Math.atan2(Cy - Ay, Cx - Ax) * 180 / Math.PI;
        return (
          <text x={mx} y={my} fontSize={12} fill="#7c3aed" fontWeight="700" textAnchor="middle"
            transform={`rotate(${angleDeg.toFixed(1)},${mx.toFixed(1)},${my.toFixed(1)})`}>
            m={m}
          </text>
        );
      })()}
      {/* n label on HC segment — offset above the diagonal */}
      {(() => {
        const acLen = Math.hypot(Cx - Ax, Cy - Ay);
        const perpX = (Cy - Ay) / acLen, perpY = -(Cx - Ax) / acLen; // perpendicular pointing "above" AC
        const mx = (Hx + Cx) / 2 + perpX * 14, my = (Hy + Cy) / 2 + perpY * 14;
        const angleDeg = Math.atan2(Cy - Ay, Cx - Ax) * 180 / Math.PI;
        return (
          <text x={mx} y={my} fontSize={12} fill="#7c3aed" fontWeight="700" textAnchor="middle"
            transform={`rotate(${angleDeg.toFixed(1)},${mx.toFixed(1)},${my.toFixed(1)})`}>
            n={n}
          </text>
        );
      })()}
      {/* Vertex labels */}
      <text x={Ax - 16} y={Ay + 6}  fontSize={13} fill="#1e40af" fontWeight="700">A</text>
      <text x={Bx + 5}  y={By + 6}  fontSize={13} fill="#1e40af" fontWeight="700">B</text>
      <text x={Cx + 5}  y={Cy - 5}  fontSize={13} fill="#1e40af" fontWeight="700">C</text>
      <text x={Dx - 16} y={Dy - 5}  fontSize={13} fill="#1e40af" fontWeight="700">D</text>
      {/* Construction point labels */}
      <text x={Kx - 14} y={Ky + 14} fontSize={11} fill="#059669" fontWeight="600">K</text>
      <text x={Fx - 12} y={Fy - 5}  fontSize={11} fill="#374151">F</text>
      <text x={Hx + 4}  y={Hy - 6}  fontSize={11} fill="#dc2626" fontWeight="600">H</text>
      <text x={Lx + 4}  y={Ly + 14} fontSize={11} fill="#dc2626" fontWeight="600">L</text>
      {/* Dots at key points */}
      {[{x:Kx,y:Ky},{x:Fx,y:Fy},{x:Hx,y:Hy},{x:Lx,y:Ly}].map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#374151" />
      ))}
    </svg>
  );
};

// ─── Dispatcher ────────────────────────────────────────────────────────────────

export type NvoDiagramConfig = Record<string, unknown>;

export function renderNvoDiagram(type: string, config: NvoDiagramConfig): React.ReactNode {
  switch (type) {
    // Blueprint-generated questions send `diagram_type: 'scene'` and carry a
    // declarative scene spec in the config, drawn by one renderer. The
    // hand-written components below stay for questions the old catalog
    // generator still produces, so both paths work during the migration.
    case 'scene':
      return <SceneRenderer scene={config as unknown as Scene} />;
    case 'RhombusCOMDiagram':
      return <RhombusCOMDiagram config={config as RhombusCOMConfig} />;
    case 'IntersectLinesDiagram':
      return <IntersectLinesDiagram config={config as IntersectLinesConfig} />;
    case 'ExtAngBDiagram':
      return <ExtAngBDiagram config={config as ExtAngBConfig} />;
    case 'IsoscAltDiagram':
      return <IsoscAltDiagram config={config as IsoscAltConfig} />;
    case 'PerpBisecBCDiagram':
      return <PerpBisecBCDiagram config={config as PerpBisecBCConfig} />;
    case 'ParallelDLDiagram':
      return <ParallelDLDiagram config={config as ParallelDLConfig} />;
    case 'BoxVolumeDiagram':
      return <BoxVolumeDiagram config={config as BoxVolumeConfig} />;
    case 'RightTriABDiagram':
      return <RightTriABDiagram config={config as RightTriABConfig} />;
    case 'ParallelogramABCDDiagram':
      return <ParallelogramABCDDiagram config={config as ParallelogramABCDConfig} />;
    case 'CongrTriDiagram':
      return <CongrTriDiagram config={config as CongrTriConfig} />;
    case 'PerpBisecCMDiagram':
      return <PerpBisecCMDiagram config={config as PerpBisecCMConfig} />;
    case 'RightTriPerimDiagram':
      return <RightTriPerimDiagram config={config as RightTriPerimConfig} />;
    default:
      return null;
  }
}
