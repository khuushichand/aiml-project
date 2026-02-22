import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const DENSITY = " .:-=+*#%@";

export default class FractalZoom implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private centerX = -0.7435;
  private centerY = 0.1314;
  private baseScale = 3.5;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const zoom = this.baseScale * Math.pow(0.97, this.elapsed / 100);
    const cols = grid.cols;
    const rows = grid.rows;
    const maxIter = 40;
    const aspect = cols / rows * 0.5;

    for (let gy = 0; gy < rows; gy++) {
      for (let gx = 0; gx < cols; gx++) {
        const x0 = this.centerX + (gx / cols - 0.5) * zoom * aspect;
        const y0 = this.centerY + (gy / rows - 0.5) * zoom;

        let x = 0;
        let y = 0;
        let iter = 0;
        while (x * x + y * y <= 4 && iter < maxIter) {
          const tmp = x * x - y * y + x0;
          y = 2 * x * y + y0;
          x = tmp;
          iter++;
        }

        const idx = iter === maxIter ? 0 : Math.floor((iter / maxIter) * (DENSITY.length - 1));
        const ch = DENSITY[idx];

        const hue = (iter / maxIter) * 270;
        const sat = iter === maxIter ? 0 : 80;
        const lum = iter === maxIter ? 5 : 30 + (iter / maxIter) * 50;
        grid.setCell(gx, gy, ch, `hsl(${hue},${sat}%,${lum}%)`);
      }
    }

    const title = "tldw";
    const ty = Math.floor(rows / 2);
    grid.writeCentered(ty, title, "#ffffff");

    const cellW = this.w / cols;
    const cellH = this.h / rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
