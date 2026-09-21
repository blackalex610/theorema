import { describe, expect, it } from 'vitest';
import { isHeicFile, isImageFile } from './imageCapture';

const file = (name: string, type: string) => new File([new Uint8Array([1, 2, 3])], name, { type });

describe('imageCapture detection', () => {
  it('accepts images by MIME type', () => {
    expect(isImageFile(file('a.png', 'image/png'))).toBe(true);
    expect(isImageFile(file('a.jpg', 'image/jpeg'))).toBe(true);
  });

  it('accepts images by extension when the MIME type is missing', () => {
    // iOS routinely hands over an empty type for camera captures.
    expect(isImageFile(file('IMG_0001.HEIC', ''))).toBe(true);
    expect(isImageFile(file('photo.JPG', ''))).toBe(true);
  });

  it('rejects non-images', () => {
    expect(isImageFile(file('notes.pdf', 'application/pdf'))).toBe(false);
    expect(isImageFile(file('data', ''))).toBe(false);
  });

  it('detects HEIC by both MIME type and extension', () => {
    expect(isHeicFile(file('a.heic', ''))).toBe(true);
    expect(isHeicFile(file('a.HEIF', ''))).toBe(true);
    expect(isHeicFile(file('a.jpg', 'image/heif'))).toBe(true);
    expect(isHeicFile(file('a.jpg', 'image/jpeg'))).toBe(false);
  });
});
