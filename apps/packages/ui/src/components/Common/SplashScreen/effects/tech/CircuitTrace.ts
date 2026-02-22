import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

interface Trace {
  x: number;
  y: number;
  dx: number;
  dy: number;
  length: number;
  drawn: number;
  color: string;
  startTime: number;
}

const TRACE_COLORS = ["#00ff88", "#00ccff", "#ffcc00", "#ff6688", "#88ff00"];

export default class CircuitTrace implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private traces: Trace[] = [];
  private board: { ch: string; color: string }[][] = [];
  private nextTraceTime = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private initBoard(): void {
    this.board = [];
    for (let y = 0; y < 24; y++) {
      this.board[y] = [];
      for (let x = 0; x < 80; x++) {
        this.board[y][x] = { ch: " ", color: "#111111" };
      }
    }
  }

  private spawnTrace(): void {
    const edge = Math.floor(Math.random() * 4);
    let x: number, y: number, dx: number, dy: number;
    if (edge === 0) { x = Math.floor(Math.random() * 80); y = 0; dx = 0; dy = 1; }
    else if (edge === 1) { x = Math.floor(Math.random() * 80); y = 23; dx = 0; dy = -1; }
    else if (edge === 2) { x = 0; y = Math.floor(Math.random() * 24); dx = 1; dy = 0; }
    else { x = 79; y = Math.floor(Math.random() * 24); dx = -1; dy = 0; }

    this.traces.push({
      x, y, dx, dy,
      length: 10 + Math.floor(Math.random() * 30),
      drawn: 0,
      color: TRACE_COLORS[Math.floor(Math.random() * TRACE_COLORS.length)],
      startTime: this.elapsed,
    });
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    if (elapsed > this.nextTraceTime) {
      this.spawnTrace();
      this.nextTraceTime = elapsed + 200 + Math.random() * 500;
    }

    for (const trace of this.traces) {
      if (trace.drawn >= trace.length) continue;
      const stepTime = (elapsed - trace.startTime) / 40;
      while (trace.drawn < Math.min(stepTime, trace.length)) {
        const { x, y } = trace;
        if (x >= 0 && x < 80 && y >= 0 && y < 24) {
          let ch: string;
          if (trace.dx !== 0) ch = "\u2500";
          else ch = "\u2502";

          // Random direction change
          if (Math.random() < 0.15 && trace.drawn > 0) {
            if (trace.dx !== 0) {
              ch = trace.dy > 0 ? (trace.dx > 0 ? "\u2510" : "\u250C") : (trace.dx > 0 ? "\u2518" : "\u2514");
              const oldDx = trace.dx;
              trace.dx = 0;
              trace.dy = oldDx > 0 ? (Math.random() > 0.5 ? 1 : -1) : (Math.random() > 0.5 ? 1 : -1);
            } else {
              ch = trace.dx > 0 ? (trace.dy > 0 ? "\u2518" : "\u2510") : (trace.dy > 0 ? "\u2514" : "\u250C");
              const oldDy = trace.dy;
              trace.dy = 0;
              trace.dx = oldDy > 0 ? (Math.random() > 0.5 ? 1 : -1) : (Math.random() > 0.5 ? 1 : -1);
            }
          }

          this.board[y][x] = { ch, color: trace.color };
        }
        trace.x += trace.dx;
        trace.y += trace.dy;
        trace.x = Math.max(0, Math.min(79, trace.x));
        trace.y = Math.max(0, Math.min(23, trace.y));
        trace.drawn++;
      }

      // Node at end
      if (trace.drawn >= trace.length && trace.x >= 0 && trace.x < 80 && trace.y >= 0 && trace.y < 24) {
        this.board[trace.y][trace.x] = { ch: "O", color: "#ffffff" };
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const cell = this.board[y][x];
        if (cell.ch !== " ") {
          grid.setCell(x, y, cell.ch, cell.color);
        }
      }
    }

    grid.writeCentered(12, " tldw ", "#ffffff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.traces = [];
    this.nextTraceTime = 0;
    this.initBoard();
    this.grid.clear();
  }

  dispose(): void {
    this.traces = [];
    this.board = [];
    this.grid.clear();
  }
}
