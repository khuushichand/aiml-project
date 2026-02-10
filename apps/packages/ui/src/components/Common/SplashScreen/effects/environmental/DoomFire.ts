import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const PALETTE = [
  "#070707", "#1f0707", "#2f0f07", "#470f07", "#571707",
  "#671f07", "#771f07", "#8f2707", "#9f2f07", "#af3f07",
  "#bf4707", "#c74707", "#df4f07", "#df5707", "#df5707",
  "#d75f07", "#d7670f", "#cf6f0f", "#cf770f", "#cf7f0f",
  "#cf8717", "#c78717", "#c78f17", "#c7971f", "#bf9f1f",
  "#bf9f1f", "#bfa727", "#bfa727", "#bfaf2f", "#b7af2f",
  "#b7b72f", "#b7b737", "#cfcf6f", "#dfdf9f", "#efefc7",
  "#ffffff",
];
const CHARS = " .,:;+*#@";

export default class DoomFireEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private fire: number[] = [];
  private cols = 80;
  private rows = 24;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.cols;
    this.cellH = height / this.rows;
    this.fire = new Array(this.cols * this.rows).fill(0);
    for (let x = 0; x < this.cols; x++) {
      this.fire[(this.rows - 1) * this.cols + x] = PALETTE.length - 1;
    }
  }

  update(_elapsed: number, _dt: number): void {
    for (let x = 0; x < this.cols; x++) {
      for (let y = 1; y < this.rows; y++) {
        const src = y * this.cols + x;
        const randIdx = Math.round(Math.random() * 3) & 3;
        const dst = src - this.cols - randIdx + 1;
        const val = this.fire[src] - (randIdx & 1);
        this.fire[Math.max(0, dst)] = Math.max(0, val);
      }
    }
    this.grid.clear("#000000");
    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.cols; x++) {
        const val = this.fire[y * this.cols + x];
        const ci = Math.floor((val / (PALETTE.length - 1)) * (CHARS.length - 1));
        this.grid.setCell(x, y, CHARS[ci], PALETTE[val]);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.fire.fill(0);
    for (let x = 0; x < this.cols; x++) {
      this.fire[(this.rows - 1) * this.cols + x] = PALETTE.length - 1;
    }
  }

  dispose(): void {
    this.fire = [];
  }
}
