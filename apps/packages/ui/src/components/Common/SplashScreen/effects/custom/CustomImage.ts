import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

// Default TLDW logo in block chars
const LOGO_LINES = [
  "  ########  ##       #####    ##      ##",
  "     ##     ##       ##  ##   ##  ##  ##",
  "     ##     ##       ##   ##  ## #### ##",
  "     ##     ##       ##  ##   ###  ####",
  "     ##     ######   #####    ##    ###",
];

const SPARKLE_CHARS = "*.+`'";

export default class CustomImage implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private shimmerPos = -20;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.shimmerPos = -20;
  }

  update(elapsed: number, dt: number): void {
    const t = elapsed / 1000;

    // Shimmer sweeps left to right continuously
    this.shimmerPos = ((t * 15) % 100) - 10;

    this.grid.clear("#000");

    const logoWidth = LOGO_LINES.reduce((max, l) => Math.max(max, l.length), 0);
    const startX = Math.floor((80 - logoWidth) / 2);
    const startY = Math.floor((24 - LOGO_LINES.length) / 2) - 2;

    // Draw the logo
    for (let row = 0; row < LOGO_LINES.length; row++) {
      const line = LOGO_LINES[row];
      const y = startY + row;
      for (let col = 0; col < line.length; col++) {
        const ch = line[col];
        if (ch === " ") continue;

        const x = startX + col;
        const distFromShimmer = Math.abs(x - this.shimmerPos);

        let color: string;
        if (distFromShimmer < 3) {
          // Bright shimmer
          const shimmerBright = 80 + (1 - distFromShimmer / 3) * 20;
          color = `hsl(210,80%,${shimmerBright}%)`;
        } else if (distFromShimmer < 6) {
          // Near-shimmer glow
          color = `hsl(210,60%,55%)`;
        } else {
          // Base logo color
          const wave = Math.sin(t * 0.5 + col * 0.1) * 10;
          color = `hsl(210,50%,${40 + wave}%)`;
        }

        this.grid.setCell(x, y, ch, color);
      }
    }

    // Subtitle
    const subtitle = "Too Long; Didn't Watch";
    const subY = startY + LOGO_LINES.length + 2;
    const subX = Math.floor((80 - subtitle.length) / 2);
    for (let i = 0; i < subtitle.length; i++) {
      const wave = Math.sin(t * 2 + i * 0.3);
      const bright = 40 + wave * 15;
      this.grid.setCell(
        subX + i, subY, subtitle[i],
        `hsl(200,40%,${bright}%)`
      );
    }

    // Sparkles scattered around the logo
    const sparkleCount = 15;
    for (let i = 0; i < sparkleCount; i++) {
      const phase = t * 1.5 + i * 2.1;
      const sx = Math.floor(startX - 5 + Math.sin(phase * 0.7 + i) * (logoWidth / 2 + 10) + logoWidth / 2);
      const sy = Math.floor(startY - 2 + Math.cos(phase * 0.5 + i * 1.3) * 6 + LOGO_LINES.length / 2);

      if (sx >= 0 && sx < 80 && sy >= 0 && sy < 24) {
        const sparkleAlpha = (Math.sin(phase * 3) + 1) / 2;
        if (sparkleAlpha > 0.5) {
          const ch = SPARKLE_CHARS[Math.floor(phase) % SPARKLE_CHARS.length];
          const bright = 50 + sparkleAlpha * 50;
          this.grid.setCell(sx, sy, ch, `hsl(45,80%,${bright}%)`);
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.shimmerPos = -20;
  }

  dispose(): void {}
}
