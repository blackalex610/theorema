const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.heic', '.heif'];

const HEIC_TIMEOUT_MS = 30_000;
const STANDARD_TIMEOUT_MS = 10_000;

/** iOS often reports an empty MIME type for camera captures, so check both. */
export const isImageFile = (file: File): boolean => {
  if ((file.type || '').startsWith('image/')) return true;
  const name = file.name.toLowerCase();
  return IMAGE_EXTENSIONS.some((ext) => name.endsWith(ext));
};

export const isHeicFile = (file: File): boolean => {
  const type = file.type || '';
  if (type === 'image/heic' || type === 'image/heif') return true;
  const name = file.name.toLowerCase();
  return name.endsWith('.heic') || name.endsWith('.heif');
};

/**
 * Longest edge, in pixels, of any photo we send anywhere.
 *
 * Phones capture at 12+ MP; re-encoded at full size that is a 3-5 MB JPEG,
 * ~33% more as a base64 data URL. Several of those in one NVO submission
 * blew straight through Vercel's 4.5 MB request-body limit (a 413 before the
 * backend ever saw the exam), and a restored exam's saved state overran the
 * ~5 MB localStorage quota. OpenAI vision never looks past ~2048 px anyway
 * (then scales the short side to 768 px), so this loses the grader nothing.
 */
export const MAX_IMAGE_EDGE = 1600;
export const JPEG_QUALITY = 0.85;

export const scaledDimensions = (
  width: number,
  height: number,
  maxEdge: number = MAX_IMAGE_EDGE
): { width: number; height: number } => {
  const longest = Math.max(width, height);
  if (longest <= maxEdge || longest === 0) return { width, height };
  const scale = maxEdge / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
};

const canvasFromBlob = (blob: Blob): Promise<HTMLCanvasElement> =>
  new Promise((resolve, reject) => {
    const image = new Image();
    const blobUrl = URL.createObjectURL(blob);
    image.onload = () => {
      const canvas = document.createElement('canvas');
      const { width, height } = scaledDimensions(image.width, image.height);
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      URL.revokeObjectURL(blobUrl);
      if (!context) {
        reject(new Error('Could not get canvas context'));
        return;
      }
      context.drawImage(image, 0, 0, width, height);
      resolve(canvas);
    };
    image.onerror = () => {
      URL.revokeObjectURL(blobUrl);
      reject(new Error('Failed to load image'));
    };
    image.src = blobUrl;
  });

const toCanvas = async (file: File): Promise<HTMLCanvasElement> => {
  if (isHeicFile(file)) {
    // Loaded on demand: heic2any touches browser globals at module scope (it
    // throws outright under jsdom), and only iOS users ever need it — so a
    // static import would both break tests and ship ~1 MB to everyone else.
    const { default: heic2any } = await import('heic2any');
    const converted = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.95 });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return canvasFromBlob(blob as Blob);
  }
  const effectiveMime = file.type && file.type.startsWith('image/') ? file.type : 'image/jpeg';
  return canvasFromBlob(new Blob([file], { type: effectiveMime }));
};

const withTimeout = async <T>(file: File, work: (canvas: HTMLCanvasElement) => T | Promise<T>): Promise<T> => {
  if (!isImageFile(file)) throw new Error('Файлът не е изображение');

  const timeoutMs = isHeicFile(file) ? HEIC_TIMEOUT_MS : STANDARD_TIMEOUT_MS;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`Обработката на снимката отне твърде дълго (${timeoutMs} ms)`)),
      timeoutMs
    );
  });

  try {
    const canvas = await Promise.race([toCanvas(file), timeout]);
    return await work(canvas);
  } finally {
    if (timer) clearTimeout(timer);
  }
};

/**
 * Normalise any camera capture to a downscaled JPEG data URL.
 *
 * Everything is re-encoded, not just HEIC: it is the only way to get a
 * predictable MIME type and size out of the range of formats phones produce.
 */
export const fileToJpegDataUrl = (file: File): Promise<string> =>
  withTimeout(file, (canvas) => canvas.toDataURL('image/jpeg', JPEG_QUALITY));

/** The same normalisation, as a File for multipart uploads. */
export const fileToJpegFile = (file: File): Promise<File> =>
  withTimeout(
    file,
    (canvas) =>
      new Promise<File>((resolve, reject) => {
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error('Снимката не можа да бъде обработена'));
              return;
            }
            const base = file.name.replace(/\.[^.]+$/, '') || 'photo';
            resolve(new File([blob], `${base}.jpg`, { type: 'image/jpeg' }));
          },
          'image/jpeg',
          JPEG_QUALITY
        );
      })
  );
