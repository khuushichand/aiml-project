import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const MANDALA_CHARS = " .:;*+oO#@%&";

export default class PsychedelicMandala implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private foldCount = 8;
  private growRadius = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.growRadius = 0;
  }

  update(elapsed: number, dt: number): void {
    const t = elapsed / 1000;
    // Mandala grows outward then resets
    this.growRadius = (t * 0.3) % 1.2;

    const cx = 40;
    const cy = 12;
    const folds = this.foldCount;
    const foldAngle = (2 * Math.PI) / folds;

    this.grid.clear("#000");

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const dx = (x - cx) / 40;
        const dy = (y - cy) / 12;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > this.growRadius) {
          continue;
        }

        let angle = Math.atan2(dy, dx);
        if (angle < 0) angle += 2 * Math.PI;

        // Fold into one sector for symmetry
        let foldedAngle = angle % foldAngle;
        // Mirror within sector
        if (foldedAngle > foldAngle / 2) {
          foldedAngle = foldAngle - foldedAngle;
        }

        // Pattern generation in folded space
        const pX = dist * Math.cos(foldedAngle);
        const pY = dist * Math.sin(foldedAngle);

        const pattern1 = Math.sin(pX * 20 + t * 1.5) * Math.cos(pY * 25 + t);
        const pattern2 = Math.sin(dist * 15 - t * 2);
        const pattern3 = Math.cos(foldedAngle * 6 + dist * 10 + t);

        const combined = (pattern1 + pattern2 + pattern3) / 3;
        const norm = (combined + 1) / 2;
        const charIdx = Math.floor(norm * (MANDALA_CHARS.length - 1));

        // Rich rainbow cycling
        const hue = (dist * 300 + t * 40 + angle * 180 / Math.PI) % 360;
        const sat = 80 + norm * 20;
        const light = 30 + norm * 45;

        this.grid.setCell(x, y, MANDALA_CHARS[charIdx], `hsl(${hue},${sat}%,${light}%)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.growRadius = 0;
  }

  dispose(): void {}
}
