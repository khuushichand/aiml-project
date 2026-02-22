import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class TypewriterEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private text = "";
  private charDelay = 50;
  private cursorVisible = true;
  private lastCursorToggle = 0;
  private startX = 0;
  private startY = 12;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.text = (config?.text as string) ?? "tldw - Too Long; Didn't Watch :: Loading...";
    this.charDelay = (config?.char_delay as number) ?? 50;
    this.startX = Math.floor((80 - this.text.length) / 2);
    this.startY = (config?.row as number) ?? 12;
    this.cursorVisible = true;
    this.lastCursorToggle = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const charsToShow = Math.min(Math.floor(elapsed / this.charDelay), this.text.length);
    const typingDone = charsToShow >= this.text.length;

    for (let i = 0; i < charsToShow; i++) {
      this.grid.setCell(this.startX + i, this.startY, this.text[i], "rgb(0,255,0)");
    }

    // Cursor logic
    if (typingDone) {
      const cyclePeriod = 500;
      this.cursorVisible = Math.floor(elapsed / cyclePeriod) % 2 === 0;
    } else {
      const sinceLast = elapsed - this.lastCursorToggle;
      if (sinceLast > 80) {
        this.cursorVisible = true;
      }
      this.lastCursorToggle = elapsed;
    }

    if (this.cursorVisible) {
      const cursorX = this.startX + charsToShow;
      if (cursorX < 80) {
        this.grid.setCell(cursorX, this.startY, "\u2588", "rgb(0,255,0)");
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.cursorVisible = true;
    this.lastCursorToggle = 0;
  }

  dispose(): void {}
}
