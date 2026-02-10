import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const ORGANIC = " .oO@*~+=";

export default class ShroomVision implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private breathPhase = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.breathPhase = 0;
  }

  update(elapsed: number, dt: number): void {
    const t = elapsed / 1000;
    this.breathPhase = t;

    // Breathing scale factor (pulsing expand/contract)
    const breath = 1 + 0.3 * Math.sin(t * 0.8);
    const breathSlow = 1 + 0.15 * Math.sin(t * 0.5 + 1.2);

    const cx = 40;
    const cy = 12;

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        // Warp coordinates sinusoidally
        const warpX = x + Math.sin(y * 0.3 + t * 1.2) * 3 * breath;
        const warpY = y + Math.cos(x * 0.15 + t * 0.9) * 2 * breathSlow;

        const dx = (warpX - cx) / 40;
        const dy = (warpY - cy) / 12;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Layered organic waves
        const wave1 = Math.sin(dist * 6 - t * 2) * 0.5 + 0.5;
        const wave2 = Math.sin(dx * 4 + Math.sin(dy * 3 + t)) * 0.5 + 0.5;
        const wave3 = Math.cos(dist * 3 + Math.atan2(dy, dx) * 2 - t * 1.5) * 0.5 + 0.5;

        const combined = wave1 * 0.4 + wave2 * 0.3 + wave3 * 0.3;
        const charIdx = Math.floor(combined * (ORGANIC.length - 1));

        // Warm spectrum: reds, oranges, yellows, magentas
        const hue = (30 + Math.sin(t * 0.3 + dist * 2) * 40 + combined * 30) % 360;
        const absHue = hue < 0 ? hue + 360 : hue;
        const sat = 70 + combined * 30;
        const light = 30 + combined * 40;

        this.grid.setCell(x, y, ORGANIC[charIdx], `hsl(${absHue},${sat}%,${light}%)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.breathPhase = 0;
  }

  dispose(): void {}
}
