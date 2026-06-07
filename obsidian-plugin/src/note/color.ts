/** Grayscale color palette, ported from supernotelib/color.py. */

export interface GrayPalette {
  black: number;
  darkgray: number;
  gray: number;
  white: number;
  transparent: number;
  darkgray_compat: number;
  gray_compat: number;
}

export const BLACK = 0x00;
export const DARK_GRAY = 0x9d;
export const GRAY = 0xc9;
export const WHITE = 0xfe;
export const TRANSPARENT = 0xff;
export const DARK_GRAY_COMPAT = 0x30;
export const GRAY_COMPAT = 0x50;

export const DEFAULT_GRAY_PALETTE: GrayPalette = {
  black: BLACK,
  darkgray: DARK_GRAY,
  gray: GRAY,
  white: WHITE,
  transparent: TRANSPARENT,
  darkgray_compat: DARK_GRAY_COMPAT,
  gray_compat: GRAY_COMPAT,
};
