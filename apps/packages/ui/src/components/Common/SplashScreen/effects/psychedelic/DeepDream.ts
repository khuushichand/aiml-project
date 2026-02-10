import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const DENSITY = " .:-=+*#%@";

export default class DeepDream implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private field: number[][] = [];
  private hueBase = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.field = Array.from({ length: 24 }, () => new Array(80).fill(0));
    this.hueBase = 0;
  }

  private fractalNoise(x: number, y: number, t: number): number {
    let val = 0;
    let amp = 1;
    let freq = 1;
    for (let oct = 0; oct < 4; oct++) {
      const sx = x * freq * 0.08;
      const sy = y * freq * 0.12;
      val += amp * Math.sin(sx + t * 0.3) * Math.cos(sy + t * 0.2)
           + amp * 0.5 * Math.sin(sx * 2.3 + sy * 1.7 + t * 0.5);
      amp *= 0.5;
      freq *= 2.1;
    }
    return val;
  }

  update(elapsed: number, dt: number): void {
    const t = elapsed / 1000;
    this.hueBase = (t * 20) % 360;

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        // Self-similar fractal layers
        const n1 = this.fractalNoise(x, y, t);
        const n2 = this.fractalNoise(x + n1 * 3, y + n1 * 3, t * 0.7);
        const n3 = this.fractalNoise(x + n2 * 2, y + n2 * 2, t * 0.4);

        // Combine for dreamy morphing
        const combined = (n1 + n2 * 0.6 + n3 * 0.3) / 1.9;
        this.field[y][x] = combined;

        // Map to char density
        const norm = (combined + 1.5) / 3;
        const clamped = Math.max(0, Math.min(1, norm));
        const charIdx = Math.floor(clamped * (DENSITY.length - 1));

        // Rainbow color rotation
        const hue = (this.hueBase + x * 3 + y * 7 + combined * 60) % 360;
        const light = 35 + clamped * 40;
        this.grid.setCell(x, y, DENSITY[charIdx], `hsl(${hue},85%,${light}%)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.hueBase = 0;
    this.field = Array.from({ length: 24 }, () => new Array(80).fill(0));
  }

  dispose(): void {}
}
