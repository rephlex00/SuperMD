import { describe, expect, it } from 'vitest';
import { buildColorMap, decodeRattaRle } from '../src/note/decoders/rattaRle';
import { DEFAULT_GRAY_PALETTE } from '../src/note/color';

const cm = buildColorMap(DEFAULT_GRAY_PALETTE, false);

describe('RattaRle decoder', () => {
  it('expands a simple (colorcode, length) run', () => {
    // 0x61 = black, length byte 0x03 → emit length+1 = 4 black pixels.
    const out = decodeRattaRle(new Uint8Array([0x61, 0x03]), 2, 2, cm, false, false);
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(Array.from(out.data)).toEqual([0x00, 0x00, 0x00, 0x00]);
  });

  it('maps background to transparent', () => {
    // 0x62 = background → transparent (0xff), length 0x03 → 4 px.
    const out = decodeRattaRle(new Uint8Array([0x62, 0x03]), 2, 2, cm, false, false);
    expect(Array.from(out.data)).toEqual([0xff, 0xff, 0xff, 0xff]);
  });

  it('swaps dimensions when horizontal', () => {
    const out = decodeRattaRle(new Uint8Array([0x61, 0x05]), 2, 3, cm, false, true);
    expect(out.width).toBe(3);
    expect(out.height).toBe(2);
  });
});
