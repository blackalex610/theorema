import { describe, expect, it } from 'vitest';
import { MAX_IMAGE_EDGE, isHeicFile, isImageFile, scaledDimensions } from './imageCapture';

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

describe('scaledDimensions', () => {
  it('leaves images at or under the limit alone', () => {
    expect(scaledDimensions(1600, 1200)).toEqual({ width: 1600, height: 1200 });
    expect(scaledDimensions(800, 600)).toEqual({ width: 800, height: 600 });
  });

  it('scales a 12 MP phone capture down to the longest-edge limit', () => {
    expect(scaledDimensions(4032, 3024)).toEqual({ width: MAX_IMAGE_EDGE, height: 1200 });
  });

  it('scales portrait captures by their height', () => {
    expect(scaledDimensions(3024, 4032)).toEqual({ width: 1200, height: MAX_IMAGE_EDGE });
  });

  it('never produces a zero-pixel side', () => {
    expect(scaledDimensions(10000, 2)).toEqual({ width: MAX_IMAGE_EDGE, height: 1 });
  });
});
