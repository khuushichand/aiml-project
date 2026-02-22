import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const FACE_COLORS = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff8800", "#ffffff"];
const BLOCK = "\u2588\u2588";

export default class RubiksCube implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private face: number[][] = [];
  private nextRotate = 0;
  private moveCount = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private initFace(): void {
    this.face = [];
    for (let r = 0; r < 3; r++) {
      this.face[r] = [];
      for (let c = 0; c < 3; c++) {
        this.face[r][c] = Math.floor(Math.random() * FACE_COLORS.length);
      }
    }
  }

  private rotateFaceCW(): void {
    const f = this.face;
    const tmp = f[0][0];
    f[0][0] = f[2][0]; f[2][0] = f[2][2]; f[2][2] = f[0][2]; f[0][2] = tmp;
    const tmp2 = f[0][1];
    f[0][1] = f[1][0]; f[1][0] = f[2][1]; f[2][1] = f[1][2]; f[1][2] = tmp2;
  }

  private shiftRow(row: number): void {
    const f = this.face[row];
    const last = f[2];
    f[2] = f[1]; f[1] = f[0]; f[0] = last;
  }

  private shiftCol(col: number): void {
    const last = this.face[2][col];
    this.face[2][col] = this.face[1][col];
    this.face[1][col] = this.face[0][col];
    this.face[0][col] = last;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    if (elapsed > this.nextRotate) {
      const move = this.moveCount % 5;
      if (move === 0) this.rotateFaceCW();
      else if (move === 1) this.shiftRow(0);
      else if (move === 2) this.shiftCol(1);
      else if (move === 3) this.shiftRow(2);
      else this.rotateFaceCW();

      this.moveCount++;
      this.nextRotate = elapsed + 800;

      // Occasionally "solve" a row
      if (this.moveCount % 12 === 0) {
        const color = Math.floor(Math.random() * FACE_COLORS.length);
        const row = Math.floor(Math.random() * 3);
        for (let c = 0; c < 3; c++) this.face[row][c] = color;
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    grid.writeCentered(2, "Rubik's Cube Solver", "#ffffff");
    grid.writeCentered(3, `Move #${this.moveCount}`, "#aaaaaa");

    // Draw the cube face centered
    const startX = 34;
    const startY = 7;
    const cellSize = 3;

    // Border
    const bw = cellSize * 3 * 2 + 4;
    const bh = cellSize * 3 + 2;
    for (let x = startX - 2; x < startX + bw - 2; x++) {
      grid.setCell(x, startY - 1, "-", "#888888");
      grid.setCell(x, startY + bh - 2, "-", "#888888");
    }

    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        const color = FACE_COLORS[this.face[r][c]];
        const bx = startX + c * (cellSize * 2 + 1);
        const by = startY + r * (cellSize + 0);

        for (let dy = 0; dy < cellSize - 1; dy++) {
          for (let dx = 0; dx < cellSize * 2 - 1; dx++) {
            const px = bx + dx;
            const py = by + dy;
            if (px >= 0 && px < 80 && py >= 0 && py < 24) {
              grid.setCell(px, py, "#", color);
            }
          }
        }
      }
    }

    // Status
    const solved = this.face.every(row => row.every(c => c === this.face[0][0]));
    const status = solved ? "SOLVED!" : "Solving...";
    const statusColor = solved ? "#00ff00" : "#ffcc00";
    grid.writeCentered(19, status, statusColor);

    grid.writeCentered(22, "tldw", "#00ccff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.moveCount = 0;
    this.nextRotate = 0;
    this.initFace();
    this.grid.clear();
  }

  dispose(): void {
    this.face = [];
    this.grid.clear();
  }
}
