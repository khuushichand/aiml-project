import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class LoadingBarEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private fillChar = "\u2588";
  private emptyChar = "\u2591";
  private barWidth = 20;
  private duration = 2000;
  private textAbove = "Loading tldw...";

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.fillChar = (config?.fill_char as string) ?? "\u2588";
    this.emptyChar = (config?.empty_char as string) ?? "\u2591";
    this.barWidth = (config?.bar_width as number) ?? 20;
    this.duration = (config?.duration as number) ?? 2000;
    this.textAbove = (config?.text_above as string) ?? "Loading tldw...";
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const progress = Math.min(elapsed / this.duration, 1);
    const filled = Math.floor(progress * this.barWidth);
    const pct = Math.floor(progress * 100);

    const barY = 12;
    const textY = barY - 2;

    // Title text
    this.grid.writeCentered(textY, this.textAbove, "rgb(200,200,200)");

    // Build bar string
    const barStr =
      "[" +
      this.fillChar.repeat(filled) +
      this.emptyChar.repeat(this.barWidth - filled) +
      "]";
    const barX = Math.floor((80 - barStr.length) / 2);

    for (let i = 0; i < barStr.length; i++) {
      const ch = barStr[i];
      const isFill = i > 0 && i <= filled;
      const color = isFill ? "rgb(0,255,0)" : "rgb(100,100,100)";
      this.grid.setCell(barX + i, barY, ch, color);
    }

    // Percentage text
    const pctStr = `${pct}%`;
    this.grid.writeCentered(barY + 1, pctStr, "rgb(200,200,200)");

    // Spinner animation
    const spinChars = ["|", "/", "-", "\\"];
    const spinIdx = Math.floor(elapsed / 100) % spinChars.length;
    if (progress < 1) {
      this.grid.setCell(barX + barStr.length + 1, barY, spinChars[spinIdx], "rgb(0,200,0)");
    } else {
      this.grid.writeCentered(barY + 3, "Complete!", "rgb(0,255,0)");
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {}

  dispose(): void {}
}
