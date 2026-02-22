import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class SpotlightEffect implements SplashEffect {
  private grid!: CharGrid;
  private contentGrid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private radius = 6;
  private freqX = 0.0015;
  private freqY = 0.002;
  private pathType: "lissajous" | "circle" | "horizontal" | "vertical" = "lissajous";
  private contentLines: string[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.contentGrid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.radius = (config?.spotlight_radius as number) ?? (config?.radius as number) ?? 6;
    this.freqX = (config?.freq_x as number) ?? 0.0015;
    this.freqY = (config?.freq_y as number) ?? 0.002;
    const pathType = config?.path_type;
    if (pathType === "lissajous" || pathType === "circle" || pathType === "horizontal" || pathType === "vertical") {
      this.pathType = pathType;
    } else {
      this.pathType = "lissajous";
    }
    this.contentLines = (config?.lines as string[]) ?? [
      "==========================================",
      "||                                      ||",
      "||    tldw - Too Long; Didn't Watch     ||",
      "||                                      ||",
      "||    Research Assistant Platform        ||",
      "||    Media Analysis & Ingestion        ||",
      "||    RAG & Knowledge Management        ||",
      "||    16+ LLM Providers                 ||",
      "||                                      ||",
      "==========================================",
    ];

    // Pre-render content into contentGrid
    const startY = Math.floor((24 - this.contentLines.length) / 2);
    for (let li = 0; li < this.contentLines.length; li++) {
      const line = this.contentLines[li];
      this.contentGrid.writeCentered(startY + li, line, "rgb(0,220,0)");
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();

    let spotX = 40 + 30 * Math.sin(elapsed * this.freqX);
    let spotY = 12 + 8 * Math.sin(elapsed * this.freqY);
    if (this.pathType === "circle") {
      spotX = 40 + 28 * Math.cos(elapsed * this.freqX);
      spotY = 12 + 8 * Math.sin(elapsed * this.freqX);
    } else if (this.pathType === "horizontal") {
      spotX = 40 + 30 * Math.sin(elapsed * this.freqX);
      spotY = 12;
    } else if (this.pathType === "vertical") {
      spotX = 40;
      spotY = 12 + 9 * Math.sin(elapsed * this.freqY);
    }
    const r2 = this.radius * this.radius;

    const startY = Math.floor((24 - this.contentLines.length) / 2);

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        // Calculate distance from spotlight center (account for char aspect ratio)
        const dx = (x - spotX) * 0.5; // chars are ~2x taller than wide
        const dy = y - spotY;
        const dist2 = dx * dx + dy * dy;

        // Check if there's content at this position
        let ch = " ";
        let hasContent = false;
        const li = y - startY;
        if (li >= 0 && li < this.contentLines.length) {
          const line = this.contentLines[li];
          const cx = Math.floor((80 - line.length) / 2);
          const ci = x - cx;
          if (ci >= 0 && ci < line.length && line[ci] !== " ") {
            ch = line[ci];
            hasContent = true;
          }
        }

        if (!hasContent) continue;

        if (dist2 < r2) {
          // Inside spotlight: full brightness
          const falloff = 1 - dist2 / r2;
          const g = Math.floor(100 + 155 * falloff);
          this.grid.setCell(x, y, ch, `rgb(0,${g},0)`);
        } else if (dist2 < r2 * 2.5) {
          // Penumbra: dim
          this.grid.setCell(x, y, ch, "rgb(0,30,0)");
        }
        // Outside: hidden (dark)
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
