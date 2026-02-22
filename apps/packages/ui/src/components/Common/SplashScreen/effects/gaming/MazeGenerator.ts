import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class MazeGeneratorEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private mazeW = 39;
  private mazeH = 11;
  private maze: number[][] = []; // 0 = wall, 1 = path, 2 = visited
  private stack: { x: number; y: number }[] = [];
  private curX = 0;
  private curY = 0;
  private stepTimer = 0;
  private stepInterval = 30;
  private done = false;
  private doneTimer = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.initMaze();
  }

  private initMaze(): void {
    this.mazeW = 39;
    this.mazeH = 11;
    this.maze = Array.from({ length: this.mazeH * 2 + 1 }, () =>
      Array(this.mazeW * 2 + 1).fill(0)
    );
    // Mark all cells
    for (let r = 0; r < this.mazeH; r++) {
      for (let c = 0; c < this.mazeW; c++) {
        this.maze[r * 2 + 1][c * 2 + 1] = 1;
      }
    }
    this.curX = 0;
    this.curY = 0;
    this.maze[1][1] = 2;
    this.stack = [{ x: 0, y: 0 }];
    this.done = false;
    this.doneTimer = 0;
    this.stepTimer = 0;
  }

  private getUnvisitedNeighbors(cx: number, cy: number): { x: number; y: number; wx: number; wy: number }[] {
    const dirs = [
      { dx: 0, dy: -1 }, { dx: 1, dy: 0 },
      { dx: 0, dy: 1 }, { dx: -1, dy: 0 },
    ];
    const result: { x: number; y: number; wx: number; wy: number }[] = [];
    for (const d of dirs) {
      const nx = cx + d.dx;
      const ny = cy + d.dy;
      if (nx >= 0 && nx < this.mazeW && ny >= 0 && ny < this.mazeH) {
        if (this.maze[ny * 2 + 1][nx * 2 + 1] !== 2) {
          result.push({
            x: nx, y: ny,
            wx: cx * 2 + 1 + d.dx,
            wy: cy * 2 + 1 + d.dy,
          });
        }
      }
    }
    return result;
  }

  private step(): void {
    if (this.stack.length === 0) {
      this.done = true;
      return;
    }
    const current = this.stack[this.stack.length - 1];
    this.curX = current.x;
    this.curY = current.y;
    const neighbors = this.getUnvisitedNeighbors(current.x, current.y);
    if (neighbors.length > 0) {
      const next = neighbors[Math.floor(Math.random() * neighbors.length)];
      // Remove wall
      this.maze[next.wy][next.wx] = 2;
      // Mark visited
      this.maze[next.y * 2 + 1][next.x * 2 + 1] = 2;
      this.stack.push({ x: next.x, y: next.y });
    } else {
      this.stack.pop();
    }
  }

  update(_elapsed: number, dt: number): void {
    if (this.done) {
      this.doneTimer += dt;
      if (this.doneTimer > 2000) {
        this.initMaze();
      }
      return;
    }

    this.stepTimer += dt;
    const stepsPerFrame = Math.max(1, Math.floor(dt / this.stepInterval));
    for (let i = 0; i < stepsPerFrame && !this.done; i++) {
      this.step();
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    this.grid.writeCentered(0, "MAZE GENERATOR", "#ff0");

    const mRows = this.mazeH * 2 + 1;
    const mCols = this.mazeW * 2 + 1;
    const ox = 1;
    const oy = 1;

    for (let r = 0; r < mRows && r + oy < 24; r++) {
      for (let c = 0; c < mCols && c + ox < 80; c++) {
        const val = this.maze[r][c];
        const gx = c + ox;
        const gy = r + oy;
        if (val === 0) {
          this.grid.setCell(gx, gy, "▓", "#126");
        } else if (val === 2) {
          this.grid.setCell(gx, gy, " ", "#000");
        }
      }
    }

    // Cursor
    if (!this.done) {
      const cx = this.curX * 2 + 1 + ox;
      const cy = this.curY * 2 + 1 + oy;
      if (cx < 80 && cy < 24) {
        this.grid.setCell(cx, cy, "❖", "#ff0");
      }

      // Show stack head trail
      const trailLen = Math.min(this.stack.length, 8);
      for (let i = this.stack.length - 2; i >= Math.max(0, this.stack.length - trailLen); i--) {
        const s = this.stack[i];
        const sx = s.x * 2 + 1 + ox;
        const sy = s.y * 2 + 1 + oy;
        if (sx < 80 && sy < 24) {
          this.grid.setCell(sx, sy, "·", "#880");
        }
      }
    }

    const status = this.done ? "COMPLETE" : `GENERATING... (${this.stack.length} stack)`;
    this.grid.writeCentered(23, status, this.done ? "#0f0" : "#888");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.initMaze();
  }

  dispose(): void {
    this.maze = [];
    this.stack = [];
  }
}
