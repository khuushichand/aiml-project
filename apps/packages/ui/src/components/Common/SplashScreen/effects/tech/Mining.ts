import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const ROCK_CHARS = ["\u2593", "\u2592", "\u2588", "#", "%"];
const GEM_CHARS = ["*", "+", "o"];
const PICKAXE_FRAMES = ["/", "-", "\\", "|"];

interface Miner {
  x: number;
  y: number;
  dx: number;
  dy: number;
  frame: number;
}

export default class Mining implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private terrain: { ch: string; color: string; mined: boolean }[][] = [];
  private miner: Miner = { x: 0, y: 12, dx: 1, dy: 0, frame: 0 };
  private lastMoveTime = 0;
  private revealText = "  Welcome to TLDW - Your Research Assistant  ";

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private buildTerrain(): void {
    this.terrain = [];
    for (let y = 0; y < 24; y++) {
      this.terrain[y] = [];
      for (let x = 0; x < 80; x++) {
        const isGem = Math.random() < 0.03;
        const ch = isGem
          ? GEM_CHARS[Math.floor(Math.random() * GEM_CHARS.length)]
          : ROCK_CHARS[Math.floor(Math.random() * ROCK_CHARS.length)];
        const color = isGem
          ? ["#ffff00", "#00ffff", "#ff00ff"][Math.floor(Math.random() * 3)]
          : `hsl(${25 + Math.random() * 15},${40 + Math.random() * 20}%,${20 + Math.random() * 15}%)`;
        this.terrain[y][x] = { ch, color, mined: false };
      }
    }
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    const moveDelay = 80;
    if (elapsed - this.lastMoveTime >= moveDelay) {
      this.lastMoveTime = elapsed;

      // Mine current position
      const { x, y } = this.miner;
      if (x >= 0 && x < 80 && y >= 0 && y < 24) {
        this.terrain[y][x].mined = true;
      }

      // Move miner in a snake pattern
      this.miner.x += this.miner.dx;

      if (this.miner.x >= 79) {
        this.miner.dx = -1;
        this.miner.y += 1;
        if (this.miner.y >= 24) {
          this.miner.y = 0;
          this.buildTerrain();
        }
      } else if (this.miner.x <= 0) {
        this.miner.dx = 1;
        this.miner.y += 1;
        if (this.miner.y >= 24) {
          this.miner.y = 0;
          this.buildTerrain();
        }
      }

      this.miner.frame = (this.miner.frame + 1) % 4;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Draw terrain
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const cell = this.terrain[y][x];
        if (cell.mined) {
          // Show revealed content (empty or text at center)
          if (y === 12) {
            const textOffset = x - Math.floor((80 - this.revealText.length) / 2);
            if (textOffset >= 0 && textOffset < this.revealText.length) {
              grid.setCell(x, y, this.revealText[textOffset], "#ffffff");
            }
          }
        } else {
          grid.setCell(x, y, cell.ch, cell.color);
        }
      }
    }

    // Draw miner (pickaxe)
    const { x: mx, y: my, frame } = this.miner;
    if (mx >= 0 && mx < 80 && my >= 0 && my < 24) {
      grid.setCell(mx, my, PICKAXE_FRAMES[frame], "#ffffff");
    }
    // Miner body behind pickaxe
    const bodyX = mx - this.miner.dx;
    if (bodyX >= 0 && bodyX < 80 && my >= 0 && my < 24) {
      grid.setCell(bodyX, my, "@", "#ffcc00");
    }

    // Stats overlay
    const mined = this.terrain.flat().filter(c => c.mined).length;
    const total = 80 * 24;
    const pct = ((mined / total) * 100).toFixed(1);
    grid.writeString(0, 0, `Mined: ${pct}%`, "#00ff00");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.lastMoveTime = 0;
    this.miner = { x: 0, y: 0, dx: 1, dy: 0, frame: 0 };
    this.buildTerrain();
    this.grid.clear();
  }

  dispose(): void {
    this.terrain = [];
    this.grid.clear();
  }
}
