import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const BASES = "ATGC";
const BASE_COLORS: Record<string, string> = {
  A: "#ff4444",
  T: "#44ff44",
  G: "#4444ff",
  C: "#ffff44",
};

export default class DnaSequence implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private strands: number = 5;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const cols = grid.cols;
    const rows = grid.rows;
    const t = this.elapsed / 1000;

    for (let s = 0; s < this.strands; s++) {
      const cx = 10 + s * 15;
      const amp = 4;
      const freq = 0.35;
      const scrollSpeed = 2.0;

      for (let y = 0; y < rows; y++) {
        const phase = (y + t * scrollSpeed) * freq;

        const x1 = cx + Math.round(Math.sin(phase) * amp);
        const x2 = cx + Math.round(Math.sin(phase + Math.PI) * amp);

        const bi1 = Math.abs(Math.floor(phase * 2 + s * 3)) % 4;
        const bi2 = (bi1 + 2) % 4;
        const b1 = BASES[bi1];
        const b2 = BASES[bi2];

        if (x1 >= 0 && x1 < cols) {
          grid.setCell(x1, y, b1, BASE_COLORS[b1]);
        }
        if (x2 >= 0 && x2 < cols) {
          grid.setCell(x2, y, b2, BASE_COLORS[b2]);
        }

        // Draw connecting rungs when strands are close
        const dist = Math.abs(x1 - x2);
        if (dist > 1 && dist < 10) {
          const minX = Math.min(x1, x2) + 1;
          const maxX = Math.max(x1, x2);
          for (let rx = minX; rx < maxX; rx++) {
            if (rx >= 0 && rx < cols) {
              grid.setCell(rx, y, "-", "#666666");
            }
          }
        }
      }
    }

    grid.writeCentered(11, " tldw ", "#ffffff");
    grid.writeCentered(12, "Genome Analysis", "#88ccff");

    const cellW = this.w / cols;
    const cellH = this.h / rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
