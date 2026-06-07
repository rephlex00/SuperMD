/**
 * Rendering helpers that turn decoded grayscale page buffers into things Obsidian
 * can use: data URLs for the LLM, PNG bytes for vault attachments, and <img>
 * elements for the inline embed renderer and the file viewer.
 *
 * Uses the renderer's Canvas APIs (available on desktop Electron and mobile
 * webview); keep this module out of unit tests (no DOM there).
 */
import { decodePageToGray } from './compositor';
import { DecodedBitmap } from './decoders/rattaRle';
import { parseNote } from './parser';
import { ParsedNote } from './fileformat';

export interface RenderedPage {
  /** JPEG/PNG data URL suitable for an LLM image_url payload. */
  dataUrl: string;
  width: number;
  height: number;
}

function grayToCanvas(gray: DecodedBitmap): HTMLCanvasElement {
  const { width, height, data } = gray;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('2D canvas context unavailable');
  const imageData = ctx.createImageData(width, height);
  const rgba = imageData.data;
  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    const o = i * 4;
    rgba[o] = v;
    rgba[o + 1] = v;
    rgba[o + 2] = v;
    rgba[o + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

function downscale(src: HTMLCanvasElement, maxEdge: number): HTMLCanvasElement {
  const scale = Math.min(1, maxEdge / Math.max(src.width, src.height));
  if (scale >= 1) return src;
  const dst = document.createElement('canvas');
  dst.width = Math.max(1, Math.round(src.width * scale));
  dst.height = Math.max(1, Math.round(src.height * scale));
  const ctx = dst.getContext('2d');
  if (!ctx) return src;
  ctx.drawImage(src, 0, 0, dst.width, dst.height);
  return dst;
}

/** Decode + downscale a page to a data URL for the LLM (JPEG keeps payloads small). */
export function pageToDataUrl(
  note: ParsedNote,
  pageIndex: number,
  maxEdge = 1568,
  type = 'image/jpeg',
  quality = 0.85,
): RenderedPage {
  const canvas = downscale(grayToCanvas(decodePageToGray(note, pageIndex)), maxEdge);
  return { dataUrl: canvas.toDataURL(type, quality), width: canvas.width, height: canvas.height };
}

/** Decode a page to lossless PNG bytes for writing a vault attachment. */
export function pageToPngBytes(note: ParsedNote, pageIndex: number): Promise<Uint8Array> {
  const canvas = grayToCanvas(decodePageToGray(note, pageIndex));
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('canvas.toBlob returned null'));
        return;
      }
      blob.arrayBuffer().then((ab) => resolve(new Uint8Array(ab)), reject);
    }, 'image/png');
  });
}

/** Decode every page of a `.note` to <img> elements (for the viewer / embed). */
export function renderNoteToImages(bytes: ArrayBuffer | Uint8Array, maxEdge = 1872): HTMLImageElement[] {
  const note = parseNote(bytes);
  const out: HTMLImageElement[] = [];
  for (let i = 0; i < note.pages.length; i++) {
    const canvas = downscale(grayToCanvas(decodePageToGray(note, i)), maxEdge);
    const img = new Image();
    img.src = canvas.toDataURL('image/png');
    out.push(img);
  }
  return out;
}
