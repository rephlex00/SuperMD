/**
 * RattaRleDecoder (+ X2 variant) — RATTA_RLE protocol.
 * Faithful port of supernotelib/decoder.py (RattaRleDecoder / RattaRleX2Decoder).
 *
 * Produces an 8-bit grayscale buffer. Background maps to `palette.transparent`
 * (0xff) so layers composite correctly; unknown color codes pass through as their
 * raw byte value (matching the Python fallback).
 */
import { GrayPalette } from '../color';

export interface DecodedBitmap {
  width: number;
  height: number;
  data: Uint8Array;
}

export type ColorMap = Record<number, number>;

const SPECIAL_LENGTH_MARKER = 0xff;
const SPECIAL_LENGTH = 0x4000;
const SPECIAL_LENGTH_FOR_BLANK = 0x400;

/** Build the code→gray map for the X-series (`x2=false`) or X2-series decoder. */
export function buildColorMap(palette: GrayPalette, x2: boolean): ColorMap {
  if (!x2) {
    return {
      0x61: palette.black, // BLACK
      0x62: palette.transparent, // BACKGROUND
      0x63: palette.darkgray, // DARK_GRAY
      0x64: palette.gray, // GRAY
      0x65: palette.white, // WHITE
      0x66: palette.black, // MARKER_BLACK
      0x67: palette.darkgray, // MARKER_DARK_GRAY
      0x68: palette.gray, // MARKER_GRAY
    };
  }
  return {
    0x61: palette.black,
    0x62: palette.transparent,
    0x65: palette.white,
    0x66: palette.black,
    0x9d: palette.darkgray, // DARK_GRAY (X2)
    0xc9: palette.gray, // GRAY (X2)
    0x9e: palette.darkgray, // MARKER_DARK_GRAY (X2)
    0xca: palette.gray, // MARKER_GRAY (X2)
    0x63: palette.darkgray_compat, // X-series compatibility
    0x64: palette.gray_compat,
  };
}

function adjustTailLength(tailLength: number, currentLength: number, totalLength: number): number {
  const gap = totalLength - currentLength;
  for (let i = 7; i >= 0; i--) {
    const l = ((tailLength & 0x7f) + 1) << i;
    if (l <= gap) return l;
  }
  return 0;
}

export function decodeRattaRle(
  data: Uint8Array,
  pageWidth: number,
  pageHeight: number,
  colormap: ColorMap,
  allBlank: boolean,
  horizontal: boolean,
): DecodedBitmap {
  let width = pageWidth;
  let height = pageHeight;
  if (horizontal) {
    const t = width;
    width = height;
    height = t;
  }
  const expected = width * height;
  const out = new Uint8Array(expected);
  let pos = 0;

  const emit = (code: number, length: number): void => {
    const g = colormap[code] !== undefined ? colormap[code] : code & 0xff;
    const end = Math.min(pos + length, expected);
    for (let k = pos; k < end; k++) out[k] = g;
    pos += length;
  };

  const waiting: Array<[number, number]> = [];
  let holder: [number, number] | null = null;
  let i = 0;

  while (i + 1 < data.length) {
    const colorcode = data[i++];
    let length = data[i++];
    let dataPushed = false;

    if (holder) {
      const prevColor: number = holder[0];
      const prevLength: number = holder[1];
      holder = null;
      if (colorcode === prevColor) {
        length = 1 + length + (((prevLength & 0x7f) + 1) << 7);
        waiting.push([colorcode, length]);
        dataPushed = true;
      } else {
        const pl = ((prevLength & 0x7f) + 1) << 7;
        waiting.push([prevColor, pl]);
      }
    }

    if (!dataPushed) {
      if (length === SPECIAL_LENGTH_MARKER) {
        length = allBlank ? SPECIAL_LENGTH_FOR_BLANK : SPECIAL_LENGTH;
        waiting.push([colorcode, length]);
        dataPushed = true;
      } else if ((length & 0x80) !== 0) {
        holder = [colorcode, length];
      } else {
        length += 1;
        waiting.push([colorcode, length]);
        dataPushed = true;
      }
    }

    while (waiting.length) {
      const [c, l] = waiting.shift() as [number, number];
      emit(c, l);
    }
  }

  if (holder) {
    const adjusted = adjustTailLength(holder[1], pos, expected);
    if (adjusted > 0) emit(holder[0], adjusted);
  }

  // Python raises on length mismatch; we leave any shortfall as 0 (black) and
  // ignore overflow (clamped in emit) so a slightly malformed page still renders.
  return { width, height, data: out };
}
