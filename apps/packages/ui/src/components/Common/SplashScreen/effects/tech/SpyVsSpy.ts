import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const SPY_LEFT = [
  "  O  ",
  " /|\\ ",
  " / \\ ",
];

const SPY_RIGHT = [
  "  O  ",
  " /|\\ ",
  " / \\ ",
];

const CLASSIFIED_LINES = [
  "AGENT STATUS: ACTIVE",
  "CLEARANCE: TOP SECRET",
  "MISSION: MEDIA ANALYSIS",
  "TARGET: ALL MEDIA FORMATS",
  "CODENAME: TLDW",
  "STATUS: OPERATIONAL",
];

export default class SpyVsSpy implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private revealedChars = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
    this.revealedChars = Math.floor(elapsed / 50);
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Top border - classified stamp
    const border = "#".repeat(80);
    grid.writeString(0, 0, border, "#ff0000");
    grid.writeCentered(1, "*** C L A S S I F I E D ***", "#ff4444");
    grid.writeString(0, 2, border, "#ff0000");

    // Left spy
    const lx = 8;
    const sy = 5;
    for (let i = 0; i < SPY_LEFT.length; i++) {
      grid.writeString(lx, sy + i, SPY_LEFT[i], "#cccccc");
    }
    grid.writeString(lx - 1, sy + 3, "AGENT A", "#00ff88");

    // Right spy
    const rx = 65;
    for (let i = 0; i < SPY_RIGHT.length; i++) {
      grid.writeString(rx, sy + i, SPY_RIGHT[i], "#cccccc");
    }
    grid.writeString(rx - 1, sy + 3, "AGENT B", "#ff8800");

    // Dashed line between them
    const dashY = sy + 1;
    for (let x = lx + 6; x < rx; x++) {
      const ch = x % 2 === 0 ? "-" : " ";
      grid.setCell(x, dashY, ch, "#666666");
    }

    // Dossier box
    const boxLeft = 20;
    const boxRight = 59;
    const boxTop = 10;
    grid.writeString(boxLeft, boxTop, "+" + "-".repeat(boxRight - boxLeft - 1) + "+", "#888888");
    grid.writeString(boxLeft, boxTop + CLASSIFIED_LINES.length + 1, "+" + "-".repeat(boxRight - boxLeft - 1) + "+", "#888888");

    // Classified text with typewriter reveal
    let totalChars = 0;
    for (let i = 0; i < CLASSIFIED_LINES.length; i++) {
      const line = CLASSIFIED_LINES[i];
      grid.setCell(boxLeft, boxTop + 1 + i, "|", "#888888");
      grid.setCell(boxRight, boxTop + 1 + i, "|", "#888888");

      for (let c = 0; c < line.length; c++) {
        if (totalChars < this.revealedChars) {
          grid.setCell(boxLeft + 2 + c, boxTop + 1 + i, line[c], "#00ff00");
        }
        totalChars++;
      }
    }

    // Scan line effect
    const scanY = Math.floor(this.elapsed / 150) % 24;
    for (let x = 0; x < 80; x++) {
      const ch = grid.getChar(x, scanY);
      if (ch !== " ") {
        grid.setCell(x, scanY, ch, "#ffffff22");
      }
    }

    // Footer
    grid.writeString(0, 21, border, "#ff0000");
    grid.writeCentered(22, "EYES ONLY - tldw Intelligence Division", "#ff6666");
    grid.writeString(0, 23, border, "#ff0000");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.revealedChars = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
