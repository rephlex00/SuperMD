/**
 * Decodes a parsed page to a flat 8-bit grayscale buffer, compositing layers.
 * Ported from supernotelib/converter.py (ImageConverter._convert_layered_page /
 * _flatten_layers / _get_layer_visibility).
 */
import { DEFAULT_GRAY_PALETTE } from './color';
import { ORIENTATION_HORIZONTAL, ParsedNote, ParsedPage, SPECIAL_WHITE_STYLE_BLOCK_SIZE } from './fileformat';
import { decodeFlate } from './decoders/flate';
import { buildColorMap, DecodedBitmap, decodeRattaRle } from './decoders/rattaRle';
import { base64ToString } from '../util/base64';

const palette = DEFAULT_GRAY_PALETTE;

function decodeLayerContent(
  content: Uint8Array,
  protocol: string | undefined,
  pw: number,
  ph: number,
  allBlank: boolean,
  horizontal: boolean,
  highres: boolean,
): DecodedBitmap | null {
  if (protocol === 'SN_ASA_COMPRESS') return decodeFlate(content, palette);
  if (protocol === 'RATTA_RLE') {
    return decodeRattaRle(content, pw, ph, buildColorMap(palette, highres), allBlank, horizontal);
  }
  return null; // unknown / unsupported (e.g. custom PNG background)
}

function getLayerVisibility(page: ParsedPage): Record<string, boolean> {
  const vis: Record<string, boolean> = {};
  if (!page.layerInfo) {
    for (const l of page.layers) vis[l.name] = true; // fallback: show everything
    vis['MAINLAYER'] = vis['MAINLAYER'] ?? true;
    return vis;
  }
  let arr: Array<{ isBackgroundLayer?: boolean; layerId?: number; isVisible?: boolean }> = [];
  try {
    arr = JSON.parse(page.layerInfo);
  } catch {
    try {
      arr = JSON.parse(base64ToString(page.layerInfo));
    } catch {
      return {};
    }
  }
  for (const layer of arr) {
    const isBg = !!layer.isBackgroundLayer;
    const id = layer.layerId ?? 0;
    const isMain = id === 0 && !isBg;
    const isVisible = !!layer.isVisible;
    if (isBg) vis['BGLAYER'] = isVisible;
    else if (isMain) vis['MAINLAYER'] = isVisible;
    else vis['LAYER' + id] = isVisible;
  }
  vis['MAINLAYER'] = vis['MAINLAYER'] ?? true;
  return vis;
}

export function decodePageToGray(note: ParsedNote, pageIndex: number): DecodedBitmap {
  const page = note.pages[pageIndex];
  const horizontal = page.orientation === ORIENTATION_HORIZONTAL;
  const pw = note.pageWidth;
  const ph = note.pageHeight;

  if (!page.layerSupported) {
    if (page.content) {
      const decoded = decodeLayerContent(page.content, page.protocol, pw, ph, false, horizontal, note.highres);
      if (decoded) return decoded;
    }
    let W = pw;
    let H = ph;
    if (horizontal) {
      W = ph;
      H = pw;
    }
    return { width: W, height: H, data: new Uint8Array(W * H).fill(palette.white) };
  }

  // Decode each layer by name.
  const imgs: Record<string, DecodedBitmap | null> = {};
  for (const layer of page.layers) {
    if (!layer.content) {
      imgs[layer.name] = null;
      continue;
    }
    // Custom (user_*) PNG backgrounds are not decoded; treat as blank.
    if (layer.name === 'BGLAYER' && page.style && page.style.startsWith('user_')) {
      imgs[layer.name] = null;
      continue;
    }
    const allBlank =
      layer.name === 'BGLAYER' &&
      page.style === 'style_white' &&
      layer.content.length === SPECIAL_WHITE_STYLE_BLOCK_SIZE;
    imgs[layer.name] = decodeLayerContent(
      layer.content,
      layer.protocol ?? page.protocol,
      pw,
      ph,
      allBlank,
      horizontal,
      note.highres,
    );
  }

  let W = pw;
  let H = ph;
  if (horizontal) {
    W = ph;
    H = pw;
  }
  const out = new Uint8Array(W * H).fill(palette.white);
  const visibility = getLayerVisibility(page);

  // Composite bottom-up: layerOrder[0] is topmost, so process it last.
  for (const name of [...page.layerOrder].reverse()) {
    if (!visibility[name]) continue;
    const img = imgs[name];
    if (!img) continue;
    const d = img.data;
    const n = Math.min(d.length, out.length);
    for (let k = 0; k < n; k++) {
      const v = d[k];
      if (v !== palette.transparent) out[k] = v;
    }
  }

  return { width: W, height: H, data: out };
}
