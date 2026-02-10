import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

export default class BinaryMatrix implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private cells: number[][] = [];
  private flipTimers: number[][] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;

    this.cells = [];
    this.flipTimers = [];
    for (let y = 0; y < 24; y++) {
      this.cells[y] = [];
      this.flipTimers[y] = [];
      for (let x = 0; x < 80; x++) {
        this.cells[y][x] = Math.random() > 0.5 ? 1 : 0;
        this.flipTimers[y][x] = Math.random() * 5000;
      }
    }
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        if (elapsed > this.flipTimers[y][x]) {
          this.cells[y][x] = this.cells[y][x] === 0 ? 1 : 0;
          this.flipTimers[y][x] = elapsed + 500 + Math.random() * 4000;
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const ch = this.cells[y][x] === 1 ? "1" : "0";
        const brightness = 40 + Math.floor(Math.sin(this.elapsed / 1000 + x * 0.3 + y * 0.2) * 20);
        grid.setCell(x, y, ch, `hsl(120,80%,${brightness}%)`);
      }
    }

    const title = "[ T L D W ]";
    const subtitle = "Too Long; Didn't Watch";
    const cy = 11;
    grid.writeCentered(cy, title, "#ffffff");
    grid.writeCentered(cy + 1, subtitle, "#cccccc");

    const border = "=".repeat(title.length + 4);
    grid.writeCentered(cy - 1, border, "#00ff00");
    grid.writeCentered(cy + 2, border, "#00ff00");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.cells = [];
    this.flipTimers = [];
    this.grid.clear();
  }
}
