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

const canvasFromBlob = (blob: Blob): Promise<HTMLCanvasElement> =>
  new Promise((resolve, reject) => {
    const image = new Image();
    const blobUrl = URL.createObjectURL(blob);
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext('2d');
      URL.revokeObjectURL(blobUrl);
      if (!context) {
        reject(new Error('Could not get canvas context'));
        return;
      }
      context.drawImage(image, 0, 0);
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

/**
 * Normalise any camera capture to a JPEG data URL.
 *
 * Everything is re-encoded, not just HEIC: it is the only way to get a
 * predictable MIME type and size out of the range of formats phones produce.
 */
export const fileToJpegDataUrl = async (file: File): Promise<string> => {
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
    return canvas.toDataURL('image/jpeg', 0.95);
  } finally {
    if (timer) clearTimeout(timer);
  }
};
