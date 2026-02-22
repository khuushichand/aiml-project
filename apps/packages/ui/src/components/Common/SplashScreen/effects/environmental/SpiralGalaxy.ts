import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const STAR_CHARS = " .\u00B7*+\u2726";
const ARM_COLORS = ["#8888ff", "#ff8888", "#88ff88", "#ffff88"];

export default class SpiralGalaxyEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private stars: Array<{ angle: number; radius: number; arm: number; brightness: number }> = [];
  private cx = 40;
  private cy = 12;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.cx = this.grid.cols / 2;
    this.cy = this.grid.rows / 2;
    this.time = 0;
    this.stars = [];
    const numArms = 4;
    for (let i = 0; i < 350; i++) {
      const arm = i % numArms;
      const r = 1 + Math.random() * 18;
      const spread = (Math.random() - 0.5) * 0.6;
      this.stars.push({
        angle: (arm / numArms) * Math.PI * 2 + Math.log(r + 1) * 0.8 + spread,
        radius: r,
        arm,
        brightness: 0.3 + Math.random() * 0.7,
      });
    }
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#000005");

    // core glow
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -3; dx <= 3; dx++) {
        const gx = Math.round(this.cx + dx);
        const gy = Math.round(this.cy + dy);
        if (gx >= 0 && gx < this.grid.cols && gy >= 0 && gy < this.grid.rows) {
          this.grid.setCell(gx, gy, "*", "#ffffcc");
        }
      }
    }

    const rot = this.time * 0.2;
    for (const s of this.stars) {
      const a = s.angle + rot - s.radius * 0.02;
      const sx = Math.round(this.cx + Math.cos(a) * s.radius * 2);
      const sy = Math.round(this.cy + Math.sin(a) * s.radius * 0.7);
      if (sx >= 0 && sx < this.grid.cols && sy >= 0 && sy < this.grid.rows) {
        const twinkle = (Math.sin(this.time * 3 + s.angle * 10) + 1) / 2;
        const b = s.brightness * (0.5 + twinkle * 0.5);
        const ci = Math.floor(b * (STAR_CHARS.length - 1));
        this.grid.setCell(sx, sy, STAR_CHARS[Math.max(1, ci)], ARM_COLORS[s.arm]);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000005";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.time = 0;
  }

  dispose(): void {
    this.stars = [];
  }
}
