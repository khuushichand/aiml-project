import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

const GLITCH_CHARS = "!@#$%^&*\u2593\u2592\u2591\u2588<>{}[]|";

export default class GlitchEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private contentLines: string[] = [];
  private glitchInterval = 150;
  private lastGlitch = 0;
  private rowShifts: number[] = [];
  private glitchChars = GLITCH_CHARS;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.contentLines = (config?.lines as string[]) ?? [
      "tldw - Too Long; Didn't Watch",
      "",
      "System Initialized",
    ];
    this.glitchInterval = (config?.interval as number) ?? 150;
    this.glitchChars = (config?.glitch_chars as string) ?? GLITCH_CHARS;
    this.rowShifts = new Array(24).fill(0);
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const startY = Math.floor((24 - this.contentLines.length) / 2);

    // Periodically regenerate glitch state
    if (elapsed - this.lastGlitch > this.glitchInterval) {
      this.lastGlitch = elapsed;
      for (let r = 0; r < 24; r++) {
        this.rowShifts[r] = Math.random() < 0.15 ? Math.floor(Math.random() * 5) - 2 : 0;
      }
    }

    // Render content with glitch corruption
    for (let li = 0; li < this.contentLines.length; li++) {
      const row = startY + li;
      if (row < 0 || row >= 24) continue;
      const line = this.contentLines[li];
      const cx = Math.floor((80 - line.length) / 2);
      const shift = this.rowShifts[row];

      for (let i = 0; i < line.length; i++) {
        const x = cx + i + shift;
        if (x < 0 || x >= 80) continue;
        if (Math.random() < 0.08) {
          const gc = this.glitchChars[Math.floor(Math.random() * this.glitchChars.length)];
          const colors = ["rgb(255,0,0)", "rgb(0,255,255)", "rgb(255,0,255)"];
          this.grid.setCell(x, row, gc, colors[Math.floor(Math.random() * colors.length)]);
        } else {
          this.grid.setCell(x, row, line[i], "rgb(200,200,200)");
        }
      }
    }

    // Random glitch noise scattered across screen
    const noiseCount = 5 + Math.floor(Math.random() * 15);
    for (let n = 0; n < noiseCount; n++) {
      const gx = Math.floor(Math.random() * 80);
      const gy = Math.floor(Math.random() * 24);
      const gc = this.glitchChars[Math.floor(Math.random() * this.glitchChars.length)];
      this.grid.setCell(gx, gy, gc, `rgb(${Math.floor(Math.random() * 255)},0,${Math.floor(Math.random() * 255)})`);
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.lastGlitch = 0;
    this.rowShifts.fill(0);
  }

  dispose(): void {
    this.contentLines = [];
  }
}
