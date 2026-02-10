import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const HEX = "0123456789ABCDEF";
const BIN = "01";
const MIXED = "0123456789abcdef!@#$%^&*<>{}[]|/\\";

interface Stream {
  row: number;
  speed: number;
  offset: number;
  charset: string;
  color: string;
  length: number;
}

export default class DataStream implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private streams: Stream[] = [];

  private readonly colors = [
    "#00ff88", "#00ccff", "#ff6600", "#ffcc00",
    "#ff00ff", "#88ff00", "#00ffcc", "#ff3366",
  ];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
    this.streams = [];

    for (let i = 0; i < 24; i++) {
      const charsets = [HEX, BIN, MIXED];
      this.streams.push({
        row: i,
        speed: 0.02 + Math.random() * 0.08,
        offset: Math.random() * 80,
        charset: charsets[Math.floor(Math.random() * charsets.length)],
        color: this.colors[Math.floor(Math.random() * this.colors.length)],
        length: 20 + Math.floor(Math.random() * 60),
      });
    }
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    for (const s of this.streams) {
      const pos = s.offset + this.elapsed * s.speed;
      for (let i = 0; i < s.length; i++) {
        const x = Math.floor(pos + i) % (grid.cols + 20) - 10;
        if (x >= 0 && x < grid.cols) {
          const ci = (Math.floor(pos * 3) + i * 7) % s.charset.length;
          const ch = s.charset[ci];
          const fade = i < 3 ? 0.3 + (i / 3) * 0.7 : i > s.length - 3 ? 0.3 : 1.0;
          const r = parseInt(s.color.slice(1, 3), 16);
          const g = parseInt(s.color.slice(3, 5), 16);
          const b = parseInt(s.color.slice(5, 7), 16);
          const color = `rgb(${Math.floor(r * fade)},${Math.floor(g * fade)},${Math.floor(b * fade)})`;
          grid.setCell(x, s.row, ch, color);
        }
      }
    }

    grid.writeCentered(12, " tldw ", "#ffffff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.streams = [];
    this.grid.clear();
  }
}
