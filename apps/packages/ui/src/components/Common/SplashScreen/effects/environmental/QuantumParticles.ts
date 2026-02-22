import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";
import { ParticlePool } from "../../engine/ParticlePool";

const ORBITAL_CHARS = ".\u00B7*+o\u25E6";
const ORBITAL_COLORS = ["#4488ff", "#66aaff", "#88ccff", "#aaddff", "#ff88aa", "#ffaa66"];

export default class QuantumParticlesEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private pool = new ParticlePool(500);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private cx = 40;
  private cy = 12;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.cx = this.grid.cols / 2;
    this.cy = this.grid.rows / 2;
    this.time = 0;
    this.spawnOrbital(0);
  }

  private spawnOrbital(t: number): void {
    for (let i = 0; i < 120; i++) {
      const shell = 1 + Math.floor(Math.random() * 3);
      const angle = Math.random() * Math.PI * 2;
      const radius = shell * 4 + (Math.random() - 0.5) * 3;
      const speed = (0.5 + Math.random() * 0.5) / shell;
      const ci = Math.floor(Math.random() * ORBITAL_CHARS.length);
      const colIdx = Math.floor(Math.random() * ORBITAL_COLORS.length);
      this.pool.spawn({
        x: this.cx + Math.cos(angle + t) * radius,
        y: this.cy + Math.sin(angle + t) * radius * 0.5,
        vx: -Math.sin(angle) * speed,
        vy: Math.cos(angle) * speed * 0.5,
        char: ORBITAL_CHARS[ci],
        color: ORBITAL_COLORS[colIdx],
        life: 2000 + Math.random() * 3000,
        maxLife: 5000,
      });
    }
  }

  update(elapsed: number, dt: number): void {
    this.time = elapsed / 1000;
    this.pool.update(dt);

    if (this.pool.alive().length < 60) {
      this.spawnOrbital(this.time);
    }

    this.grid.clear("#000008");
    this.pool.toGrid(this.grid);
    this.grid.setCell(Math.round(this.cx), Math.round(this.cy), "@", "#ffffff");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000008";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.pool.clear();
    this.time = 0;
  }

  dispose(): void {
    this.pool.clear();
  }
}
