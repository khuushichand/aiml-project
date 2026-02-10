import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface BigBlock {
  cells: { dx: number; dy: number }[];
  color: string;
  x: number;
  y: number;
  rotation: number;
}

export default class TetrisBlockEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private block!: BigBlock;
  private dropTimer = 0;
  private rotateTimer = 0;
  private landed: { x: number; y: number; color: string }[] = [];
  private blockScale = 3;

  private templates = [
    { cells: [{ dx: 0, dy: 0 }, { dx: 1, dy: 0 }, { dx: 2, dy: 0 }, { dx: 3, dy: 0 }], color: "#0ff" },
    { cells: [{ dx: 0, dy: 0 }, { dx: 1, dy: 0 }, { dx: 0, dy: 1 }, { dx: 1, dy: 1 }], color: "#ff0" },
    { cells: [{ dx: 0, dy: 0 }, { dx: 1, dy: 0 }, { dx: 2, dy: 0 }, { dx: 1, dy: 1 }], color: "#a0f" },
    { cells: [{ dx: 0, dy: 0 }, { dx: 0, dy: 1 }, { dx: 1, dy: 1 }, { dx: 1, dy: 2 }], color: "#0f0" },
    { cells: [{ dx: 1, dy: 0 }, { dx: 1, dy: 1 }, { dx: 0, dy: 1 }, { dx: 0, dy: 2 }], color: "#f00" },
    { cells: [{ dx: 0, dy: 0 }, { dx: 0, dy: 1 }, { dx: 0, dy: 2 }, { dx: 1, dy: 2 }], color: "#fa0" },
    { cells: [{ dx: 1, dy: 0 }, { dx: 1, dy: 1 }, { dx: 1, dy: 2 }, { dx: 0, dy: 2 }], color: "#00f" },
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.landed = [];
    this.spawnBlock();
  }

  private spawnBlock(): void {
    const t = this.templates[Math.floor(Math.random() * this.templates.length)];
    this.block = {
      cells: t.cells.map(c => ({ ...c })),
      color: t.color,
      x: 30 + Math.floor(Math.random() * 15),
      y: -4,
      rotation: 0,
    };
  }

  private rotateCells(): void {
    // Rotate 90 degrees around centroid
    let cx = 0, cy = 0;
    for (const c of this.block.cells) { cx += c.dx; cy += c.dy; }
    cx /= this.block.cells.length;
    cy /= this.block.cells.length;
    for (const c of this.block.cells) {
      const dx = c.dx - cx;
      const dy = c.dy - cy;
      c.dx = Math.round(cx - dy);
      c.dy = Math.round(cy + dx);
    }
    this.block.rotation = (this.block.rotation + 1) % 4;
  }

  private getScreenCells(): { sx: number; sy: number }[] {
    const result: { sx: number; sy: number }[] = [];
    for (const c of this.block.cells) {
      for (let sy = 0; sy < this.blockScale; sy++) {
        for (let sx = 0; sx < this.blockScale; sx++) {
          result.push({
            sx: this.block.x + c.dx * this.blockScale + sx,
            sy: Math.round(this.block.y) + c.dy * this.blockScale + sy,
          });
        }
      }
    }
    return result;
  }

  private hasLanded(): boolean {
    for (const sc of this.getScreenCells()) {
      if (sc.sy >= 23) return true;
      if (this.landed.some(l => l.x === sc.sx && l.y === sc.sy + 1)) return true;
    }
    return false;
  }

  update(_elapsed: number, dt: number): void {
    this.dropTimer += dt;
    this.rotateTimer += dt;

    if (this.rotateTimer > 600) {
      this.rotateTimer = 0;
      this.rotateCells();
    }

    if (this.dropTimer > 100) {
      this.dropTimer = 0;
      if (!this.hasLanded()) {
        this.block.y += 1;
      } else {
        // Lock
        for (const sc of this.getScreenCells()) {
          if (sc.sx >= 0 && sc.sx < 80 && sc.sy >= 0 && sc.sy < 24) {
            this.landed.push({ x: sc.sx, y: sc.sy, color: this.block.color });
          }
        }
        // Clear full rows
        for (let r = 23; r >= 0; r--) {
          const rowCells = this.landed.filter(l => l.y === r);
          if (rowCells.length >= 70) {
            this.landed = this.landed.filter(l => l.y !== r);
            for (const l of this.landed) {
              if (l.y < r) l.y++;
            }
            r++;
          }
        }
        // Trim if too many
        if (this.landed.length > 800) {
          this.landed = this.landed.slice(-400);
        }
        this.spawnBlock();
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    this.grid.writeCentered(0, "TETRIS BLOCKS", "#0ff");

    // Landed blocks
    for (const l of this.landed) {
      if (l.x >= 0 && l.x < 80 && l.y >= 0 && l.y < 24) {
        this.grid.setCell(l.x, l.y, "█", l.color);
      }
    }

    // Current block
    for (const sc of this.getScreenCells()) {
      if (sc.sx >= 0 && sc.sx < 80 && sc.sy >= 0 && sc.sy < 24) {
        this.grid.setCell(sc.sx, sc.sy, "█", this.block.color);
      }
    }

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.landed = [];
    this.spawnBlock();
  }

  dispose(): void {
    this.landed = [];
  }
}
