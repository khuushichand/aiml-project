import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const DEPTH_CHARS = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

export default class TrippyTunnel implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private zOffset = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.zOffset = 0;
  }

  update(elapsed: number, dt: number): void {
    this.zOffset = elapsed * 0.002;
    const cx = 40;
    const cy = 12;

    this.grid.clear("#000");

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const dx = (x - cx) / 40;
        const dy = (y - cy) / 12;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 0.01) {
          this.grid.setCell(x, y, "@", "#ffffff");
          continue;
        }

        // Tunnel depth from distance to center (inverse)
        const depth = 1 / dist;
        const angle = Math.atan2(dy, dx);

        // Texture coordinates in tunnel space
        const u = angle / Math.PI;
        const v = depth + this.zOffset;

        // Ring pattern
        const ringPhase = Math.sin(v * 6) * 0.5 + 0.5;
        // Segment pattern
        const segPhase = Math.sin(u * 8 + v * 2) * 0.5 + 0.5;

        const combined = ringPhase * 0.7 + segPhase * 0.3;
        const charPool = DEPTH_CHARS;
        const charIdx = Math.floor(combined * (charPool.length - 1));
        const ch = charPool[Math.min(charIdx, charPool.length - 1)];

        // Rainbow rings
        const hue = (v * 60 + angle * 30 / Math.PI) % 360;
        const absHue = hue < 0 ? hue + 360 : hue;
        const light = 30 + combined * 40;
        const sat = 80 + ringPhase * 20;
        const fadeFactor = Math.min(1, dist * 2);

        this.grid.setCell(
          x, y, ch,
          `hsl(${absHue},${sat}%,${light * fadeFactor}%)`
        );
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.zOffset = 0;
  }

  dispose(): void {}
}
