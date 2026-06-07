/**
 * FlateDecoder — SN_ASA_COMPRESS protocol. Ported from supernotelib/decoder.py.
 *
 * zlib-inflate the data, interpret as uint16, reshape (1404 x 1888), rotate 90°
 * clockwise, drop the bottom 16 rows, and remap color codes to grayscale.
 */
import pako from 'pako';
import { GrayPalette } from '../color';
import { DecodedBitmap } from './rattaRle';

const INTERNAL_WIDTH = 1404; // INTERNAL_PAGE_WIDTH
const INTERNAL_HEIGHT = 1888; // INTERNAL_PAGE_HEIGHT
const CROP_HEIGHT = 1872; // after dropping the bottom 16 rows

const COLORCODE_BLACK = 0x0000;
const COLORCODE_BACKGROUND = 0xffff;
const COLORCODE_DARK_GRAY = 0x2104;
const COLORCODE_GRAY = 0xe1e2;

export function decodeFlate(data: Uint8Array, palette: GrayPalette): DecodedBitmap {
  const inflated = pako.inflate(data);
  const u16 = new Uint16Array(
    inflated.buffer,
    inflated.byteOffset,
    Math.floor(inflated.byteLength / 2),
  );

  const W = INTERNAL_WIDTH;
  const Hfull = INTERNAL_HEIGHT;
  const Hc = CROP_HEIGHT;
  const out = new Uint8Array(W * Hc);

  // Output pixel (x, y) maps to the clockwise-rotated source index:
  //   src = (W - 1 - x) * Hfull + y      (numpy reshape(1404,1888) + rot90 CW)
  for (let y = 0; y < Hc; y++) {
    const rowBase = y * W;
    for (let x = 0; x < W; x++) {
      const v = u16[(W - 1 - x) * Hfull + y];
      let g: number;
      switch (v) {
        case COLORCODE_BLACK:
          g = palette.black;
          break;
        case COLORCODE_DARK_GRAY:
          g = palette.darkgray;
          break;
        case COLORCODE_GRAY:
          g = palette.gray;
          break;
        case COLORCODE_BACKGROUND:
        default:
          g = palette.white;
          break;
      }
      out[rowBase + x] = g;
    }
  }

  return { width: W, height: Hc, data: out };
}
