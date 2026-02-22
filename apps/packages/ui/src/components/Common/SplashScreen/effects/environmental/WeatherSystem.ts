import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Particle { x: number; y: number; speed: number }

const enum Weather { Rain, Snow, Lightning, Clear }
const SKY_COLORS: Record<number, string> = {
  [Weather.Rain]: "#0a1122",
  [Weather.Snow]: "#1a1a2a",
  [Weather.Lightning]: "#0a0a1a",
  [Weather.Clear]: "#0a0a22",
};
const CLOUD_COLOR = "#556677";
const RAIN_COLOR = "#5588cc";
const SNOW_COLOR = "#ccddee";
const LIGHTNING_COLOR = "#ffffaa";
const STAR_COLOR = "#aabbcc";

export default class WeatherSystemEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private weather: Weather = Weather.Rain;
  private particles: Particle[] = [];
  private lightningTimer = 0;
  private lightningFlash = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.particles = [];
    this.weather = Weather.Rain;
  }

  update(elapsed: number, dt: number): void {
    this.time = elapsed / 1000;
    const step = dt / 16;
    const cycle = Math.floor(this.time / 8) % 4;
    this.weather = cycle as Weather;

    const bg = SKY_COLORS[this.weather];
    this.grid.clear(bg);

    // clouds for rain/snow/lightning
    if (this.weather !== Weather.Clear) {
      for (let ci = 0; ci < 3; ci++) {
        const cx = 10 + ci * 25 + Math.sin(this.time * 0.3 + ci) * 3;
        for (let dx = -5; dx <= 5; dx++) {
          const gx = Math.round(cx + dx);
          if (gx >= 0 && gx < this.grid.cols) {
            this.grid.setCell(gx, 2, "~", CLOUD_COLOR);
            if (Math.abs(dx) < 4) this.grid.setCell(gx, 3, "~", CLOUD_COLOR);
          }
        }
      }
    }

    // spawn particles
    if (this.weather === Weather.Rain && Math.random() < 0.5) {
      this.particles.push({ x: Math.floor(Math.random() * this.grid.cols), y: 4, speed: 0.6 + Math.random() * 0.3 });
    }
    if (this.weather === Weather.Snow && Math.random() < 0.3) {
      this.particles.push({ x: Math.floor(Math.random() * this.grid.cols), y: 4, speed: 0.15 + Math.random() * 0.1 });
    }

    // update particles
    for (const p of this.particles) {
      p.y += p.speed * step;
      if (this.weather === Weather.Snow) p.x += Math.sin(this.time + p.x) * 0.15;
    }
    this.particles = this.particles.filter(p => p.y < this.grid.rows - 1);

    // draw particles
    for (const p of this.particles) {
      const py = Math.round(p.y);
      const px = Math.round(p.x);
      if (px >= 0 && px < this.grid.cols && py >= 0 && py < this.grid.rows) {
        if (this.weather === Weather.Rain) {
          this.grid.setCell(px, py, "|", RAIN_COLOR);
        } else {
          this.grid.setCell(px, py, "*", SNOW_COLOR);
        }
      }
    }

    // lightning
    if (this.weather === Weather.Lightning) {
      this.lightningTimer -= dt;
      if (this.lightningTimer <= 0) {
        this.lightningFlash = 150;
        this.lightningTimer = 1500 + Math.random() * 3000;
        // draw bolt
        let bx = 20 + Math.floor(Math.random() * 40);
        for (let by = 3; by < this.grid.rows - 2; by++) {
          bx += Math.floor(Math.random() * 3) - 1;
          bx = Math.max(0, Math.min(this.grid.cols - 1, bx));
          this.grid.setCell(bx, by, "/", LIGHTNING_COLOR);
        }
      }
      this.lightningFlash = Math.max(0, this.lightningFlash - dt);
    }

    // clear weather: stars
    if (this.weather === Weather.Clear) {
      this.particles = [];
      for (let i = 0; i < 30; i++) {
        const sx = (i * 17 + 3) % this.grid.cols;
        const sy = (i * 7 + 1) % (this.grid.rows - 4);
        const twinkle = Math.sin(this.time * 3 + i) > 0.2;
        this.grid.setCell(sx, sy, twinkle ? "*" : ".", STAR_COLOR);
      }
    }

    // ground
    this.grid.fillRow(this.grid.rows - 1, this.weather === Weather.Snow ? "_" : ".", "#335533");

    const labels = ["Rain", "Snow", "Storm", "Clear Night"];
    this.grid.writeCentered(0, `[ ${labels[this.weather]} ]`, "#888899");
  }

  render(ctx: CanvasRenderingContext2D): void {
    const bg = this.lightningFlash > 50 ? "#333344" : (SKY_COLORS[this.weather] || "#0a0a1a");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.particles = []; this.time = 0; this.lightningFlash = 0; }
  dispose(): void { this.particles = []; }
}
