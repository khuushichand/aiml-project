import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const CELL_CHARS = " .+*#@";

export default class ElectricSheep implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private cells: number[][] = [];
  private ages: number[][] = [];
  private stepTimer = 0;
  private generation = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.generation = 0;
    this.stepTimer = 0;
    this.seedCells();
  }

  private seedCells(): void {
    this.cells = Array.from({ length: 24 }, () =>
      Array.from({ length: 80 }, () => Math.random() > 0.6 ? 1 : 0)
    );
    this.ages = Array.from({ length: 24 }, () => new Array(80).fill(0));
  }

  private countNeighbors(x: number, y: number): number {
    let count = 0;
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        if (dx === 0 && dy === 0) continue;
        const ny = (y + dy + 24) % 24;
        const nx = (x + dx + 80) % 80;
        count += this.cells[ny][nx];
      }
    }
    return count;
  }

  private step(): void {
    const next: number[][] = Array.from({ length: 24 }, () => new Array(80).fill(0));
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const n = this.countNeighbors(x, y);
        const alive = this.cells[y][x];
        // Modified rules for more interesting patterns
        if (alive) {
          next[y][x] = (n === 2 || n === 3 || n === 6) ? 1 : 0;
        } else {
          next[y][x] = (n === 3 || n === 5) ? 1 : 0;
        }
        if (next[y][x] && alive) {
          this.ages[y][x] = Math.min(this.ages[y][x] + 1, 20);
        } else if (!next[y][x]) {
          this.ages[y][x] = Math.max(this.ages[y][x] - 1, 0);
        }
      }
    }
    this.cells = next;
    this.generation++;

    // Re-seed if too empty
    let total = 0;
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) total += this.cells[y][x];
    }
    if (total < 40) this.seedCells();
  }

  update(elapsed: number, dt: number): void {
    this.stepTimer += dt;
    if (this.stepTimer > 120) {
      this.step();
      this.stepTimer = 0;
    }

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const alive = this.cells[y][x];
        const age = this.ages[y][x];
        const charIdx = alive ? Math.min(age + 1, CELL_CHARS.length - 1) : (age > 0 ? 1 : 0);
        const ch = CELL_CHARS[charIdx];

        // Color by age and generation
        const hue = (this.generation * 3 + age * 20 + x + y) % 360;
        const sat = alive ? 90 : 40;
        const light = alive ? 40 + age * 3 : 10 + age * 5;

        this.grid.setCell(x, y, ch, `hsl(${hue},${sat}%,${Math.min(light, 80)}%)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.seedCells();
    this.generation = 0;
    this.stepTimer = 0;
  }

  dispose(): void {}
}
