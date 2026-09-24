/**
 * Upload-channel ids for phone pairing.
 *
 * The channel id is the only thing that scopes a pairing channel: whoever
 * holds it can follow that channel's upload stream. It used to come from
 * Math.random() (not a cryptographic source) plus a timestamp; it is now 128
 * bits from the platform CSPRNG. The shape stays inside the backend's
 * `^[a-zA-Z0-9_-]{8,64}$` channel-id check.
 */
export const generateChannelId = (): string => {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `ch_${hex}`;
};

export const isStrongChannelId = (value: string): boolean => /^ch_[0-9a-f]{32}$/.test(value);
