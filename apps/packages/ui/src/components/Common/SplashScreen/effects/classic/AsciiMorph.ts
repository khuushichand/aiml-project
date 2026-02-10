import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";
import { getAsciiArt } from "../../../../../data/splash-ascii-art";

interface MorphCell {
  x: number;
  y: number;
  fromCh: string;
  toCh: string;
  transitionPoint: number; // 0-1 when this cell switches
}

export default class AsciiMorphEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private morphCells: MorphCell[] = [];
  private duration = 2000;

  private getArtLinesFromName(name: unknown): string[] | null {
    if (typeof name !== "string" || !name.trim()) return null;
    const art = getAsciiArt(name);
    return art.replace(/\r/g, "").split("\n");
  }

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.duration = (config?.duration as number) ?? 2000;

    const namedStartArt = this.getArtLinesFromName(config?.start_art_name);
    const startArt: string[] = namedStartArt ?? (config?.start_art as string[]) ?? [
      "  ####  ",
      " #    # ",
      " #    # ",
      "  ####  ",
      " #    # ",
      " #    # ",
      "  ####  ",
    ];
    const namedEndArt = this.getArtLinesFromName(config?.end_art_name);
    const endArt: string[] = namedEndArt ?? (config?.end_art as string[]) ?? [
      " ###### ",
      "   ##   ",
      "   ##   ",
      "   ##   ",
      "   ##   ",
      "   ##   ",
      "   ##   ",
    ];

    // Build morph cells from the union of both arts
    this.morphCells = [];
    const maxLines = Math.max(startArt.length, endArt.length);
    const maxWidth = Math.max(...startArt.map((l) => l.length), ...endArt.map((l) => l.length));
    const ox = Math.floor((80 - maxWidth) / 2);
    const oy = Math.floor((24 - maxLines) / 2);

    for (let row = 0; row < maxLines; row++) {
      const sLine = startArt[row] ?? "";
      const eLine = endArt[row] ?? "";
      const lineLen = Math.max(sLine.length, eLine.length);
      for (let col = 0; col < lineLen; col++) {
        const fromCh = col < sLine.length ? sLine[col] : " ";
        const toCh = col < eLine.length ? eLine[col] : " ";
        if (fromCh !== " " || toCh !== " ") {
          this.morphCells.push({
            x: ox + col,
            y: oy + row,
            fromCh,
            toCh,
            transitionPoint: Math.random(),
          });
        }
      }
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const progress = Math.min(elapsed / this.duration, 1);
    const transChars = "@#%&*+=-~:.";

    for (const cell of this.morphCells) {
      let ch: string;
      let color: string;

      if (progress < cell.transitionPoint * 0.8) {
        // Still showing start
        ch = cell.fromCh;
        color = "rgb(0,180,255)";
      } else if (progress < cell.transitionPoint) {
        // Transitioning: show random intermediate chars
        ch = transChars[Math.floor(Math.random() * transChars.length)];
        color = "rgb(255,255,0)";
      } else {
        // Show end
        ch = cell.toCh;
        color = "rgb(0,255,100)";
      }

      if (ch !== " ") {
        this.grid.setCell(cell.x, cell.y, ch, color);
      }
    }

    // Label
    const label = progress < 0.5 ? "Morphing..." : "Complete";
    this.grid.writeCentered(22, label, "rgb(150,150,150)");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {}

  dispose(): void {
    this.morphCells = [];
  }
}
