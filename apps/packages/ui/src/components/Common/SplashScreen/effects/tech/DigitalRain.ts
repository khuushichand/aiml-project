import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*<>[]{}|/\\~";

interface Drop {
  x: number;
  y: number;
  speed: number;
  length: number;
  highlight: number;
}

export default class DigitalRain implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private drops: Drop[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
    this.drops = [];

    for (let i = 0; i < 50; i++) {
      this.drops.push(this.makeDrop());
    }
  }

  private makeDrop(): Drop {
    return {
      x: Math.floor(Math.random() * 80),
      y: -Math.floor(Math.random() * 24),
      speed: 0.003 + Math.random() * 0.01,
      length: 5 + Math.floor(Math.random() * 15),
      highlight: Math.floor(Math.random() * 5),
    };
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    for (const drop of this.drops) {
      drop.y += drop.speed * 16;
      if (drop.y - drop.length > 24) {
        Object.assign(drop, this.makeDrop());
        drop.y = -drop.length;
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    for (const drop of this.drops) {
      const headY = Math.floor(drop.y);
      for (let i = 0; i < drop.length; i++) {
        const cy = headY - i;
        if (cy < 0 || cy >= 24) continue;

        const ci = (Math.floor(this.elapsed / 80) + i + drop.x * 7) % CHARSET.length;
        const ch = CHARSET[ci];

        let color: string;
        if (i === 0) {
          color = "#ffffff";
        } else if (i === drop.highlight) {
          color = "#aaffaa";
        } else {
          const fade = 1.0 - (i / drop.length);
          const g = Math.floor(100 + fade * 155);
          color = `rgb(0,${g},0)`;
        }

        grid.setCell(drop.x, cy, ch, color);
      }
    }

    // Title in magenta
    const title = " T L D W ";
    const sub = "Digital Rain Protocol";
    grid.writeCentered(11, title, "#ff00ff");
    grid.writeCentered(12, sub, "#cc44cc");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.drops = [];
    this.grid.clear();
  }

  dispose(): void {
    this.drops = [];
    this.grid.clear();
  }
}
