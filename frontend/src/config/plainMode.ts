/**
 * Plain mode: strips the visual design so screens can be worked on bare.
 *
 * Flip this to `false` (or set VITE_PLAIN_UI=false) to get the real design
 * back. Nothing else needs changing — the styling lives entirely in
 * src/styles/plain.css, scoped to a class this flag puts on <html>, and no
 * page or component was edited to make it work.
 */
export const PLAIN_UI = import.meta.env.VITE_PLAIN_UI !== 'false';
