import type { ReactNode } from 'react';

/**
 * Whether a react-markdown `code` element is a fenced block rather than
 * inline code. react-markdown v9+ stopped passing an `inline` prop, so the
 * renderers that branched on it rendered every inline `x` as a full block.
 * Fenced blocks carry a language class or span lines; inline code does neither.
 */
export const isBlockCode = (className: string | undefined, children: ReactNode): boolean =>
  /\blanguage-/.test(className ?? '') || String(children).includes('\n');
