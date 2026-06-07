import { describe, expect, it } from 'vitest';
import { base64ToString, base64ToUint8, uint8ToBase64 } from '../src/util/base64';

describe('base64', () => {
  it('round-trips bytes', () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 251, 252, 253, 254, 255]);
    expect(Array.from(base64ToUint8(uint8ToBase64(bytes)))).toEqual(Array.from(bytes));
  });

  it('decodes a known string', () => {
    // "Note/file.note" base64-encoded (as Supernote link paths are stored).
    const b64 = uint8ToBase64(new TextEncoder().encode('Note/file.note'));
    expect(base64ToString(b64)).toBe('Note/file.note');
  });
});
