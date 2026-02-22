import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const CHARS = " .:-=+*#%@";

export default class MeltingScreen implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private drops: number[] = [];
  private speeds: number[] = [];
  private hueShift = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.drops = new Array(80).fill(0);
    this.speeds = Array.from({ length: 80 }, () => 0.3 + Math.random() * 1.2);
    this.hueShift = 0;
    // Fill initial content
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const ch = CHARS[Math.floor(Math.random() * CHARS.length)];
        this.grid.setCell(x, y, ch, "#ffffff");
      }
    }
  }

  update(elapsed: number, dt: number): void {
    this.hueShift = (elapsed * 0.05) % 360;
    const dtSec = dt / 1000;

    for (let x = 0; x < 80; x++) {
      this.drops[x] += this.speeds[x] * dtSec * 8;
      const dropRow = Math.floor(this.drops[x]);

      for (let y = 23; y >= 0; y--) {
        const distFromDrop = y - dropRow;
        if (distFromDrop > 0 && distFromDrop < 6) {
          // Stretching/dripping zone
          const stretchFactor = distFromDrop / 6;
          const srcY = Math.max(0, y - Math.floor(distFromDrop * 0.5));
          const charIdx = Math.floor(stretchFactor * (CHARS.length - 1));
          const hue = (this.hueShift + x * 4 + y * 8) % 360;
          const sat = 70 + stretchFactor * 30;
          this.grid.setCell(x, y, CHARS[charIdx], `hsl(${hue},${sat}%,60%)`);
        } else if (y <= dropRow) {
          // Melted zone - distorted
          const wave = Math.sin(elapsed * 0.002 + x * 0.3 + y * 0.5);
          const charIdx = Math.floor((wave * 0.5 + 0.5) * (CHARS.length - 1));
          const hue = (this.hueShift + y * 15 + x * 3) % 360;
          this.grid.setCell(x, y, CHARS[charIdx], `hsl(${hue},80%,50%)`);
        } else {
          // Intact zone above
          const hue = (this.hueShift + x * 2) % 360;
          const brightness = 40 + Math.sin(elapsed * 0.001 + x * 0.1) * 20;
          const ch = CHARS[Math.floor(Math.random() * 3) + 5];
          this.grid.setCell(x, y, ch, `hsl(${hue},30%,${brightness}%)`);
        }
      }

      // Reset column when fully melted
      if (this.drops[x] > 30) {
        this.drops[x] = -5;
        this.speeds[x] = 0.3 + Math.random() * 1.2;
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.drops.fill(0);
    this.speeds = Array.from({ length: 80 }, () => 0.3 + Math.random() * 1.2);
    this.hueShift = 0;
  }

  dispose(): void {
    // No external resources
  }
}
