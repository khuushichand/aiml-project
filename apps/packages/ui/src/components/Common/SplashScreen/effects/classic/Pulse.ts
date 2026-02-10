import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class PulseEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private baseR = 0;
  private baseG = 200;
  private baseB = 0;
  private cycleMs = 1200;
  private contentLines: string[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    const color = config?.color as number[] | undefined;
    if (color && color.length >= 3) {
      this.baseR = color[0];
      this.baseG = color[1];
      this.baseB = color[2];
    }
    this.cycleMs = (config?.cycle_ms as number) ?? 1200;
    this.contentLines = (config?.lines as string[]) ?? ["tldw", "", "Loading..."];
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const t = (elapsed / this.cycleMs) * Math.PI * 2;
    const factor = 0.3 + 0.7 * ((Math.sin(t) + 1) / 2);
    const r = Math.floor(this.baseR * factor);
    const g = Math.floor(this.baseG * factor);
    const b = Math.floor(this.baseB * factor);
    const color = `rgb(${r},${g},${b})`;

    const startY = Math.floor((24 - this.contentLines.length) / 2);
    for (let i = 0; i < this.contentLines.length; i++) {
      const line = this.contentLines[i];
      if (line.length > 0) {
        this.grid.writeCentered(startY + i, line, color);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {}

  dispose(): void {
    this.contentLines = [];
  }
}
