import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const TRAIN = [
  "  _____ _______ ",
  " |     |       |",
  " | tldw| CARGO |",
  " |_____|_______|",
  " (O)       (O)  ",
];
const MTN_COLOR = "#445566";
const TREE_COLOR = "#226633";
const GROUND_COLOR = "#443322";
const TRAIN_COLOR = "#cccccc";
const WHEEL_COLOR = "#888888";
const SKY_COLOR = "#0a0a2a";
const TRACK_COLOR = "#666655";

export default class TrainJourneyEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private scroll = 0;
  private mountains: number[] = [];
  private trees: number[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.scroll = 0;
    this.mountains = [];
    for (let i = 0; i < 200; i++) {
      this.mountains.push(Math.floor(Math.sin(i * 0.15) * 3 + Math.sin(i * 0.07) * 2 + 5));
    }
    this.trees = [];
    for (let i = 0; i < 200; i++) {
      this.trees.push(Math.random() < 0.3 ? 1 : 0);
    }
  }

  update(_elapsed: number, dt: number): void {
    this.scroll += dt * 0.02;
    this.grid.clear(SKY_COLOR);

    // stars in sky
    for (let x = 0; x < this.grid.cols; x++) {
      if ((x * 7 + 13) % 19 < 2) {
        this.grid.setCell(x, (x * 3 + 5) % 6, ".", "#aaaacc");
      }
    }

    // mountains (far parallax)
    const mtnOff = Math.floor(this.scroll * 0.3) % this.mountains.length;
    for (let x = 0; x < this.grid.cols; x++) {
      const mi = (x + mtnOff) % this.mountains.length;
      const mh = this.mountains[mi];
      for (let dy = 0; dy < mh; dy++) {
        const my = 14 - dy;
        if (my >= 0 && my < this.grid.rows) {
          this.grid.setCell(x, my, "/", MTN_COLOR);
        }
      }
    }

    // trees (mid parallax)
    const treeOff = Math.floor(this.scroll * 0.6) % this.trees.length;
    for (let x = 0; x < this.grid.cols; x++) {
      const ti = (x + treeOff) % this.trees.length;
      if (this.trees[ti]) {
        this.grid.setCell(x, 15, "^", TREE_COLOR);
        this.grid.setCell(x, 16, "|", TREE_COLOR);
      }
    }

    // ground and track
    this.grid.fillRow(17, "=", TRACK_COLOR);
    for (let y = 18; y < this.grid.rows; y++) {
      this.grid.fillRow(y, ".", GROUND_COLOR);
    }

    // train (foreground)
    const trainX = 10;
    for (let r = 0; r < TRAIN.length; r++) {
      const row = TRAIN[r];
      const gy = 12 + r;
      for (let c = 0; c < row.length; c++) {
        const gx = trainX + c;
        if (gx >= 0 && gx < this.grid.cols && row[c] !== " ") {
          const color = row[c] === "O" || row[c] === "(" || row[c] === ")" ? WHEEL_COLOR : TRAIN_COLOR;
          this.grid.setCell(gx, gy, row[c], color);
        }
      }
    }

    // smoke
    const smokeX = trainX + 2;
    const wobble = Math.sin(this.scroll * 2) * 1.5;
    for (let i = 0; i < 4; i++) {
      const sx = Math.round(smokeX - i * 2 + wobble);
      const sy = 11 - i;
      if (sx >= 0 && sx < this.grid.cols && sy >= 0) {
        this.grid.setCell(sx, sy, i < 2 ? "*" : ".", "#888899");
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = SKY_COLOR;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.scroll = 0; }
  dispose(): void { this.mountains = []; this.trees = []; }
}
