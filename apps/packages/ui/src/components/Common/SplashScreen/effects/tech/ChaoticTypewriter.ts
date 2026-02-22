import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const TARGET_LINES = [
  "",
  "  Welcome to TLDW",
  "  ================",
  "",
  "  Too Long; Didn't Watch",
  "",
  "  Your personal research assistant",
  "  for media analysis, transcription,",
  "  and knowledge management.",
  "",
  "  Initializing systems...",
  "  Loading AI models...",
  "  Connecting to providers...",
  "",
  "  Status: READY",
  "",
];

interface CharState {
  target: string;
  current: string;
  settled: boolean;
  settleTime: number;
  x: number;
  y: number;
}

export default class ChaoticTypewriter implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private chars: CharState[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private buildChars(): void {
    this.chars = [];
    let idx = 0;
    const startY = Math.floor((24 - TARGET_LINES.length) / 2);

    for (let li = 0; li < TARGET_LINES.length; li++) {
      const line = TARGET_LINES[li];
      for (let ci = 0; ci < line.length; ci++) {
        if (line[ci] === " ") continue;
        const scrambleX = Math.floor(Math.random() * 80);
        const scrambleY = Math.floor(Math.random() * 24);
        this.chars.push({
          target: line[ci],
          current: String.fromCharCode(33 + Math.floor(Math.random() * 93)),
          settled: false,
          settleTime: 500 + idx * 40 + Math.random() * 300,
          x: scrambleX,
          y: scrambleY,
        });
        idx++;
      }
    }
  }

  private getTargetPos(charIdx: number): { x: number; y: number } {
    let idx = 0;
    const startY = Math.floor((24 - TARGET_LINES.length) / 2);
    for (let li = 0; li < TARGET_LINES.length; li++) {
      const line = TARGET_LINES[li];
      for (let ci = 0; ci < line.length; ci++) {
        if (line[ci] === " ") continue;
        if (idx === charIdx) return { x: ci, y: startY + li };
        idx++;
      }
    }
    return { x: 0, y: 0 };
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    for (let i = 0; i < this.chars.length; i++) {
      const ch = this.chars[i];
      if (ch.settled) continue;

      if (elapsed >= ch.settleTime) {
        const target = this.getTargetPos(i);
        ch.x = target.x;
        ch.y = target.y;
        ch.current = ch.target;
        ch.settled = true;
      } else {
        // Randomly change character and drift toward target
        if (Math.random() < 0.15) {
          ch.current = String.fromCharCode(33 + Math.floor(Math.random() * 93));
        }
        const target = this.getTargetPos(i);
        const progress = elapsed / ch.settleTime;
        ch.x = Math.round(ch.x + (target.x - ch.x) * progress * 0.05);
        ch.y = Math.round(ch.y + (target.y - ch.y) * progress * 0.05);
        ch.x = Math.max(0, Math.min(79, ch.x));
        ch.y = Math.max(0, Math.min(23, ch.y));
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    for (const ch of this.chars) {
      const color = ch.settled ? "#ffffff" : "#ff8844";
      grid.setCell(ch.x, ch.y, ch.current, color);
    }

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.buildChars();
    this.grid.clear();
  }

  dispose(): void {
    this.chars = [];
    this.grid.clear();
  }
}
