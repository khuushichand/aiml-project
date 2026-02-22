import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface WaveSrc { x: number; y: number; birth: number }

const WAVE_CHARS = " .\u00B7:;oO#";
const COLORS = ["#001133", "#003366", "#005599", "#0077cc", "#0099ee", "#44bbff", "#88ddff"];

export default class WaveRippleEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private sources: WaveSrc[] = [];
  private nextDrop = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.sources = [];
    this.nextDrop = 500;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed;

    if (elapsed > this.nextDrop) {
      this.sources.push({
        x: 5 + Math.floor(Math.random() * (this.grid.cols - 10)),
        y: 2 + Math.floor(Math.random() * (this.grid.rows - 4)),
        birth: elapsed,
      });
      this.nextDrop = elapsed + 800 + Math.random() * 1500;
    }

    // cull old sources
    this.sources = this.sources.filter(s => elapsed - s.birth < 8000);

    this.grid.clear("#000a1a");

    for (let y = 0; y < this.grid.rows; y++) {
      for (let x = 0; x < this.grid.cols; x++) {
        let total = 0;
        for (const src of this.sources) {
          const dx = (x - src.x) * 0.5;
          const dy = y - src.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const age = (elapsed - src.birth) / 1000;
          const wave = Math.sin(dist * 1.5 - age * 4) * Math.max(0, 1 - age * 0.15) / (1 + dist * 0.1);
          total += wave;
        }

        if (Math.abs(total) > 0.05) {
          const norm = (total + 1) / 2;
          const clamped = Math.max(0, Math.min(1, norm));
          const ci = Math.floor(clamped * (WAVE_CHARS.length - 1));
          const colIdx = Math.floor(clamped * (COLORS.length - 1));
          this.grid.setCell(x, y, WAVE_CHARS[ci], COLORS[colIdx]);
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000a1a";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.sources = []; this.time = 0; this.nextDrop = 500; }
  dispose(): void { this.sources = []; }
}
