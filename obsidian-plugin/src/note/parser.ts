/**
 * Pure-TS port of supernotelib/parser.py — parses a `.note` binary into a
 * structured ParsedNote (pages, layers, bitmap byte ranges, metadata).
 *
 * Supports the X-series format (`SN_FILE_VER_*`, layered) and the original
 * format (`SN_FILE_ASA_*`, non-layered).
 */
import {
  A5X2_PAGE_HEIGHT,
  A5X2_PAGE_WIDTH,
  LAYER_KEYS,
  LENGTH_FIELD_SIZE,
  ORIENTATION_VERTICAL,
  PAGE_HEIGHT,
  PAGE_WIDTH,
  Params,
  ParsedKeyword,
  ParsedLayer,
  ParsedLink,
  ParsedNote,
  ParsedPage,
} from './fileformat';
import { base64ToString } from '../util/base64';

const X_SIGNATURE_OFFSET = 4;
const X_SIGNATURE_RE = /^SN_FILE_VER_\d{8}/;
const ORIG_SIGNATURE_RE = /^SN_FILE_ASA_\d{8}/;

const latin1 = new TextDecoder('latin1');
const utf8 = new TextDecoder('utf-8', { fatal: false });

export class UnsupportedFileFormat extends Error {}

function u32(buf: Uint8Array, off: number): number {
  return (buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16) | buf[off + 3] * 0x1000000) >>> 0;
}

/** Read a length-prefixed block: 4-byte LE length, then that many bytes. */
function readBlock(buf: Uint8Array, address: number): Uint8Array | null {
  if (!address || address <= 0 || address + LENGTH_FIELD_SIZE > buf.length) return null;
  const len = u32(buf, address);
  const start = address + LENGTH_FIELD_SIZE;
  return buf.subarray(start, Math.min(start + len, buf.length));
}

function extractParameters(text: string): Params {
  const params: Params = {};
  const re = /<([^:<>]+):([^:<>]*)>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const key = m[1];
    const value = m[2];
    const existing = params[key];
    if (existing !== undefined) {
      if (Array.isArray(existing)) existing.push(value);
      else params[key] = [existing, value];
    } else {
      params[key] = value;
    }
  }
  return params;
}

function parseMetadataBlock(buf: Uint8Array, address: number): Params {
  const block = readBlock(buf, address);
  if (!block) return {};
  return extractParameters(utf8.decode(block));
}

function str(params: Params, key: string): string | undefined {
  const v = params[key];
  if (v === undefined) return undefined;
  return Array.isArray(v) ? v[0] : v;
}

function asList(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

function detectSignature(buf: Uint8Array): { signature: string; isX: boolean } {
  const xSig = latin1.decode(buf.subarray(X_SIGNATURE_OFFSET, X_SIGNATURE_OFFSET + 20));
  if (X_SIGNATURE_RE.test(xSig)) return { signature: xSig.slice(0, 20), isX: true };
  const oSig = latin1.decode(buf.subarray(0, 20));
  if (ORIG_SIGNATURE_RE.test(oSig)) return { signature: oSig.slice(0, 20), isX: false };
  throw new UnsupportedFileFormat('unknown .note signature');
}

function parseLayer(buf: Uint8Array, address: number): ParsedLayer {
  const meta = parseMetadataBlock(buf, address);
  const bitmapAddr = str(meta, 'LAYERBITMAP');
  return {
    name: str(meta, 'LAYERNAME') ?? '',
    protocol: str(meta, 'LAYERPROTOCOL'),
    type: str(meta, 'LAYERTYPE'),
    content: bitmapAddr ? readBlock(buf, parseInt(bitmapAddr, 10)) : null,
  };
}

function parsePage(buf: Uint8Array, address: number, isX: boolean): ParsedPage {
  const meta = parseMetadataBlock(buf, address);
  const orientation = str(meta, 'ORIENTATION') ?? ORIENTATION_VERTICAL;
  const style = str(meta, 'PAGESTYLE');
  const layerInfoRaw = str(meta, 'LAYERINFO');
  const layerInfo = layerInfoRaw && layerInfoRaw !== 'none' ? layerInfoRaw.replace(/#/g, ':') : undefined;
  const layerOrder = (str(meta, 'LAYERSEQ') ?? '').split(',').filter((s) => s.length > 0);

  const layers: ParsedLayer[] = [];
  if (isX) {
    for (const key of LAYER_KEYS) {
      const addr = str(meta, key);
      if (addr !== undefined) layers.push(parseLayer(buf, parseInt(addr, 10)));
    }
  }

  if (layers.length > 0) {
    return {
      protocol: layers[0].protocol,
      orientation,
      style,
      layerInfo,
      layerOrder: layerOrder.length ? layerOrder : layers.map((l) => l.name),
      layerSupported: true,
      layers,
      content: null,
    };
  }

  // Non-layered (original format): single DATA bitmap + PROTOCOL.
  const dataAddr = str(meta, 'DATA');
  return {
    protocol: str(meta, 'PROTOCOL'),
    orientation,
    style,
    layerInfo,
    layerOrder: [],
    layerSupported: false,
    layers: [],
    content: dataAddr ? readBlock(buf, parseInt(dataAddr, 10)) : null,
  };
}

function parseKeywords(buf: Uint8Array, footer: Params): ParsedKeyword[] {
  const out: ParsedKeyword[] = [];
  for (const key of Object.keys(footer)) {
    if (!key.startsWith('KEYWORD_')) continue;
    for (const addr of asList(footer[key])) {
      const meta = parseMetadataBlock(buf, parseInt(addr, 10));
      const text = str(meta, 'KEYWORD');
      const page = str(meta, 'KEYWORDPAGE');
      if (text) out.push({ pageNumber: page ? parseInt(page, 10) - 1 : 0, text });
    }
  }
  return out;
}

function parseLinks(buf: Uint8Array, footer: Params): ParsedLink[] {
  const out: ParsedLink[] = [];
  const linkKeys = Object.keys(footer).filter((k) => k.startsWith('LINK'));
  for (const key of linkKeys) {
    // footer key form: LINKO<pageDigits>... — page number lives in chars 6..10 (sync.py parity).
    const pageNumber = /^\D+(\d{4})/.test(key) ? parseInt(key.slice(6, 10), 10) - 1 : 0;
    for (const addr of asList(footer[key])) {
      const meta = parseMetadataBlock(buf, parseInt(addr, 10));
      const encoded = str(meta, 'LINKFILE') ?? '';
      let name = '';
      try {
        name = encoded ? base64ToString(encoded) : '';
        const slash = Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\'));
        if (slash >= 0) name = name.slice(slash + 1);
      } catch {
        name = '';
      }
      out.push({
        pageNumber,
        type: parseInt(str(meta, 'LINKTYPE') ?? '0', 10),
        inout: parseInt(str(meta, 'LINKINOUT') ?? '0', 10),
        name,
      });
    }
  }
  return out;
}

/** Parse a `.note` file (raw bytes) into a structured ParsedNote. */
export function parseNote(input: ArrayBuffer | Uint8Array): ParsedNote {
  const buf = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (buf.length < 8) throw new UnsupportedFileFormat('file too small');

  const filetype = latin1.decode(buf.subarray(0, 4));
  const { signature, isX } = detectSignature(buf);
  const highres = isX && parseInt(signature.slice(-8), 10) >= 20230015;

  const footerAddress = u32(buf, buf.length - 4);
  const footer = parseMetadataBlock(buf, footerAddress);

  const headerAddress = str(footer, 'FILE_FEATURE');
  const header = headerAddress ? parseMetadataBlock(buf, parseInt(headerAddress, 10)) : {};

  let pageWidth = PAGE_WIDTH;
  let pageHeight = PAGE_HEIGHT;
  if (str(header, 'APPLY_EQUIPMENT') === 'N5') {
    pageWidth = A5X2_PAGE_WIDTH;
    pageHeight = A5X2_PAGE_HEIGHT;
  }

  const pageAddresses = Object.keys(footer)
    .filter((k) => k.startsWith('PAGE'))
    .flatMap((k) => asList(footer[k]))
    .map((a) => parseInt(a, 10));

  const pages = pageAddresses.map((addr) => parsePage(buf, addr, isX));

  return {
    filetype,
    signature,
    pageWidth,
    pageHeight,
    highres,
    pages,
    keywords: isX ? parseKeywords(buf, footer) : [],
    links: isX ? parseLinks(buf, footer) : [],
  };
}
