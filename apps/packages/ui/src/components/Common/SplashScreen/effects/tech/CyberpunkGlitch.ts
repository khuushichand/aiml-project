import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const GLITCH_CHARS = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`";
const NEON_COLORS = ["#00ffff", "#ff00ff", "#ffff00", "#ff0066", "#00ff66", "#6600ff"];

const TITLE_LINES = [
  "  ████████╗██╗     ██████╗ ██╗    ██╗",
  "  ╚══██╔══╝██║     ██╔══██╗██║    ██║",
  "     ██║   ██║     ██║  ██║██║ █╗ ██║",
  "     ██║   ██║     ██║  ██║██║███╗██║",
  "     ██║   ███████╗██████╔╝╚███╔███╔╝",
  "     ╚═╝   ╚══════╝╚═════╝  ╚══╝╚══╝ ",
];

export default class CyberpunkGlitch implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private glitchIntensity = 0;
  private nextGlitch = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
    this.glitchIntensity = 0;
    this.nextGlitch = 500;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    if (elapsed > this.nextGlitch) {
      this.glitchIntensity = 0.5 + Math.random() * 0.5;
      this.nextGlitch = elapsed + 200 + Math.random() * 2000;
    }

    this.glitchIntensity *= 0.95;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Background noise
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        if (Math.random() < 0.03) {
          const ci = Math.floor(Math.random() * GLITCH_CHARS.length);
          grid.setCell(x, y, GLITCH_CHARS[ci], "#1a1a2e");
        }
      }
    }

    // Title with RGB split / glitch offset
    const titleStartY = 5;
    for (let i = 0; i < TITLE_LINES.length; i++) {
      const line = TITLE_LINES[i];
      const offsetX = this.glitchIntensity > 0.2
        ? Math.floor((Math.random() - 0.5) * this.glitchIntensity * 6)
        : 0;

      const cx = Math.floor((80 - line.length) / 2) + offsetX;

      // Cyan layer (offset left)
      if (this.glitchIntensity > 0.3) {
        for (let c = 0; c < line.length; c++) {
          const px = cx + c - 1;
          if (px >= 0 && px < 80) grid.setCell(px, titleStartY + i, line[c], "#00ffff44");
        }
      }

      // Main layer
      for (let c = 0; c < line.length; c++) {
        const px = cx + c;
        if (px >= 0 && px < 80) {
          const ch = this.glitchIntensity > 0.4 && Math.random() < this.glitchIntensity * 0.3
            ? GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]
            : line[c];
          grid.setCell(px, titleStartY + i, ch, "#ff00ff");
        }
      }

      // Magenta layer (offset right)
      if (this.glitchIntensity > 0.3) {
        for (let c = 0; c < line.length; c++) {
          const px = cx + c + 1;
          if (px >= 0 && px < 80) grid.setCell(px, titleStartY + i, line[c], "#ff006644");
        }
      }
    }

    // Glitch bars
    if (this.glitchIntensity > 0.2) {
      const numBars = Math.floor(this.glitchIntensity * 5);
      for (let b = 0; b < numBars; b++) {
        const barY = Math.floor(Math.random() * 24);
        const barStart = Math.floor(Math.random() * 40);
        const barLen = 10 + Math.floor(Math.random() * 30);
        const color = NEON_COLORS[Math.floor(Math.random() * NEON_COLORS.length)];
        for (let x = barStart; x < Math.min(barStart + barLen, 80); x++) {
          grid.setCell(x, barY, "=", color);
        }
      }
    }

    // Subtitle
    grid.writeCentered(13, "C Y B E R P U N K   M E D I A", "#ffff00");
    grid.writeCentered(14, "[ NEURAL LINK ESTABLISHED ]", "#00ffff");

    // Scan lines
    for (let y = 0; y < 24; y += 3) {
      for (let x = 0; x < 80; x++) {
        if (Math.random() < 0.1) {
          grid.setCell(x, y, "-", "#ffffff11");
        }
      }
    }

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.glitchIntensity = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
