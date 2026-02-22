import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class FadeEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private duration = 1000;
  private contentLines: string[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.duration = (config?.duration as number) ?? 1000;
    this.contentLines = (config?.lines as string[]) ?? [
      "",
      "tldw - Too Long; Didn't Watch",
      "",
      "Research Assistant & Media Platform",
    ];
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const alpha = Math.min(elapsed / this.duration, 1);
    const brightness = Math.floor(alpha * 220);
    const color = `rgb(${brightness},${brightness},${brightness})`;

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
