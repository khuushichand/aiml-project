import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Star {
  x: number;
  y: number;
  z: number;
}

const STAR_CHARS = ["\u00B7", ".", "*", "+"];
const STAR_COLORS = ["#444466", "#6666aa", "#8888cc", "#bbbbff", "#ffffff"];

export default class StarfieldEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private stars: Star[] = [];
  private speed = 0.015;
  private starCount = 200;
  private cx = 40;
  private cy = 12;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.cx = this.grid.cols / 2;
    this.cy = this.grid.rows / 2;
    const numStars = Number(config?.num_stars);
    this.starCount = Number.isFinite(numStars) ? Math.max(10, Math.floor(numStars)) : 200;
    const warpFactor = Number(config?.warp_factor);
    this.speed = Number.isFinite(warpFactor)
      ? Math.max(0.002, 0.01 + warpFactor * 0.04)
      : 0.015;
    this.stars = [];
    for (let i = 0; i < this.starCount; i++) {
      this.stars.push(this.makeStar());
    }
  }

  private makeStar(): Star {
    return {
      x: (Math.random() - 0.5) * 160,
      y: (Math.random() - 0.5) * 80,
      z: Math.random() * 1.0,
    };
  }

  update(_elapsed: number, dt: number): void {
    this.grid.clear("#000005");

    for (const star of this.stars) {
      star.z -= this.speed * (dt / 16);
      if (star.z <= 0.01) {
        Object.assign(star, this.makeStar());
        star.z = 1.0;
      }

      const sx = Math.round(this.cx + star.x / star.z);
      const sy = Math.round(this.cy + star.y / star.z);

      if (sx >= 0 && sx < this.grid.cols && sy >= 0 && sy < this.grid.rows) {
        const brightness = 1 - star.z;
        const ci = Math.floor(brightness * (STAR_CHARS.length - 1));
        const colIdx = Math.floor(brightness * (STAR_COLORS.length - 1));
        this.grid.setCell(sx, sy, STAR_CHARS[ci], STAR_COLORS[colIdx]);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000005";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.stars = [];
    for (let i = 0; i < this.starCount; i++) this.stars.push(this.makeStar());
  }

  dispose(): void {
    this.stars = [];
  }
}
