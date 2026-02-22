import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";
import { ParticlePool } from "../../engine/ParticlePool";

const BURST_COLORS = ["#ff4444", "#44ff44", "#4444ff", "#ffff44", "#ff44ff", "#44ffff", "#ff8844", "#ffffff"];
const SPARK_CHARS = ["*", "+", ".", "\u00B7", "o"];

export default class FireworksEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private pool = new ParticlePool(500);
  private cellW = 0;
  private cellH = 0;
  private rockets: Array<{ x: number; y: number; vy: number; targetY: number; color: string }> = [];
  private nextLaunch = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.rockets = [];
    this.nextLaunch = 300;
  }

  private burst(x: number, y: number, color: string): void {
    const count = 25 + Math.floor(Math.random() * 20);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 + (Math.random() - 0.5) * 0.3;
      const speed = 0.03 + Math.random() * 0.06;
      this.pool.spawn({
        x, y,
        vx: Math.cos(angle) * speed * 2,
        vy: Math.sin(angle) * speed,
        char: SPARK_CHARS[Math.floor(Math.random() * SPARK_CHARS.length)],
        color,
        life: 1000 + Math.random() * 1500,
        maxLife: 2500,
      });
    }
  }

  update(elapsed: number, dt: number): void {
    const step = dt / 16;

    if (elapsed > this.nextLaunch) {
      const color = BURST_COLORS[Math.floor(Math.random() * BURST_COLORS.length)];
      this.rockets.push({
        x: 10 + Math.floor(Math.random() * 60),
        y: this.grid.rows - 1,
        vy: -0.15 - Math.random() * 0.1,
        targetY: 3 + Math.floor(Math.random() * 8),
        color,
      });
      this.nextLaunch = elapsed + 500 + Math.random() * 1500;
    }

    // update rockets
    for (const r of this.rockets) {
      r.y += r.vy * step;
    }
    const exploded = this.rockets.filter(r => r.y <= r.targetY);
    for (const r of exploded) {
      this.burst(r.x, Math.round(r.y), r.color);
    }
    this.rockets = this.rockets.filter(r => r.y > r.targetY);

    // apply gravity to particles by adjusting vy through spawned state
    this.pool.update(dt);

    this.grid.clear("#050508");
    this.pool.toGrid(this.grid);

    // draw rockets
    for (const r of this.rockets) {
      const ry = Math.round(r.y);
      if (ry >= 0 && ry < this.grid.rows) {
        this.grid.setCell(r.x, ry, "|", r.color);
        if (ry + 1 < this.grid.rows) this.grid.setCell(r.x, ry + 1, ".", "#ff8800");
      }
    }

    // ground line
    this.grid.fillRow(this.grid.rows - 1, "_", "#222222");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#050508";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.rockets = []; this.pool.clear(); this.nextLaunch = 300; }
  dispose(): void { this.rockets = []; this.pool.clear(); }
}
