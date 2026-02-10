/**
 * Rich-style color names → CSS hex mapping.
 * Covers the named colors used in the Python splash effects.
 */
const RICH_COLOR_MAP: Record<string, string> = {
  black: "#000000",
  red: "#cc0000",
  green: "#00cc00",
  yellow: "#cccc00",
  blue: "#0000cc",
  magenta: "#cc00cc",
  cyan: "#00cccc",
  white: "#cccccc",
  bright_black: "#666666",
  bright_red: "#ff0000",
  bright_green: "#00ff00",
  bright_yellow: "#ffff00",
  bright_blue: "#5555ff",
  bright_magenta: "#ff55ff",
  bright_cyan: "#55ffff",
  bright_white: "#ffffff",
  orange: "#ff8c00",
  sandy_brown: "#f4a460",
  grey: "#808080",
  gray: "#808080",
  dark_green: "#006400",
  dark_blue: "#00008b",
  dark_red: "#8b0000",
  dark_cyan: "#008b8b",
  dark_magenta: "#8b008b",
  purple: "#800080",
  pink: "#ffc0cb",
  gold: "#ffd700",
  silver: "#c0c0c0",
  lime: "#00ff00",
  teal: "#008080",
  navy: "#000080",
  olive: "#808000",
  maroon: "#800000",
  aqua: "#00ffff",
  coral: "#ff7f50",
  salmon: "#fa8072",
  chartreuse: "#7fff00",
  turquoise: "#40e0d0",
  violet: "#ee82ee",
  indigo: "#4b0082",
  crimson: "#dc143c",
};

/**
 * Parse a Rich-style color spec into a CSS color string.
 * Handles: named colors, "rgb(r,g,b)", "bold X", "dim X", hex "#RRGGBB".
 */
export function richColorToCSS(spec: string | undefined | null): string {
  if (!spec) return "#cccccc";

  // Strip modifiers
  let s = spec.replace(/\b(bold|dim|italic|underline|on\s+\S+)\b/g, "").trim();

  // Already hex
  if (s.startsWith("#")) return s;

  // rgb(r,g,b)
  const rgbMatch = s.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (rgbMatch) {
    const [, r, g, b] = rgbMatch;
    return `rgb(${r},${g},${b})`;
  }

  // Named color (support underscores and spaces)
  const key = s.toLowerCase().replace(/\s+/g, "_");
  if (RICH_COLOR_MAP[key]) return RICH_COLOR_MAP[key];

  return "#cccccc";
}

/** Generate a random HSL color string. */
export function randomHSL(sMin = 60, sMax = 100, lMin = 40, lMax = 70): string {
  const h = Math.floor(Math.random() * 360);
  const s = sMin + Math.floor(Math.random() * (sMax - sMin));
  const l = lMin + Math.floor(Math.random() * (lMax - lMin));
  return `hsl(${h},${s}%,${l}%)`;
}

/** Interpolate between two hex colors. t in [0,1]. */
export function lerpColor(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const h = hex.replace("#", "");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  };
  try {
    const [r1, g1, b1] = parse(a);
    const [r2, g2, b2] = parse(b);
    const r = Math.round(r1 + (r2 - r1) * t);
    const g = Math.round(g1 + (g2 - g1) * t);
    const bb = Math.round(b1 + (b2 - b1) * t);
    return `rgb(${r},${g},${bb})`;
  } catch {
    return t < 0.5 ? a : b;
  }
}

/** Adjust brightness of a hex color. factor > 1 = brighter, < 1 = dimmer. */
export function adjustBrightness(hex: string, factor: number): string {
  const h = hex.replace("#", "");
  const r = Math.min(255, Math.round(parseInt(h.slice(0, 2), 16) * factor));
  const g = Math.min(255, Math.round(parseInt(h.slice(2, 4), 16) * factor));
  const b = Math.min(255, Math.round(parseInt(h.slice(4, 6), 16) * factor));
  return `rgb(${r},${g},${b})`;
}
