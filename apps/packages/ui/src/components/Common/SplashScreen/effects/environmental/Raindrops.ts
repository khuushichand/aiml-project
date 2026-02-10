import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Drop { x: number; y: number; speed: number }
interface Ripple { x: number; y: number; radius: number; maxRadius: number; life: number }

const RIPPLE_CHARS = ["\u00B7", "o", "O", "(", ")"];
const WATER_COLOR = "#113355";
const RIPPLE_COLOR = "#4488bb";
const DROP_COLOR = "#88ccff";

export default class RaindropsEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private drops: Drop[] = [];
  private ripples: Ripple[] = [];
  private waterLine = 16;
  private spawnRatePerSec = 2;
  private maxConcurrentRipples = 20;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.drops = [];
    this.ripples = [];
    this.waterLine = Math.floor(this.grid.rows * 0.65);
    const spawnRate = Number(config?.spawn_rate);
    this.spawnRatePerSec = Number.isFinite(spawnRate) ? Math.max(0, spawnRate) : 2;
    const maxRipples = Number(config?.max_concurrent_ripples);
    this.maxConcurrentRipples = Number.isFinite(maxRipples)
      ? Math.max(1, Math.floor(maxRipples))
      : 20;
  }

  update(_elapsed: number, dt: number): void {
    const step = dt / 16;

    // spawn drops based on configured per-second rate
    let spawnBudget = this.spawnRatePerSec * (dt / 1000);
    while (spawnBudget > 0) {
      if (Math.random() < Math.min(1, spawnBudget)) {
        this.drops.push({ x: Math.floor(Math.random() * this.grid.cols), y: 0, speed: 0.8 + Math.random() * 0.5 });
      }
      spawnBudget -= 1;
    }

    for (const d of this.drops) d.y += d.speed * step;

    // drops hitting water create ripples
    const landed = this.drops.filter(d => d.y >= this.waterLine);
    for (const d of landed) {
      if (this.ripples.length < this.maxConcurrentRipples) {
        this.ripples.push({ x: d.x, y: this.waterLine, radius: 0, maxRadius: 5 + Math.random() * 4, life: 1 });
      }
    }
    this.drops = this.drops.filter(d => d.y < this.waterLine);

    for (const r of this.ripples) {
      r.radius += 0.06 * step;
      r.life = 1 - r.radius / r.maxRadius;
    }
    this.ripples = this.ripples.filter(r => r.life > 0);

    this.grid.clear("#0a0a1a");

    // water surface
    for (let y = this.waterLine; y < this.grid.rows; y++) {
      this.grid.fillRow(y, "~", WATER_COLOR);
    }

    // ripples on water
    for (const r of this.ripples) {
      const rad = Math.round(r.radius);
      for (let dx = -rad; dx <= rad; dx++) {
        const px = r.x + dx;
        if (px < 0 || px >= this.grid.cols) continue;
        const dist = Math.abs(dx);
        if (dist >= rad - 1 && dist <= rad) {
          const ry = this.waterLine;
          if (ry < this.grid.rows) {
            const ci = Math.min(rad, RIPPLE_CHARS.length - 1);
            this.grid.setCell(px, ry, RIPPLE_CHARS[ci], RIPPLE_COLOR);
          }
        }
      }
    }

    // falling drops
    for (const d of this.drops) {
      const iy = Math.round(d.y);
      if (iy >= 0 && iy < this.grid.rows) {
        this.grid.setCell(d.x, iy, "|", DROP_COLOR);
        if (iy > 0) this.grid.setCell(d.x, iy - 1, "'", DROP_COLOR);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#0a0a1a";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.drops = []; this.ripples = []; }
  dispose(): void { this.drops = []; this.ripples = []; }
}
