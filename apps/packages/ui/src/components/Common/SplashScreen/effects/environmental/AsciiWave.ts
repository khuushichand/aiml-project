import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const WAVE_CHARS = "~\u2248\u223C-_.";
const COLORS = ["#0066cc", "#0088ee", "#00aaff", "#44ccff", "#88eeff", "#bbffff"];

export default class AsciiWaveEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#000011");

    for (let y = 0; y < this.grid.rows; y++) {
      for (let x = 0; x < this.grid.cols; x++) {
        const w1 = Math.sin(x * 0.15 + this.time * 2.0);
        const w2 = Math.sin(x * 0.08 - this.time * 1.5 + y * 0.3);
        const w3 = Math.sin(x * 0.2 + this.time * 0.7 + y * 0.1);
        const combined = (w1 + w2 + w3) / 3;
        const waveY = Math.floor(this.grid.rows / 2 + combined * 6);

        if (Math.abs(y - waveY) < 2) {
          const ci = Math.floor(((combined + 1) / 2) * (WAVE_CHARS.length - 1));
          const colorIdx = Math.floor(((combined + 1) / 2) * (COLORS.length - 1));
          this.grid.setCell(x, y, WAVE_CHARS[Math.max(0, ci)], COLORS[colorIdx]);
        }
      }
    }

    this.grid.writeCentered(2, "~ tldw ~", "#88eeff");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000011";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.time = 0;
    this.grid.clear("#000011");
  }

  dispose(): void { /* nothing to clean up */ }
}
