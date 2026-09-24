import { describe, expect, it } from 'vitest';
import { generateChannelId, isStrongChannelId } from './channelId';

describe('generateChannelId', () => {
  it('fits the backend channel-id pattern', () => {
    expect(generateChannelId()).toMatch(/^[a-zA-Z0-9_-]{8,64}$/);
  });

  it('carries 128 bits of randomness', () => {
    expect(generateChannelId()).toMatch(/^ch_[0-9a-f]{32}$/);
  });

  it('does not repeat', () => {
    const ids = new Set(Array.from({ length: 200 }, generateChannelId));
    expect(ids.size).toBe(200);
  });
});

describe('isStrongChannelId', () => {
  it('accepts generated ids and rejects the old Math.random format', () => {
    expect(isStrongChannelId(generateChannelId())).toBe(true);
    expect(isStrongChannelId('ch_m1x2y3z4abcdefghij')).toBe(false);
    expect(isStrongChannelId('')).toBe(false);
  });
});
