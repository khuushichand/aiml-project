import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class SoundBarsEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private barCount = 32;
  private barHeights: number[] = [];
  private targetHeights: number[] = [];
  private beatTimer = 0;
  private beatInterval = 300;
  private time = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    const configuredBars = Number(config?.num_bars);
    if (Number.isFinite(configuredBars)) {
      this.barCount = Math.max(4, Math.min(40, Math.floor(configuredBars)));
    } else {
      this.barCount = 32;
    }
    this.barHeights = Array(this.barCount).fill(0);
    this.targetHeights = Array(this.barCount).fill(0);
    this.beatTimer = 0;
    this.time = 0;
    this.generateBeat();
  }

  private generateBeat(): void {
    for (let i = 0; i < this.barCount; i++) {
      // Create a pseudo-frequency distribution
      const center = this.barCount / 2;
      const dist = Math.abs(i - center) / center;
      const bass = i < 6 ? 0.8 : 0.3;
      const mid = dist < 0.3 ? 0.7 : 0.2;
      const treble = i > this.barCount - 6 ? 0.5 : 0.2;
      const base = Math.max(bass, mid, treble);
      this.targetHeights[i] = Math.floor((base + Math.random() * 0.5) * 18);
    }
  }

  private hslForBar(barIdx: number): string {
    const hue = Math.floor((barIdx / this.barCount) * 300);
    return `hsl(${hue}, 100%, 60%)`;
  }

  update(_elapsed: number, dt: number): void {
    this.time += dt;
    this.beatTimer += dt;
    if (this.beatTimer > this.beatInterval) {
      this.beatTimer = 0;
      this.beatInterval = 200 + Math.random() * 200;
      this.generateBeat();
    }

    // Smooth interpolation
    for (let i = 0; i < this.barCount; i++) {
      const diff = this.targetHeights[i] - this.barHeights[i];
      this.barHeights[i] += diff * Math.min(1, dt * 0.008);
      // Gravity pull down
      if (this.targetHeights[i] < this.barHeights[i]) {
        this.barHeights[i] -= dt * 0.01;
      }
      this.barHeights[i] = Math.max(0, Math.min(20, this.barHeights[i]));
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    this.grid.writeCentered(0, "♪ AUDIO VISUALIZER ♪", "#fff");

    const baseY = 22;
    const barWidth = this.barCount <= 32 ? 2 : 1;
    const gap = Math.floor((80 - this.barCount * barWidth) / 2);

    for (let i = 0; i < this.barCount; i++) {
      const h = Math.round(this.barHeights[i]);
      const x = gap + i * barWidth;
      const color = this.hslForBar(i);

      for (let j = 0; j < h; j++) {
        const y = baseY - j;
        if (y >= 2 && y < 24) {
          this.grid.setCell(x, y, "┃", color);
          if (barWidth > 1) {
            this.grid.setCell(x + 1, y, "┃", color);
          }
        }
      }

      // Peak indicator
      const peakY = baseY - h;
      if (peakY >= 2 && peakY < 24) {
        this.grid.setCell(x, peakY, "═", "#fff");
        if (barWidth > 1) {
          this.grid.setCell(x + 1, peakY, "═", "#fff");
        }
      }
    }

    // Bottom base line
    this.grid.fillRow(23, "─", "#333");

    // Time display
    const secs = Math.floor(this.time / 1000);
    const mins = Math.floor(secs / 60);
    const remSecs = secs % 60;
    const timeStr = `${mins}:${remSecs.toString().padStart(2, "0")}`;
    this.grid.writeString(2, 23, timeStr, "#888");
    this.grid.writeString(70, 23, "▶ PLAYING", "#0f0");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.barHeights = Array(this.barCount).fill(0);
    this.targetHeights = Array(this.barCount).fill(0);
    this.time = 0;
    this.beatTimer = 0;
  }

  dispose(): void {
    this.barHeights = [];
    this.targetHeights = [];
  }
}
