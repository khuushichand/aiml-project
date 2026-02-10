import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const RING_CHARS = [".", ":", "+", "*", "#", "@", "%", "&"];

export default class QuantumTunnel implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const cx = 40;
    const cy = 12;
    const t = this.elapsed / 1000;
    const numRings = 12;

    for (let r = numRings - 1; r >= 0; r--) {
      const baseRadius = (r + 1) * 2.5;
      const pulse = Math.sin(t * 2 + r * 0.5) * 0.5;
      const radius = baseRadius + pulse;
      const expand = ((t * 3 + r * 2) % (numRings * 2.5));

      const effectiveRadius = (radius + expand) % (numRings * 3);
      const charIdx = r % RING_CHARS.length;
      const ch = RING_CHARS[charIdx];

      const hue = (r * 30 + t * 50) % 360;
      const brightness = Math.max(20, 70 - effectiveRadius * 2);

      // Draw ring as an ellipse (wider than tall due to character aspect ratio)
      const steps = Math.max(20, Math.floor(effectiveRadius * 8));
      for (let s = 0; s < steps; s++) {
        const angle = (s / steps) * Math.PI * 2;
        const px = Math.round(cx + Math.cos(angle) * effectiveRadius * 2);
        const py = Math.round(cy + Math.sin(angle) * effectiveRadius);

        if (px >= 0 && px < 80 && py >= 0 && py < 24) {
          grid.setCell(px, py, ch, `hsl(${hue},80%,${brightness}%)`);
        }
      }
    }

    // Center text
    grid.writeCentered(cy, " TLDW ", "#ffffff");
    grid.writeCentered(cy + 1, "Quantum Tunnel", "#aaddff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
