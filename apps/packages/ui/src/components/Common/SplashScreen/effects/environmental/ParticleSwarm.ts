import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const SWARM_CHARS = [".", "\u00B7", "*", "o"];
const SWARM_COLORS = ["#44aaff", "#66ccff", "#88ddff", "#aaeeff"];
const TRAIL_COLOR = "#113344";

export default class ParticleSwarmEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private trails: number[] = [];
  private cols = 80;
  private rows = 24;
  private boids: Array<{ x: number; y: number; vx: number; vy: number }> = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.cols;
    this.cellH = height / this.rows;
    this.trails = new Array(this.cols * this.rows).fill(0);
    this.boids = [];
    for (let i = 0; i < 60; i++) {
      this.boids.push({
        x: Math.random() * this.cols,
        y: Math.random() * this.rows,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.3,
      });
    }
  }

  update(_elapsed: number, dt: number): void {
    const step = dt / 16;

    // decay trails
    for (let i = 0; i < this.trails.length; i++) {
      this.trails[i] *= 0.95;
    }

    // boids rules
    for (const b of this.boids) {
      let sepX = 0, sepY = 0, alignX = 0, alignY = 0, cohX = 0, cohY = 0;
      let neighbors = 0;

      for (const o of this.boids) {
        if (o === b) continue;
        const dx = o.x - b.x, dy = o.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 12) {
          neighbors++;
          alignX += o.vx;
          alignY += o.vy;
          cohX += o.x;
          cohY += o.y;
          if (dist < 3) {
            sepX -= dx / (dist + 0.1);
            sepY -= dy / (dist + 0.1);
          }
        }
      }

      if (neighbors > 0) {
        alignX /= neighbors; alignY /= neighbors;
        cohX = cohX / neighbors - b.x; cohY = cohY / neighbors - b.y;
        b.vx += sepX * 0.05 + (alignX - b.vx) * 0.02 + cohX * 0.01;
        b.vy += sepY * 0.05 + (alignY - b.vy) * 0.02 + cohY * 0.01;
      }

      // speed limit
      const speed = Math.sqrt(b.vx * b.vx + b.vy * b.vy);
      if (speed > 0.6) { b.vx = (b.vx / speed) * 0.6; b.vy = (b.vy / speed) * 0.6; }

      b.x += b.vx * step;
      b.y += b.vy * step;

      // wrap
      if (b.x < 0) b.x += this.cols;
      if (b.x >= this.cols) b.x -= this.cols;
      if (b.y < 0) b.y += this.rows;
      if (b.y >= this.rows) b.y -= this.rows;

      // leave trail
      const ix = Math.floor(b.x), iy = Math.floor(b.y);
      if (ix >= 0 && ix < this.cols && iy >= 0 && iy < this.rows) {
        this.trails[iy * this.cols + ix] = 1;
      }
    }

    this.grid.clear("#050510");

    // draw trails
    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.cols; x++) {
        const t = this.trails[y * this.cols + x];
        if (t > 0.1) this.grid.setCell(x, y, ".", TRAIL_COLOR);
      }
    }

    // draw boids
    for (const b of this.boids) {
      const ix = Math.round(b.x), iy = Math.round(b.y);
      if (ix >= 0 && ix < this.cols && iy >= 0 && iy < this.rows) {
        const ci = Math.floor(Math.random() * SWARM_CHARS.length);
        this.grid.setCell(ix, iy, SWARM_CHARS[ci], SWARM_COLORS[ci]);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#050510";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.trails.fill(0); }
  dispose(): void { this.boids = []; this.trails = []; }
}
