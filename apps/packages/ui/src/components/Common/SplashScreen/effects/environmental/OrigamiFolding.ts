import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

type Point = { x: number; y: number };
type Frame = Point[][];

const PAPER_COLOR = "#ddccbb";
const FOLD_COLOR = "#998877";
const BG = "#1a1a22";

function lerp(a: number, b: number, t: number): number { return a + (b - a) * t; }
function lerpPt(a: Point, b: Point, t: number): Point {
  return { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) };
}

// Each frame is an array of line segments (pairs of points)
const FRAMES: Frame[] = [
  // Step 0: flat square
  [
    [{ x: -12, y: -6 }, { x: 12, y: -6 }],
    [{ x: 12, y: -6 }, { x: 12, y: 6 }],
    [{ x: 12, y: 6 }, { x: -12, y: 6 }],
    [{ x: -12, y: 6 }, { x: -12, y: -6 }],
  ],
  // Step 1: triangle fold
  [
    [{ x: -12, y: 6 }, { x: 12, y: 6 }],
    [{ x: 12, y: 6 }, { x: 0, y: -6 }],
    [{ x: 0, y: -6 }, { x: -12, y: 6 }],
    [{ x: -6, y: 0 }, { x: 6, y: 0 }],
  ],
  // Step 2: kite shape
  [
    [{ x: 0, y: -8 }, { x: 8, y: 0 }],
    [{ x: 8, y: 0 }, { x: 0, y: 8 }],
    [{ x: 0, y: 8 }, { x: -8, y: 0 }],
    [{ x: -8, y: 0 }, { x: 0, y: -8 }],
    [{ x: 0, y: -8 }, { x: 0, y: 8 }],
  ],
  // Step 3: bird base
  [
    [{ x: 0, y: -8 }, { x: 6, y: -2 }],
    [{ x: 6, y: -2 }, { x: 3, y: 6 }],
    [{ x: 3, y: 6 }, { x: -3, y: 6 }],
    [{ x: -3, y: 6 }, { x: -6, y: -2 }],
    [{ x: -6, y: -2 }, { x: 0, y: -8 }],
    [{ x: 0, y: -8 }, { x: 0, y: 6 }],
  ],
  // Step 4: crane shape
  [
    [{ x: -10, y: -2 }, { x: -3, y: 0 }], // head/neck
    [{ x: -3, y: 0 }, { x: 0, y: -4 }],    // body top
    [{ x: 0, y: -4 }, { x: 5, y: -6 }],     // wing up
    [{ x: 0, y: -4 }, { x: 5, y: -1 }],     // wing down
    [{ x: 5, y: -6 }, { x: 5, y: -1 }],     // wing tip
    [{ x: -3, y: 0 }, { x: 3, y: 3 }],      // body
    [{ x: 3, y: 3 }, { x: 8, y: 5 }],       // tail
    [{ x: -10, y: -2 }, { x: -12, y: -4 }], // beak
  ],
];

const STEP_LABELS = ["Flat Paper", "Triangle Fold", "Kite Fold", "Bird Base", "Crane"];

export default class OrigamiFoldingEffect implements SplashEffect {
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
    this.grid.clear(BG);
    const cycle = this.time * 0.3;
    const frameIdx = Math.floor(cycle) % FRAMES.length;
    const nextIdx = (frameIdx + 1) % FRAMES.length;
    const t = cycle - Math.floor(cycle);
    const smooth = t * t * (3 - 2 * t);

    const from = FRAMES[frameIdx];
    const to = FRAMES[nextIdx];
    const cx = this.grid.cols / 2;
    const cy = this.grid.rows / 2;

    const maxLines = Math.max(from.length, to.length);
    for (let i = 0; i < maxLines; i++) {
      const fi = i < from.length ? i : from.length - 1;
      const ti = i < to.length ? i : to.length - 1;
      const a = lerpPt(from[fi][0], to[ti][0], smooth);
      const b = lerpPt(from[fi][1], to[ti][1], smooth);
      this.drawLine(Math.round(cx + a.x * 2), Math.round(cy + a.y), Math.round(cx + b.x * 2), Math.round(cy + b.y));
    }

    const label = STEP_LABELS[frameIdx];
    this.grid.writeCentered(1, `[ ${label} ]`, "#aaaacc");
    this.grid.writeCentered(this.grid.rows - 2, "Origami Crane", PAPER_COLOR);
  }

  private drawLine(x0: number, y0: number, x1: number, y1: number): void {
    const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx - dy, cx = x0, cy = y0;
    for (let i = 0; i < 100; i++) {
      if (cx >= 0 && cx < this.grid.cols && cy >= 0 && cy < this.grid.rows) {
        const ch = dx > dy ? "-" : (dy > dx ? "|" : "/");
        this.grid.setCell(cx, cy, ch, FOLD_COLOR);
      }
      if (cx === x1 && cy === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; cx += sx; }
      if (e2 < dx) { err += dx; cy += sy; }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; }
  dispose(): void { /* nothing */ }
}
