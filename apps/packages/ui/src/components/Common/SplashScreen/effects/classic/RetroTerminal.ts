import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

export default class RetroTerminalEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private contentLines: string[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.contentLines = (config?.lines as string[]) ?? [
      "> SYSTEM BOOT v2.4.1",
      "> Initializing display...",
      "> Loading tldw kernel............ OK",
      "> Memory check: 640K",
      "> ",
      "> tldw - Research Assistant",
      "> Ready.",
    ];
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();
    const startY = Math.floor((24 - this.contentLines.length) / 2);
    // Slight flicker
    const flickerDim = Math.random() < 0.03 ? 0.6 : 1.0;

    for (let li = 0; li < this.contentLines.length; li++) {
      const row = startY + li;
      if (row < 0 || row >= 24) continue;
      const line = this.contentLines[li];
      const cx = 2;
      for (let i = 0; i < line.length && cx + i < 80; i++) {
        // Phosphor glow: brighter chars get slight boost
        const base = line[i] === " " ? 0 : 180;
        const g = Math.floor(base * flickerDim + Math.random() * 30);
        this.grid.setCell(cx + i, row, line[i], `rgb(0,${Math.min(g, 255)},0)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000a00";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);

    // Scanlines overlay
    ctx.fillStyle = "rgba(0,0,0,0.15)";
    for (let y = 0; y < this.height; y += 3) {
      ctx.fillRect(0, y, this.width, 1);
    }

    // Edge vignette for CRT curvature
    const grd = ctx.createRadialGradient(
      this.width / 2, this.height / 2, Math.min(this.width, this.height) * 0.35,
      this.width / 2, this.height / 2, Math.max(this.width, this.height) * 0.7
    );
    grd.addColorStop(0, "rgba(0,0,0,0)");
    grd.addColorStop(1, "rgba(0,0,0,0.6)");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, this.width, this.height);

    // Subtle green tint overlay for phosphor glow
    ctx.fillStyle = "rgba(0,40,0,0.05)";
    ctx.fillRect(0, 0, this.width, this.height);
  }

  reset(): void {}

  dispose(): void {
    this.contentLines = [];
  }
}
