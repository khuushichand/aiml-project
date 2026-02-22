import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

export default class HolographicInterface implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private scanLineY = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
    this.scanLineY = Math.floor(elapsed / 100) % 24;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const t = this.elapsed / 1000;
    const cx = 40;
    const cy = 12;

    // Rotating wireframe cube (projected to 2D)
    const size = 6;
    const cubeVerts = [
      [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
      [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ];
    const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];

    const cosA = Math.cos(t); const sinA = Math.sin(t);
    const cosB = Math.cos(t * 0.7); const sinB = Math.sin(t * 0.7);

    const projected = cubeVerts.map(([x, y, z]) => {
      const x1 = x * cosA - z * sinA;
      const z1 = x * sinA + z * cosA;
      const y1 = y * cosB - z1 * sinB;
      const px = Math.round(cx + x1 * size * 2);
      const py = Math.round(cy + y1 * size);
      return { px, py };
    });

    for (const [a, b] of edges) {
      const pa = projected[a]; const pb = projected[b];
      const steps = Math.max(Math.abs(pb.px - pa.px), Math.abs(pb.py - pa.py));
      if (steps === 0) continue;
      for (let s = 0; s <= steps; s++) {
        const px = Math.round(pa.px + (pb.px - pa.px) * s / steps);
        const py = Math.round(pa.py + (pb.py - pa.py) * s / steps);
        if (px >= 0 && px < 80 && py >= 0 && py < 24) {
          grid.setCell(px, py, "*", "#00ccff");
        }
      }
    }

    // Data readouts on left panel
    const readouts = [
      "SYSTEM: ONLINE",
      `TEMP: ${(42 + Math.sin(t) * 3).toFixed(1)}C`,
      `FREQ: ${(3.2 + Math.cos(t * 0.5) * 0.1).toFixed(2)}GHz`,
      `MEM: ${(78 + Math.sin(t * 1.3) * 5).toFixed(0)}%`,
      `NET: ${(124 + Math.sin(t * 2) * 30).toFixed(0)}Mbps`,
    ];
    for (let i = 0; i < readouts.length; i++) {
      grid.writeString(2, 2 + i, readouts[i], "#006699");
    }

    // Right panel - bar graphs
    for (let i = 0; i < 5; i++) {
      const val = Math.floor((Math.sin(t + i) * 0.5 + 0.5) * 12);
      const bar = "\u2588".repeat(val) + "\u2591".repeat(12 - val);
      grid.writeString(60, 2 + i, bar, "#0088cc");
    }

    // Scan line
    for (let x = 0; x < 80; x++) {
      grid.setCell(x, this.scanLineY, "\u2592", "#00ffff33");
    }

    // Border frame
    for (let x = 0; x < 80; x++) {
      grid.setCell(x, 0, "\u2550", "#004466");
      grid.setCell(x, 23, "\u2550", "#004466");
    }
    for (let y = 0; y < 24; y++) {
      grid.setCell(0, y, "\u2551", "#004466");
      grid.setCell(79, y, "\u2551", "#004466");
    }

    // Title
    grid.writeCentered(21, "HOLOGRAPHIC INTERFACE v3.1", "#00ccff");
    grid.writeCentered(22, "tldw", "#ffffff");

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
