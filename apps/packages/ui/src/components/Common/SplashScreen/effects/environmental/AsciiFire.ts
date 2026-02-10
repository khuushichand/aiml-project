import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const FIRE_CHARS = " .oO8@#";
const FIRE_COLORS = [
  "#000000", "#330000", "#661100", "#993300",
  "#cc5500", "#ee7700", "#ffaa00", "#ffcc44", "#ffee88",
];

export default class AsciiFireEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private heat: number[] = [];
  private cols = 80;
  private rows = 24;
  private sparks: Array<{ x: number; y: number; life: number }> = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.cols;
    this.cellH = height / this.rows;
    this.heat = new Array(this.cols * this.rows).fill(0);
    this.sparks = [];
  }

  update(_elapsed: number, _dt: number): void {
    // seed bottom row
    for (let x = 0; x < this.cols; x++) {
      this.heat[(this.rows - 1) * this.cols + x] = Math.random() > 0.3 ? 1 : 0.5 + Math.random() * 0.5;
    }
    // propagate upward
    for (let y = 0; y < this.rows - 1; y++) {
      for (let x = 0; x < this.cols; x++) {
        const below = this.heat[(y + 1) * this.cols + x];
        const bl = this.heat[(y + 1) * this.cols + Math.max(0, x - 1)];
        const br = this.heat[(y + 1) * this.cols + Math.min(this.cols - 1, x + 1)];
        const decay = 0.05 + Math.random() * 0.08;
        this.heat[y * this.cols + x] = Math.max(0, (below + bl + br) / 3 - decay);
      }
    }
    // random sparks
    if (Math.random() < 0.3) {
      this.sparks.push({ x: Math.floor(Math.random() * this.cols), y: this.rows - 2, life: 8 + Math.random() * 6 });
    }
    for (const s of this.sparks) {
      s.y -= 0.5;
      s.x += (Math.random() - 0.5) * 1.5;
      s.life--;
    }
    this.sparks = this.sparks.filter(s => s.life > 0 && s.y >= 0);

    this.grid.clear("#000000");
    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.cols; x++) {
        const h = this.heat[y * this.cols + x];
        if (h > 0.05) {
          const ci = Math.floor(h * (FIRE_CHARS.length - 1));
          const colIdx = Math.floor(h * (FIRE_COLORS.length - 1));
          this.grid.setCell(x, y, FIRE_CHARS[Math.min(ci, FIRE_CHARS.length - 1)], FIRE_COLORS[colIdx]);
        }
      }
    }
    for (const s of this.sparks) {
      const sx = Math.round(s.x);
      const sy = Math.round(s.y);
      if (sx >= 0 && sx < this.cols && sy >= 0 && sy < this.rows) {
        this.grid.setCell(sx, sy, "*", "#ffee88");
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.heat.fill(0);
    this.sparks = [];
  }

  dispose(): void {
    this.heat = [];
    this.sparks = [];
  }
}
