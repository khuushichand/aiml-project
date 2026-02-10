import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Star { x: number; y: number; brightness: number; phase: number }
interface Constellation { stars: number[]; birth: number }

const STAR_CHARS = [".", "\u00B7", "*", "+"];
const DIM = "#334466";
const BRIGHT = "#ffffff";
const LINE_COLOR = "#223355";

export default class ConstellationMapEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private stars: Star[] = [];
  private constellations: Constellation[] = [];
  private nextConst = 2000;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.stars = [];
    for (let i = 0; i < 80; i++) {
      this.stars.push({
        x: Math.floor(Math.random() * this.grid.cols),
        y: Math.floor(Math.random() * this.grid.rows),
        brightness: 0.3 + Math.random() * 0.7,
        phase: Math.random() * Math.PI * 2,
      });
    }
    this.constellations = [];
    this.nextConst = 1000;
  }

  private makeConstellation(t: number): void {
    const count = 3 + Math.floor(Math.random() * 4);
    const indices: number[] = [];
    const startIdx = Math.floor(Math.random() * this.stars.length);
    for (let i = 0; i < count && indices.length < count; i++) {
      const idx = (startIdx + i * 7) % this.stars.length;
      if (!indices.includes(idx)) indices.push(idx);
    }
    this.constellations.push({ stars: indices, birth: t });
    if (this.constellations.length > 5) this.constellations.shift();
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed;
    if (elapsed > this.nextConst) {
      this.makeConstellation(elapsed);
      this.nextConst = elapsed + 3000 + Math.random() * 4000;
    }

    this.grid.clear("#05050f");
    const t = elapsed / 1000;

    // draw constellation lines
    for (const c of this.constellations) {
      const age = (elapsed - c.birth) / 1000;
      if (age > 10) continue;
      const alpha = age < 1 ? age : age > 8 ? (10 - age) / 2 : 1;
      if (alpha <= 0) continue;
      for (let i = 0; i < c.stars.length - 1; i++) {
        const a = this.stars[c.stars[i]];
        const b = this.stars[c.stars[i + 1]];
        this.drawLine(a.x, a.y, b.x, b.y, alpha);
      }
    }

    // draw stars with twinkling
    for (const s of this.stars) {
      const twinkle = (Math.sin(t * 2.5 + s.phase) + 1) / 2;
      const b = s.brightness * (0.4 + twinkle * 0.6);
      const ci = Math.floor(b * (STAR_CHARS.length - 1));
      const color = b > 0.7 ? BRIGHT : DIM;
      this.grid.setCell(s.x, s.y, STAR_CHARS[ci], color);
    }
  }

  private drawLine(x0: number, y0: number, x1: number, y1: number, _alpha: number): void {
    const dx = Math.abs(x1 - x0);
    const dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    let cx = x0, cy = y0;
    for (let i = 0; i < 80; i++) {
      if (cx >= 0 && cx < this.grid.cols && cy >= 0 && cy < this.grid.rows) {
        this.grid.setCell(cx, cy, "-", LINE_COLOR);
      }
      if (cx === x1 && cy === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; cx += sx; }
      if (e2 < dx) { err += dx; cy += sy; }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#05050f";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.constellations = []; this.time = 0; this.nextConst = 1000; }
  dispose(): void { this.stars = []; this.constellations = []; }
}
