import { describe, expect, it } from 'vitest';
import { isBlockCode } from './markdown';

describe('isBlockCode', () => {
  it('treats inline code as inline', () => {
    // react-markdown v10 dropped the `inline` prop; the old renderers
    // therefore drew every inline `x` as a full code block.
    expect(isBlockCode(undefined, 'x = 2')).toBe(false);
  });

  it('treats fenced code with a language as a block', () => {
    expect(isBlockCode('language-python', 'print(1)')).toBe(true);
  });

  it('treats multi-line fenced code without a language as a block', () => {
    expect(isBlockCode(undefined, 'a = 1\nb = 2\n')).toBe(true);
  });
});
