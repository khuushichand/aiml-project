import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const BAR_CHARS = [" ", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"];

export default class MusicVisualizer implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private numBars = 32;
  private barHeights: number[] = [];
  private targetHeights: number[] = [];
  private beatPhase = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
    this.barHeights = new Array(this.numBars).fill(0);
    this.targetHeights = new Array(this.numBars).fill(0);
  }

  update(elapsed: number, dt: number): void {
    this.elapsed = elapsed;

    // Simulated beat at ~120 BPM
    this.beatPhase = (elapsed / 500) % 1;
    const beat = this.beatPhase < 0.1;

    for (let i = 0; i < this.numBars; i++) {
      // Simulate frequency response
      const freq = i / this.numBars;
      const bass = Math.sin(elapsed / 250 + i * 0.1) * (1 - freq) * 0.8;
      const mid = Math.sin(elapsed / 180 + i * 0.3) * (freq > 0.2 && freq < 0.6 ? 0.7 : 0.2);
      const treble = Math.sin(elapsed / 120 + i * 0.7) * freq * 0.5;
      const beatBoost = beat ? 0.4 * (1 - freq) : 0;

      this.targetHeights[i] = Math.max(0, Math.min(1, (bass + mid + treble + beatBoost + 0.3) * 0.7));

      // Smooth interpolation
      const speed = dt * 0.008;
      this.barHeights[i] += (this.targetHeights[i] - this.barHeights[i]) * speed;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    grid.writeCentered(0, "TLDW Audio Visualizer", "#ffffff");

    const maxBarH = 18;
    const barWidth = 2;
    const gap = 0;
    const totalWidth = this.numBars * (barWidth + gap);
    const startX = Math.floor((80 - totalWidth) / 2);
    const bottomY = 22;

    for (let i = 0; i < this.numBars; i++) {
      const h = Math.floor(this.barHeights[i] * maxBarH);
      const x = startX + i * (barWidth + gap);

      const hue = (i / this.numBars) * 300;

      for (let row = 0; row < h; row++) {
        const y = bottomY - row;
        if (y < 2 || y > 22) continue;

        const brightness = 40 + (row / maxBarH) * 50;
        const color = `hsl(${hue},85%,${brightness}%)`;

        for (let bx = 0; bx < barWidth; bx++) {
          const px = x + bx;
          if (px >= 0 && px < 80) {
            const charIdx = row === h - 1
              ? Math.floor((this.barHeights[i] * maxBarH - h + 1) * (BAR_CHARS.length - 1))
              : BAR_CHARS.length - 1;
            grid.setCell(px, y, BAR_CHARS[Math.max(0, Math.min(charIdx, BAR_CHARS.length - 1))], color);
          }
        }
      }
    }

    // Beat indicator
    const beatChar = this.beatPhase < 0.1 ? "*" : ".";
    grid.writeCentered(23, `${beatChar} 120 BPM ${beatChar}`, "#ff4488");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.barHeights = new Array(this.numBars).fill(0);
    this.targetHeights = new Array(this.numBars).fill(0);
    this.grid.clear();
  }

  dispose(): void {
    this.barHeights = [];
    this.targetHeights = [];
    this.grid.clear();
  }
}
