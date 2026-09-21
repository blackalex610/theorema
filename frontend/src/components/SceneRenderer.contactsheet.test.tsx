/**
 * Contact sheet for the NVO figure renderer.
 *
 * Not an assertion suite — a way to *look* at every figure template at once
 * when adding or changing one, because a scene spec that verifies cleanly can
 * still draw a label off the edge of the box or a foot of a perpendicular on
 * top of a vertex. Both of those shipped and were caught this way.
 *
 * Skipped unless both paths are supplied, so a normal `vitest run` stays quiet:
 *
 *   # 1. dump one sample scene per template
 *   cd backend && python -c "..."   # see docs/nvo-generation.md
 *   # 2. render them
 *   SCENES_JSON=/abs/scenes.json SCENES_HTML=/abs/scenes.html \
 *     npx vitest run src/components/SceneRenderer.contactsheet.test.tsx
 *   # 3. open scenes.html
 *
 * KaTeX renders in an effect, so table cells come out unstyled here. That is a
 * limitation of static markup, not of the renderer.
 */
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import fs from 'node:fs';
import path from 'node:path';
import SceneRenderer, { type Scene } from './SceneRenderer';

const IN = process.env.SCENES_JSON;
const OUT = process.env.SCENES_HTML;

describe('scene contact sheet', () => {
  it.skipIf(!IN || !OUT)('renders every figure template to an HTML sheet', () => {
    const items: { title: string; stem: string; scene: Scene }[] =
      JSON.parse(fs.readFileSync(IN!, 'utf-8'));

    const cards = items.map((it) => {
      const svg = renderToStaticMarkup(<SceneRenderer scene={it.scene} />);
      return `<figure><figcaption><b>${it.title}</b><br><span>${
        it.stem.replace(/</g, '&lt;')
      }</span></figcaption>${svg}</figure>`;
    });

    fs.mkdirSync(path.dirname(OUT!), { recursive: true });
    fs.writeFileSync(
      OUT!,
      `<!doctype html><meta charset="utf-8">
<style>
 body{font:13px system-ui;background:#fff;color:#111;margin:0;padding:18px}
 h1{font:600 17px system-ui;margin:0 0 14px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
 figure{margin:0;border:1px solid #ccc;border-radius:6px;padding:8px;background:#fff}
 figcaption{font-size:11px;color:#444;margin-bottom:4px;min-height:44px}
 figcaption b{color:#0a4;font-family:ui-monospace,monospace}
 svg{color:#111}
</style>
<h1>NVO scene renderer — ${items.length} figure templates</h1>
<div class="grid">${cards.join('\n')}</div>`,
      'utf-8'
    );

    expect(cards.length).toBeGreaterThan(0);
  });
});
