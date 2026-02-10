import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

interface CellData {
  x: number;
  y: number;
  ch: string;
  color: string;
}

export default class PixelDissolveEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private cells: CellData[] = [];
  private duration = 2000;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.duration = (config?.duration as number) ?? 2000;

    const lines: string[] = (config?.lines as string[]) ?? [
      "tldw - Too Long; Didn't Watch",
      "",
      "Research Assistant",
      "& Media Platform",
    ];

    // Build cell list from content
    this.cells = [];
    const startY = Math.floor((24 - lines.length) / 2);
    for (let li = 0; li < lines.length; li++) {
      const line = lines[li];
      const cx = Math.floor((80 - line.length) / 2);
      for (let i = 0; i < line.length; i++) {
        if (line[i] !== " ") {
          this.cells.push({ x: cx + i, y: startY + li, ch: line[i], color: "rgb(0,220,0)" });
        }
      }
    }

    // Fisher-Yates shuffle for random reveal order
    for (let i = this.cells.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [this.cells[i], this.cells[j]] = [this.cells[j], this.cells[i]];
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const progress = Math.min(elapsed / this.duration, 1);
    const count = Math.floor(progress * this.cells.length);

    for (let i = 0; i < count; i++) {
      const c = this.cells[i];
      this.grid.setCell(c.x, c.y, c.ch, c.color);
    }

    // Sparkle effect at the frontier
    if (count < this.cells.length && count > 0) {
      const frontier = this.cells[count];
      this.grid.setCell(frontier.x, frontier.y, "\u2588", "rgb(255,255,255)");
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {}

  dispose(): void {
    this.cells = [];
  }
}
