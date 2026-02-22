import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class GameOfLifeEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private cols = 78;
  private rows = 20;
  private cells: boolean[][] = [];
  private generation = 0;
  private evolveTimer = 0;
  private evolveInterval = 150;
  private population = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.generation = 0;
    this.evolveTimer = 0;
    this.initCells();
  }

  private initCells(): void {
    this.cells = Array.from({ length: this.rows }, () =>
      Array.from({ length: this.cols }, () => Math.random() < 0.3)
    );
    // Plant some gliders
    const glider = [[0, 1], [1, 2], [2, 0], [2, 1], [2, 2]];
    for (let g = 0; g < 4; g++) {
      const ox = 5 + g * 18;
      const oy = 2 + g * 4;
      for (const [dy, dx] of glider) {
        const cy = (oy + dy) % this.rows;
        const cx = (ox + dx) % this.cols;
        this.cells[cy][cx] = true;
      }
    }
    this.countPop();
  }

  private countPop(): void {
    this.population = 0;
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        if (this.cells[r][c]) this.population++;
      }
    }
  }

  private neighbors(r: number, c: number): number {
    let count = 0;
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        if (dr === 0 && dc === 0) continue;
        const nr = (r + dr + this.rows) % this.rows;
        const nc = (c + dc + this.cols) % this.cols;
        if (this.cells[nr][nc]) count++;
      }
    }
    return count;
  }

  private evolve(): void {
    const next: boolean[][] = Array.from({ length: this.rows }, () =>
      Array(this.cols).fill(false)
    );
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const n = this.neighbors(r, c);
        if (this.cells[r][c]) {
          next[r][c] = n === 2 || n === 3;
        } else {
          next[r][c] = n === 3;
        }
      }
    }
    this.cells = next;
    this.generation++;
    this.countPop();

    // Reset if stagnant
    if (this.population < 5 || this.generation > 500) {
      this.generation = 0;
      this.initCells();
    }
  }

  update(_elapsed: number, dt: number): void {
    this.evolveTimer += dt;
    if (this.evolveTimer >= this.evolveInterval) {
      this.evolveTimer = 0;
      this.evolve();
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    this.grid.writeCentered(0, "CONWAY'S GAME OF LIFE", "#0af");

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        if (this.cells[r][c]) {
          const n = this.neighbors(r, c);
          let color = "#08f";
          if (n === 2) color = "#0af";
          else if (n === 3) color = "#0df";
          else if (n >= 4) color = "#06a";
          this.grid.setCell(c + 1, r + 2, "■", color);
        }
      }
    }

    this.grid.writeString(2, 23, `Gen: ${this.generation}`, "#888");
    this.grid.writeString(20, 23, `Pop: ${this.population}`, "#888");
    this.grid.writeString(55, 23, "Toroidal Grid", "#555");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.generation = 0;
    this.evolveTimer = 0;
    this.initCells();
  }

  dispose(): void {
    this.cells = [];
  }
}
