import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';

type HslTuple = [number, number, number];

const parseDarkThemeTokens = (): Record<string, HslTuple> => {
  const css = readFileSync(path.join(process.cwd(), 'app/globals.css'), 'utf-8');
  const darkBlockMatch = css.match(/\.dark\s*\{([\s\S]*?)\}/);
  if (!darkBlockMatch) {
    throw new Error('Unable to find .dark block in app/globals.css');
  }

  const tokens: Record<string, HslTuple> = {};
  const tokenPattern = /--([a-z0-9-]+):\s*([^;]+);/gi;
  let match = tokenPattern.exec(darkBlockMatch[1]);
  while (match) {
    const value = match[2].trim();
    const hslMatch = value.match(/^([+-]?(?:\d+\.?\d*|\.\d+))\s+([+-]?(?:\d+\.?\d*|\.\d+))%\s+([+-]?(?:\d+\.?\d*|\.\d+))%$/);
    if (hslMatch) {
      tokens[match[1]] = [
        Number.parseFloat(hslMatch[1]),
        Number.parseFloat(hslMatch[2]),
        Number.parseFloat(hslMatch[3]),
      ];
    }
    match = tokenPattern.exec(darkBlockMatch[1]);
  }
  return tokens;
};

const hslToRgb = ([h, s, l]: HslTuple): [number, number, number] => {
  const hue = ((h % 360) + 360) % 360;
  const sat = s / 100;
  const light = l / 100;
  const chroma = (1 - Math.abs((2 * light) - 1)) * sat;
  const x = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
  const m = light - (chroma / 2);

  let rPrime = 0;
  let gPrime = 0;
  let bPrime = 0;

  if (hue < 60) {
    rPrime = chroma;
    gPrime = x;
  } else if (hue < 120) {
    rPrime = x;
    gPrime = chroma;
  } else if (hue < 180) {
    gPrime = chroma;
    bPrime = x;
  } else if (hue < 240) {
    gPrime = x;
    bPrime = chroma;
  } else if (hue < 300) {
    rPrime = x;
    bPrime = chroma;
  } else {
    rPrime = chroma;
    bPrime = x;
  }

  return [rPrime + m, gPrime + m, bPrime + m];
};

const linearize = (channel: number): number => (
  channel <= 0.03928
    ? channel / 12.92
    : ((channel + 0.055) / 1.055) ** 2.4
);

const luminance = (rgb: [number, number, number]): number => (
  (0.2126 * linearize(rgb[0])) +
  (0.7152 * linearize(rgb[1])) +
  (0.0722 * linearize(rgb[2]))
);

const contrastRatio = (foreground: HslTuple, background: HslTuple): number => {
  const fg = luminance(hslToRgb(foreground));
  const bg = luminance(hslToRgb(background));
  const lighter = Math.max(fg, bg);
  const darker = Math.min(fg, bg);
  return (lighter + 0.05) / (darker + 0.05);
};

describe('dark mode contrast tokens', () => {
  it('meets WCAG AA thresholds for core text and UI pairs', () => {
    const tokens = parseDarkThemeTokens();
    const checks: Array<{ fg: string; bg: string; minRatio: number }> = [
      { fg: 'foreground', bg: 'background', minRatio: 4.5 },
      { fg: 'card-foreground', bg: 'card', minRatio: 4.5 },
      { fg: 'secondary-foreground', bg: 'secondary', minRatio: 4.5 },
      { fg: 'muted-foreground', bg: 'muted', minRatio: 4.5 },
      { fg: 'primary-foreground', bg: 'primary', minRatio: 4.5 },
      { fg: 'destructive-foreground', bg: 'destructive', minRatio: 4.5 },
      { fg: 'border', bg: 'background', minRatio: 3 },
      { fg: 'chart-1', bg: 'background', minRatio: 3 },
      { fg: 'chart-2', bg: 'background', minRatio: 3 },
    ];

    checks.forEach(({ fg, bg, minRatio }) => {
      expect(tokens[fg], `Missing dark token --${fg}`).toBeDefined();
      expect(tokens[bg], `Missing dark token --${bg}`).toBeDefined();
      const ratio = contrastRatio(tokens[fg], tokens[bg]);
      expect(
        ratio,
        `Expected --${fg} on --${bg} to meet ${minRatio}:1 but got ${ratio.toFixed(2)}:1`
      ).toBeGreaterThanOrEqual(minRatio);
    });
  });

  it('keeps dark mode token values stable', () => {
    const tokens = parseDarkThemeTokens();
    expect(tokens).toMatchSnapshot();
  });
});
