import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const BASES = ["A", "T", "G", "C"] as const;
const BASE_COLORS: Record<string, string> = { A: "#ff4444", T: "#4488ff", G: "#44cc44", C: "#ffcc00" };
const STRAND_COLOR = "#aaaacc";
const PAIR_COLOR = "#666688";

export default class DnaHelixEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private baseSequence: number[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.baseSequence = [];
    for (let i = 0; i < this.grid.rows; i++) {
      this.baseSequence.push(Math.floor(Math.random() * 4));
    }
  }

  private complement(idx: number): number {
    // A-T, G-C pairs
    return idx <= 1 ? 1 - idx : 5 - idx;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#080818");
    const cx = this.grid.cols / 2;
    const amplitude = 12;

    for (let y = 0; y < this.grid.rows; y++) {
      const phase = y * 0.5 + this.time * 2;
      const x1 = Math.round(cx + Math.sin(phase) * amplitude);
      const x2 = Math.round(cx - Math.sin(phase) * amplitude);
      const depth1 = Math.cos(phase);
      const depth2 = -depth1;

      // draw connecting base pair
      const minX = Math.min(x1, x2);
      const maxX = Math.max(x1, x2);
      if (y % 2 === 0) {
        for (let x = minX + 1; x < maxX; x++) {
          this.grid.setCell(x, y, "-", PAIR_COLOR);
        }
        // base labels at connection points
        const bi = this.baseSequence[y % this.baseSequence.length];
        const ci = this.complement(bi);
        const b1 = BASES[bi];
        const b2 = BASES[ci];
        if (x1 >= 0 && x1 < this.grid.cols) {
          this.grid.setCell(x1, y, b1, BASE_COLORS[b1]);
        }
        if (x2 >= 0 && x2 < this.grid.cols) {
          this.grid.setCell(x2, y, b2, BASE_COLORS[b2]);
        }
      } else {
        // strand backbone
        const ch1 = depth1 > 0 ? "O" : "o";
        const ch2 = depth2 > 0 ? "O" : "o";
        if (x1 >= 0 && x1 < this.grid.cols) {
          this.grid.setCell(x1, y, ch1, STRAND_COLOR);
        }
        if (x2 >= 0 && x2 < this.grid.cols) {
          this.grid.setCell(x2, y, ch2, STRAND_COLOR);
        }
      }
    }

    this.grid.writeCentered(0, "= DNA Helix =", "#ccccff");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#080818";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; }
  dispose(): void { this.baseSequence = []; }
}
