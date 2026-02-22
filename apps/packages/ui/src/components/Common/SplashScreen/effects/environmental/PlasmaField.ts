import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const DENSITY = " .:;+=xX$&#@";

function hslToHex(h: number, s: number, l: number): string {
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

export default class PlasmaFieldEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#000000");

    for (let y = 0; y < this.grid.rows; y++) {
      for (let x = 0; x < this.grid.cols; x++) {
        const v1 = Math.sin(x * 0.12 + this.time);
        const v2 = Math.sin(y * 0.15 + this.time * 0.7);
        const v3 = Math.sin((x + y) * 0.1 + this.time * 1.3);
        const cx = x - this.grid.cols / 2;
        const cy = y - this.grid.rows / 2;
        const v4 = Math.sin(Math.sqrt(cx * cx + cy * cy) * 0.2 - this.time * 0.9);
        const val = (v1 + v2 + v3 + v4) / 4;
        const norm = (val + 1) / 2;
        const hue = (norm * 360 + this.time * 60) % 360;
        const ci = Math.floor(norm * (DENSITY.length - 1));
        this.grid.setCell(x, y, DENSITY[ci], hslToHex(hue, 0.8, 0.55));
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.time = 0;
    this.grid.clear("#000000");
  }

  dispose(): void { /* no resources */ }
}
