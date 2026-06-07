/** Hashing helpers using WebCrypto (available on desktop + mobile). */

function toHex(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, '0');
  return s;
}

/** Copy into a fresh ArrayBuffer so WebCrypto gets a non-shared BufferSource. */
function toAB(input: ArrayBuffer | Uint8Array): ArrayBuffer {
  if (input instanceof Uint8Array) {
    const ab = new ArrayBuffer(input.byteLength);
    new Uint8Array(ab).set(input);
    return ab;
  }
  return input;
}

export async function sha1Hex(input: ArrayBuffer | Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-1', toAB(input));
  return toHex(new Uint8Array(digest));
}

export async function sha256Hex(input: string | Uint8Array): Promise<string> {
  const bytes = typeof input === 'string' ? new TextEncoder().encode(input) : input;
  const digest = await crypto.subtle.digest('SHA-256', toAB(bytes));
  return toHex(new Uint8Array(digest));
}
