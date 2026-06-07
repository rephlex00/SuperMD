/** Supernote file-format constants, ported from supernotelib/fileformat.py. */

export const PAGE_WIDTH = 1404;
export const PAGE_HEIGHT = 1872;
export const A5X2_PAGE_WIDTH = 1920;
export const A5X2_PAGE_HEIGHT = 2560;

export const ADDRESS_SIZE = 4;
export const LENGTH_FIELD_SIZE = 4;

export const LAYER_KEYS = ['MAINLAYER', 'LAYER1', 'LAYER2', 'LAYER3', 'BGLAYER'];

export const ORIENTATION_VERTICAL = '1000';
export const ORIENTATION_HORIZONTAL = '1090';

/** Block size of the special blank "style_white" background layer. */
export const SPECIAL_WHITE_STYLE_BLOCK_SIZE = 0x140e;

export type Params = Record<string, string | string[]>;

export interface ParsedLayer {
  name: string;
  protocol?: string;
  type?: string;
  content: Uint8Array | null;
}

export interface ParsedPage {
  protocol?: string;
  orientation: string;
  style?: string;
  layerInfo?: string;
  layerOrder: string[];
  layerSupported: boolean;
  layers: ParsedLayer[];
  content: Uint8Array | null;
}

export interface ParsedKeyword {
  pageNumber: number;
  text: string;
}

export interface ParsedLink {
  pageNumber: number;
  type: number;
  inout: number;
  name: string;
}

export interface ParsedNote {
  filetype: string;
  signature: string;
  pageWidth: number;
  pageHeight: number;
  /** True when signature year >= 20230015 → high-res grayscale (RattaRleX2). */
  highres: boolean;
  pages: ParsedPage[];
  keywords: ParsedKeyword[];
  links: ParsedLink[];
}
