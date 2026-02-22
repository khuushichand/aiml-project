import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Fish { x: number; y: number; speed: number; dir: number; kind: number; color: string }
interface Bubble { x: number; y: number; speed: number }

const FISH_R = ["><>", "><>>", ">-=>"];
const FISH_L = ["<><", "<<><", "<=->"];
const FISH_COLORS = ["#ff8844", "#44ccff", "#ffcc00", "#ff44aa", "#44ff88", "#ff6666"];
const WEED_COLOR = "#228844";
const BUBBLE_COLOR = "#88ccee";
const WATER_BG = "#0a1a33";

export default class AsciiAquariumEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private fish: Fish[] = [];
  private bubbles: Bubble[] = [];
  private time = 0;
  private weeds: number[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.fish = [];
    for (let i = 0; i < 10; i++) {
      const dir = Math.random() < 0.5 ? 1 : -1;
      this.fish.push({
        x: Math.random() * this.grid.cols,
        y: 3 + Math.floor(Math.random() * 16),
        speed: 0.02 + Math.random() * 0.03,
        dir,
        kind: Math.floor(Math.random() * 3),
        color: FISH_COLORS[Math.floor(Math.random() * FISH_COLORS.length)],
      });
    }
    this.bubbles = [];
    this.weeds = [];
    for (let x = 0; x < this.grid.cols; x++) {
      this.weeds.push(Math.random() < 0.12 ? 2 + Math.floor(Math.random() * 4) : 0);
    }
    this.time = 0;
  }

  update(elapsed: number, dt: number): void {
    this.time = elapsed / 1000;
    const step = dt / 16;

    for (const f of this.fish) {
      f.x += f.speed * f.dir * step;
      if (f.x > this.grid.cols + 5) { f.x = -5; f.dir = 1; }
      if (f.x < -5) { f.x = this.grid.cols + 5; f.dir = -1; }
    }

    if (Math.random() < 0.08) {
      this.bubbles.push({
        x: 5 + Math.floor(Math.random() * (this.grid.cols - 10)),
        y: this.grid.rows - 2,
        speed: 0.05 + Math.random() * 0.05,
      });
    }
    for (const b of this.bubbles) b.y -= b.speed * step;
    this.bubbles = this.bubbles.filter(b => b.y > 0);

    this.grid.clear(WATER_BG);

    // seaweed
    for (let x = 0; x < this.grid.cols; x++) {
      const h = this.weeds[x];
      for (let i = 0; i < h; i++) {
        const wy = this.grid.rows - 1 - i;
        const sway = Math.sin(this.time * 1.5 + x * 0.5) > 0.3 ? 1 : 0;
        const wx = Math.min(this.grid.cols - 1, Math.max(0, x + (i > 1 ? sway : 0)));
        this.grid.setCell(wx, wy, i % 2 === 0 ? "|" : "/", WEED_COLOR);
      }
    }

    // sand bottom
    this.grid.fillRow(this.grid.rows - 1, ".", "#aa8855");

    // fish
    for (const f of this.fish) {
      const art = f.dir > 0 ? FISH_R[f.kind] : FISH_L[f.kind];
      const fx = Math.round(f.x);
      for (let c = 0; c < art.length; c++) {
        const gx = fx + c;
        if (gx >= 0 && gx < this.grid.cols && f.y < this.grid.rows) {
          this.grid.setCell(gx, f.y, art[c], f.color);
        }
      }
    }

    // bubbles
    for (const b of this.bubbles) {
      const by = Math.round(b.y);
      const ch = by % 3 === 0 ? "O" : by % 3 === 1 ? "o" : "\u00B0";
      if (b.x < this.grid.cols && by >= 0 && by < this.grid.rows) {
        this.grid.setCell(b.x, by, ch, BUBBLE_COLOR);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = WATER_BG;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.fish = []; this.bubbles = []; this.time = 0; }
  dispose(): void { this.fish = []; this.bubbles = []; this.weeds = []; }
}
