import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";
import { getAsciiArt } from "../../../../../data/splash-ascii-art";

export default class OldFilmEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private contentLines: string[] = [];
  private shakeY = 0;
  private shakeIntensity = 1;
  private grainDensity = 0.07;

  private getArtLines(name: unknown): string[] | null {
    if (typeof name !== "string" || !name.trim()) return null;
    return getAsciiArt(name).replace(/\r/g, "").split("\n");
  }

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.shakeIntensity = Math.max(0, Number(config?.shake_intensity ?? 1));
    this.grainDensity = Math.max(0, Number(config?.grain_density ?? 0.07));
    const frameArtNames = Array.isArray(config?.frames_art_names) ? (config?.frames_art_names as string[]) : [];
    const frameArtLines = this.getArtLines(frameArtNames[0]);
    this.contentLines = (config?.lines as string[]) ?? frameArtLines ?? [
      "~ tldw ~",
      "",
      "A Research Picture",
      "",
      "Directed by: Open Source",
      "",
      "MCMXXV",
    ];
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    // Random vertical shake
    const shakeChance = Math.min(1, 0.3 * Math.max(this.shakeIntensity, 0));
    const shakeRange = Math.max(0, Math.round(this.shakeIntensity));
    if (Math.random() < shakeChance && shakeRange > 0) {
      this.shakeY = Math.floor(Math.random() * (shakeRange * 2 + 1)) - shakeRange;
    } else {
      this.shakeY = 0;
    }

    const startY = Math.floor((24 - this.contentLines.length) / 2);
    for (let li = 0; li < this.contentLines.length; li++) {
      const line = this.contentLines[li];
      if (line.length === 0) continue;
      const row = startY + li + this.shakeY;
      if (row < 0 || row >= 24) continue;

      const cx = Math.floor((80 - line.length) / 2);
      for (let i = 0; i < line.length; i++) {
        // Sepia tone: warm yellow-brown range
        const base = 140 + Math.floor(Math.random() * 40);
        const r = Math.min(base + 40, 255);
        const g = Math.min(base + 10, 220);
        const b = Math.floor(base * 0.5);
        this.grid.setCell(cx + i, row, line[i], `rgb(${r},${g},${b})`);
      }
    }

    // Film grain: random dots
    const grainCount = Math.max(1, Math.round(80 * 24 * this.grainDensity * 0.2));
    for (let n = 0; n < grainCount; n++) {
      const gx = Math.floor(Math.random() * 80);
      const gy = Math.floor(Math.random() * 24);
      const v = 40 + Math.floor(Math.random() * 60);
      this.grid.setCell(gx, gy, ".", `rgb(${v},${v},${Math.floor(v * 0.6)})`);
    }

    // Occasional vertical scratch line
    if (Math.random() < Math.min(0.6, 0.15 + this.grainDensity)) {
      const scratchX = Math.floor(Math.random() * 80);
      for (let sy = 0; sy < 24; sy++) {
        if (Math.random() < 0.7) {
          this.grid.setCell(scratchX, sy, "|", "rgba(200,180,120,0.4)");
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    // Sepia background
    ctx.fillStyle = "#1a1408";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);

    // Vignette
    const grd = ctx.createRadialGradient(
      this.width / 2, this.height / 2, Math.min(this.width, this.height) * 0.3,
      this.width / 2, this.height / 2, Math.max(this.width, this.height) * 0.65
    );
    grd.addColorStop(0, "rgba(0,0,0,0)");
    grd.addColorStop(1, "rgba(0,0,0,0.55)");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, this.width, this.height);
  }

  reset(): void {
    this.shakeY = 0;
  }

  dispose(): void {
    this.contentLines = [];
  }
}
