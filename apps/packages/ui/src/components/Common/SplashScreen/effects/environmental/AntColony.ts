import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Ant { x: number; y: number; dir: number }

const ANT_COLOR = "#cc4422";
const TRAIL_COLORS = ["#1a1a08", "#2a2a10", "#3a3a18", "#4a4a20", "#5a5a28"];
const FOOD_COLOR = "#44cc44";
const NEST_COLOR = "#886644";
const BG = "#0a0a05";

export default class AntColonyEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private cols = 80;
  private rows = 24;
  private pheromones: number[] = [];
  private ants: Ant[] = [];
  private food: Set<number> = new Set();
  private nestX = 40;
  private nestY = 12;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.cols;
    this.cellH = height / this.rows;
    this.pheromones = new Array(this.cols * this.rows).fill(0);
    this.ants = [];
    for (let i = 0; i < 40; i++) {
      this.ants.push({
        x: this.nestX + Math.floor(Math.random() * 6 - 3),
        y: this.nestY + Math.floor(Math.random() * 4 - 2),
        dir: Math.floor(Math.random() * 8),
      });
    }
    // food sources
    this.food = new Set();
    const foodSpots = [{ x: 10, y: 5 }, { x: 65, y: 18 }, { x: 55, y: 4 }];
    for (const f of foodSpots) {
      for (let dy = -2; dy <= 2; dy++) {
        for (let dx = -2; dx <= 2; dx++) {
          const fx = f.x + dx, fy = f.y + dy;
          if (fx >= 0 && fx < this.cols && fy >= 0 && fy < this.rows) {
            this.food.add(fy * this.cols + fx);
          }
        }
      }
    }
  }

  private dirs = [
    [0, -1], [1, -1], [1, 0], [1, 1],
    [0, 1], [-1, 1], [-1, 0], [-1, -1],
  ];

  update(_elapsed: number, _dt: number): void {
    // decay pheromones
    for (let i = 0; i < this.pheromones.length; i++) {
      this.pheromones[i] *= 0.995;
    }

    for (const ant of this.ants) {
      // sense ahead in 3 directions
      let bestDir = ant.dir;
      let bestVal = -1;
      for (let d = -1; d <= 1; d++) {
        const nd = (ant.dir + d + 8) % 8;
        const nx = ant.x + this.dirs[nd][0];
        const ny = ant.y + this.dirs[nd][1];
        if (nx >= 0 && nx < this.cols && ny >= 0 && ny < this.rows) {
          const val = this.pheromones[ny * this.cols + nx];
          if (val > bestVal) { bestVal = val; bestDir = nd; }
        }
      }

      // random wandering
      if (Math.random() < 0.3) {
        bestDir = (ant.dir + Math.floor(Math.random() * 3) - 1 + 8) % 8;
      }

      ant.dir = bestDir;
      ant.x += this.dirs[ant.dir][0];
      ant.y += this.dirs[ant.dir][1];

      // wrap
      if (ant.x < 0) ant.x = this.cols - 1;
      if (ant.x >= this.cols) ant.x = 0;
      if (ant.y < 0) ant.y = this.rows - 1;
      if (ant.y >= this.rows) ant.y = 0;

      // deposit pheromone
      const idx = ant.y * this.cols + ant.x;
      this.pheromones[idx] = Math.min(1, this.pheromones[idx] + 0.15);
    }

    this.grid.clear(BG);

    // trails
    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.cols; x++) {
        const p = this.pheromones[y * this.cols + x];
        if (p > 0.05) {
          const ci = Math.floor(p * (TRAIL_COLORS.length - 1));
          this.grid.setCell(x, y, "\u00B7", TRAIL_COLORS[ci]);
        }
      }
    }

    // food
    for (const fi of this.food) {
      const fx = fi % this.cols, fy = Math.floor(fi / this.cols);
      this.grid.setCell(fx, fy, "%", FOOD_COLOR);
    }

    // nest
    this.grid.setCell(this.nestX, this.nestY, "O", NEST_COLOR);

    // ants
    for (const ant of this.ants) {
      this.grid.setCell(ant.x, ant.y, ".", ANT_COLOR);
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.pheromones.fill(0); }
  dispose(): void { this.ants = []; this.pheromones = []; this.food.clear(); }
}
