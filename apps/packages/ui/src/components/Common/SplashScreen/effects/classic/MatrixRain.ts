import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

interface Column {
  y: number;
  speed: number;
  length: number;
  chars: string[];
}

const CHARS = "abcdefghijklmnopqrstuvwxyz0123456789@#$%&";
const TITLE = "tldw";

export default class MatrixRainEffect implements SplashEffect {
  private grid!: CharGrid;
  private columns: Column[] = [];
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private titleRevealed = false;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.columns = [];
    for (let x = 0; x < 80; x++) {
      this.columns.push({
        y: Math.random() * -24,
        speed: 8 + Math.random() * 16,
        length: 4 + Math.floor(Math.random() * 12),
        chars: Array.from({ length: 24 }, () => CHARS[Math.floor(Math.random() * CHARS.length)]),
      });
    }
    this.titleRevealed = false;
  }

  update(elapsed: number, dt: number): void {
    this.grid.clear();
    const dtSec = dt / 1000;
    for (let x = 0; x < 80; x++) {
      const col = this.columns[x];
      col.y += col.speed * dtSec;
      if (col.y - col.length > 24) {
        col.y = Math.random() * -6;
        col.speed = 8 + Math.random() * 16;
      }
      for (let i = 0; i < col.length; i++) {
        const row = Math.floor(col.y) - i;
        if (row >= 0 && row < 24) {
          const fade = 1 - i / col.length;
          const g = Math.floor(80 + 175 * fade);
          const color = `rgb(0,${g},0)`;
          const ch = i === 0
            ? CHARS[Math.floor(Math.random() * CHARS.length)]
            : col.chars[row % col.chars.length];
          this.grid.setCell(x, row, ch, color);
        }
      }
    }
    if (elapsed > 500) {
      this.titleRevealed = true;
      const tx = Math.floor((80 - TITLE.length) / 2);
      const ty = 12;
      this.grid.writeString(tx, ty, TITLE, "rgb(255,255,255)");
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.columns = [];
    this.titleRevealed = false;
  }

  dispose(): void {
    this.columns = [];
  }
}
