import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

type Point = { x: number; y: number };

function circlePoints(n: number, cx: number, cy: number, r: number): Point[] {
  const pts: Point[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    pts.push({ x: cx + Math.cos(a) * r * 2, y: cy + Math.sin(a) * r });
  }
  return pts;
}

function squarePoints(n: number, cx: number, cy: number, r: number): Point[] {
  const pts: Point[] = [];
  const perSide = Math.floor(n / 4);
  const corners = [
    { x: cx - r * 2, y: cy - r }, { x: cx + r * 2, y: cy - r },
    { x: cx + r * 2, y: cy + r }, { x: cx - r * 2, y: cy + r },
  ];
  for (let s = 0; s < 4; s++) {
    const a = corners[s], b = corners[(s + 1) % 4];
    for (let i = 0; i < perSide; i++) {
      const t = i / perSide;
      pts.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
    }
  }
  return pts.slice(0, n);
}

function trianglePoints(n: number, cx: number, cy: number, r: number): Point[] {
  const pts: Point[] = [];
  const verts = [
    { x: cx, y: cy - r },
    { x: cx + r * 2, y: cy + r },
    { x: cx - r * 2, y: cy + r },
  ];
  const perSide = Math.floor(n / 3);
  for (let s = 0; s < 3; s++) {
    const a = verts[s], b = verts[(s + 1) % 3];
    for (let i = 0; i < perSide; i++) {
      const t = i / perSide;
      pts.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
    }
  }
  return pts.slice(0, n);
}

const SHAPE_COLORS = ["#ff4488", "#44ff88", "#4488ff"];
const N = 64;

export default class MorphingShapeEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private shapes: Point[][] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    const cx = this.grid.cols / 2, cy = this.grid.rows / 2, r = 8;
    this.shapes = [circlePoints(N, cx, cy, r), squarePoints(N, cx, cy, r), trianglePoints(N, cx, cy, r)];
    this.time = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#0a0a14");
    const cycle = this.time * 0.4;
    const idx = Math.floor(cycle) % this.shapes.length;
    const next = (idx + 1) % this.shapes.length;
    const t = cycle - Math.floor(cycle);
    const smooth = t * t * (3 - 2 * t);
    const from = this.shapes[idx];
    const to = this.shapes[next];
    const color = SHAPE_COLORS[idx];

    for (let i = 0; i < N; i++) {
      const px = Math.round(from[i].x + (to[i].x - from[i].x) * smooth);
      const py = Math.round(from[i].y + (to[i].y - from[i].y) * smooth);
      if (px >= 0 && px < this.grid.cols && py >= 0 && py < this.grid.rows) {
        this.grid.setCell(px, py, "\u2588", color);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#0a0a14";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; }
  dispose(): void { this.shapes = []; }
}
