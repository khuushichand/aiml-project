import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

interface Component {
  x: number;
  y: number;
  art: string[];
  color: string;
}

const CHIPS = [
  ["+------+", "|IC-001|", "+------+"],
  ["+----+", "|FPGA|", "+----+"],
  ["+--+", "|uC|", "+--+"],
];

const RESISTORS = ["[-/\\/\\/-]", "[-====-]"];

export default class CircuitBoard implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private components: Component[] = [];
  private traceMap: boolean[][] = [];
  private activeTrace = 0;
  private traceSegments: { x1: number; y1: number; x2: number; y2: number }[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private buildBoard(): void {
    this.components = [];
    this.traceSegments = [];
    this.traceMap = Array.from({ length: 24 }, () => Array(80).fill(false));

    // Place chips
    const chipPositions = [[5, 3], [30, 2], [55, 4], [15, 14], [45, 15], [70, 10]];
    for (let i = 0; i < chipPositions.length; i++) {
      const [x, y] = chipPositions[i];
      const chip = CHIPS[i % CHIPS.length];
      this.components.push({ x, y, art: chip, color: "#44aa44" });
    }

    // Place resistors
    const resPositions = [[10, 8], [35, 10], [60, 7], [20, 20], [50, 19]];
    for (const [x, y] of resPositions) {
      const r = RESISTORS[Math.floor(Math.random() * RESISTORS.length)];
      this.components.push({ x, y, art: [r], color: "#aa8844" });
    }

    // Build traces connecting components
    for (let i = 0; i < this.components.length - 1; i++) {
      const a = this.components[i];
      const b = this.components[i + 1];
      const ax = a.x + Math.floor((a.art[0]?.length ?? 0) / 2);
      const ay = a.y + a.art.length;
      const bx = b.x + Math.floor((b.art[0]?.length ?? 0) / 2);
      const by = b.y;
      this.traceSegments.push({ x1: ax, y1: ay, x2: bx, y2: by });
    }
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
    this.activeTrace = Math.floor(elapsed / 400) % (this.traceSegments.length + 5);
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Background dots for PCB
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        if (x % 4 === 0 && y % 3 === 0) {
          grid.setCell(x, y, ".", "#1a3a1a");
        }
      }
    }

    // Draw traces
    for (let i = 0; i < this.traceSegments.length; i++) {
      const seg = this.traceSegments[i];
      const isActive = i <= this.activeTrace;
      const color = isActive ? "#00ff66" : "#336633";

      // Horizontal then vertical
      const midY = seg.y1;
      for (let x = Math.min(seg.x1, seg.x2); x <= Math.max(seg.x1, seg.x2); x++) {
        if (x >= 0 && x < 80 && midY >= 0 && midY < 24) {
          grid.setCell(x, midY, "\u2500", color);
        }
      }
      for (let y = Math.min(midY, seg.y2); y <= Math.max(midY, seg.y2); y++) {
        if (seg.x2 >= 0 && seg.x2 < 80 && y >= 0 && y < 24) {
          grid.setCell(seg.x2, y, "\u2502", color);
        }
      }
    }

    // Draw components
    for (const comp of this.components) {
      for (let i = 0; i < comp.art.length; i++) {
        grid.writeString(comp.x, comp.y + i, comp.art[i], comp.color);
      }
    }

    // Title
    grid.writeCentered(23, "tldw Circuit Board", "#00ccff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.activeTrace = 0;
    this.buildBoard();
    this.grid.clear();
  }

  dispose(): void {
    this.components = [];
    this.traceSegments = [];
    this.grid.clear();
  }
}
