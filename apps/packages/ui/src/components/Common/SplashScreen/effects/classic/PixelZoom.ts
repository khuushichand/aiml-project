import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";
import { getAsciiArt } from "../../../../../data/splash-ascii-art";

export default class PixelZoomEffect implements SplashEffect {
  private grid!: CharGrid;
  private sourceGrid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private duration = 2000;
  private maxPixelSize = 8;
  private contentLines: string[] = [];

  private getArtLines(name: unknown): string[] | null {
    if (typeof name !== "string" || !name.trim()) return null;
    return getAsciiArt(name).replace(/\r/g, "").split("\n");
  }

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.sourceGrid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.duration = (config?.duration as number) ?? 2000;
    this.maxPixelSize = Math.max(1, Math.floor(Number(config?.max_pixel_size ?? 8)));
    const targetArtLines = this.getArtLines(config?.target_art_name);
    this.contentLines = (config?.lines as string[]) ?? targetArtLines ?? [
      "tldw",
      "",
      "Too Long; Didn't Watch",
      "",
      "Enhancing...",
    ];

    // Pre-populate source grid
    const startY = Math.floor((24 - this.contentLines.length) / 2);
    for (let li = 0; li < this.contentLines.length; li++) {
      const line = this.contentLines[li];
      if (line.length === 0) continue;
      this.sourceGrid.writeCentered(startY + li, line, "rgb(0,220,0)");
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const progress = Math.min(elapsed / this.duration, 1);
    // Block size goes from configured max down to 1
    const blockSize = Math.max(1, Math.ceil(this.maxPixelSize * (1 - progress)));
    const startY = Math.floor((24 - this.contentLines.length) / 2);

    if (blockSize <= 1) {
      // Final resolved state
      for (let li = 0; li < this.contentLines.length; li++) {
        const line = this.contentLines[li];
        if (line.length === 0) continue;
        this.grid.writeCentered(startY + li, line, "rgb(0,255,0)");
      }
      return;
    }

    // Render pixelated version: sample center of each block
    for (let by = 0; by < 24; by += blockSize) {
      for (let bx = 0; bx < 80; bx += blockSize) {
        // Sample from center of block in source content
        const sy = Math.min(by + Math.floor(blockSize / 2), 23);
        const sx = Math.min(bx + Math.floor(blockSize / 2), 79);

        // Check if source has content at this position
        let ch = " ";
        let color = "rgb(0,80,0)";
        for (let li = 0; li < this.contentLines.length; li++) {
          const line = this.contentLines[li];
          const row = startY + li;
          if (row === sy) {
            const cx = Math.floor((80 - line.length) / 2);
            const ci = sx - cx;
            if (ci >= 0 && ci < line.length && line[ci] !== " ") {
              ch = line[ci];
              const g = 100 + Math.floor(progress * 155);
              color = `rgb(0,${g},0)`;
            }
            break;
          }
        }

        // Fill the block with the sampled char
        for (let dy = 0; dy < blockSize && by + dy < 24; dy++) {
          for (let dx = 0; dx < blockSize && bx + dx < 80; dx++) {
            if (ch !== " ") {
              this.grid.setCell(bx + dx, by + dy, ch, color);
            }
          }
        }
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
