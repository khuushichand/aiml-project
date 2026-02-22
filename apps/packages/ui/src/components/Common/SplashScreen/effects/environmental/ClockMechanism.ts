import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Gear { cx: number; cy: number; r: number; teeth: number; speed: number; color: string }

const GEAR_COLORS = ["#cc8844", "#ddaa55", "#bb7733", "#eebb66", "#aa6622"];

export default class ClockMechanismEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private gears: Gear[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.gears = [
      { cx: 20, cy: 12, r: 8, teeth: 16, speed: 1, color: GEAR_COLORS[0] },
      { cx: 38, cy: 10, r: 6, teeth: 12, speed: -1.33, color: GEAR_COLORS[1] },
      { cx: 52, cy: 14, r: 7, teeth: 14, speed: 1.14, color: GEAR_COLORS[2] },
      { cx: 66, cy: 8, r: 5, teeth: 10, speed: -1.6, color: GEAR_COLORS[3] },
      { cx: 40, cy: 20, r: 4, teeth: 8, speed: 2, color: GEAR_COLORS[4] },
    ];
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#1a1008");

    for (const g of this.gears) {
      const angle = this.time * g.speed;
      this.drawGear(g, angle);
    }

    // pendulum
    const pendAngle = Math.sin(this.time * 2) * 0.4;
    const px = 10;
    const py = 3;
    for (let i = 0; i < 8; i++) {
      const bx = Math.round(px + Math.sin(pendAngle) * i * 1.5);
      const by = py + i;
      if (bx >= 0 && bx < this.grid.cols && by < this.grid.rows) {
        this.grid.setCell(bx, by, i < 7 ? "|" : "O", "#ccaa44");
      }
    }

    this.grid.writeCentered(1, "[ CLOCKWORK ]", "#eedd88");
  }

  private drawGear(g: Gear, angle: number): void {
    const steps = g.teeth * 4;
    for (let i = 0; i < steps; i++) {
      const a = (i / steps) * Math.PI * 2 + angle;
      const isTooth = (i % 4) < 2;
      const r = isTooth ? g.r * 2 : (g.r - 1) * 2; // stretch x for aspect ratio
      const ry = isTooth ? g.r : g.r - 1;
      const px = Math.round(g.cx + Math.cos(a) * r);
      const py = Math.round(g.cy + Math.sin(a) * ry);
      if (px >= 0 && px < this.grid.cols && py >= 0 && py < this.grid.rows) {
        const ch = isTooth ? "#" : "o";
        this.grid.setCell(px, py, ch, g.color);
      }
    }
    // center axle
    this.grid.setCell(g.cx, g.cy, "+", "#ffffff");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#1a1008";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; }
  dispose(): void { this.gears = []; }
}
