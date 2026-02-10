import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

const GLITCH_CHARS = "!@#$%^&*\u2593\u2592\u2591\u2588";

export default class GlitchRevealEffect implements SplashEffect {
  private grid!: CharGrid;
  private targetText: string[] = [];
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private startIntensity = 0.9;
  private duration = 2000;
  private glitchChars = GLITCH_CHARS;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.startIntensity = (config?.start_intensity as number) ?? 0.9;
    this.duration = (config?.duration as number) ?? 2000;
    this.glitchChars = (config?.glitch_chars as string) ?? GLITCH_CHARS;
    this.targetText = [];
    const content = (config?.content as string) ?? "tldw - Too Long; Didn't Watch";
    const cy = 12;
    const cx = Math.floor((80 - content.length) / 2);
    for (let i = 0; i < content.length; i++) {
      this.targetText.push(`${cx + i},${cy},${content[i]}`);
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const progress = Math.min(elapsed / this.duration, 1);
    const intensity = this.startIntensity * (1 - progress);

    for (const entry of this.targetText) {
      const [xs, ys, ch] = entry.split(",");
      const x = parseInt(xs);
      const y = parseInt(ys);
      if (Math.random() < intensity) {
        const gc = this.glitchChars[Math.floor(Math.random() * this.glitchChars.length)];
        const r = 100 + Math.floor(Math.random() * 155);
        const g = Math.floor(Math.random() * 100);
        this.grid.setCell(x, y, gc, `rgb(${r},${g},${g})`);
      } else {
        this.grid.setCell(x, y, ch, "rgb(220,220,220)");
      }
    }

    // Scatter random glitch chars across grid at decreasing density
    const scatterCount = Math.floor(80 * 24 * intensity * 0.05);
    for (let i = 0; i < scatterCount; i++) {
      const gx = Math.floor(Math.random() * 80);
      const gy = Math.floor(Math.random() * 24);
      const gc = this.glitchChars[Math.floor(Math.random() * this.glitchChars.length)];
      this.grid.setCell(gx, gy, gc, `rgb(0,${150 + Math.floor(Math.random() * 105)},0)`);
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.targetText = [];
  }

  dispose(): void {
    this.targetText = [];
  }
}
