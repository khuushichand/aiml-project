import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const DENSITY = " .:-=+*#%@";

interface Blob {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  hue: number;
}

export default class LavaLamp implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private blobs: Blob[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.spawnBlobs();
  }

  private spawnBlobs(): void {
    this.blobs = Array.from({ length: 7 }, () => ({
      x: 10 + Math.random() * 60,
      y: 4 + Math.random() * 16,
      vx: (Math.random() - 0.5) * 2,
      vy: (Math.random() - 0.5) * 3,
      radius: 3 + Math.random() * 5,
      hue: Math.random() * 60 + 10, // warm: 10-70 (red/orange/yellow)
    }));
  }

  update(elapsed: number, dt: number): void {
    const dtSec = dt / 1000;

    // Update blob positions
    for (const b of this.blobs) {
      // Gentle buoyancy oscillation
      b.vy += Math.sin(elapsed * 0.001 + b.hue) * 0.5 * dtSec;
      b.vx += Math.sin(elapsed * 0.0007 + b.x * 0.1) * 0.3 * dtSec;

      b.x += b.vx * dtSec * 3;
      b.y += b.vy * dtSec * 3;

      // Damping
      b.vx *= 0.99;
      b.vy *= 0.99;

      // Bounce off walls softly
      if (b.x < 3) { b.x = 3; b.vx = Math.abs(b.vx) * 0.5; }
      if (b.x > 77) { b.x = 77; b.vx = -Math.abs(b.vx) * 0.5; }
      if (b.y < 1) { b.y = 1; b.vy = Math.abs(b.vy) * 0.5; }
      if (b.y > 22) { b.y = 22; b.vy = -Math.abs(b.vy) * 0.5; }

      // Slowly shift hue
      b.hue = (b.hue + dtSec * 5) % 70 + 10;

      // Pulsing radius
      b.radius = 3.5 + 2 * Math.sin(elapsed * 0.001 + b.hue * 0.1);
    }

    // Render metaball field
    const threshold = 1.0;
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        let field = 0;
        let hueSum = 0;
        let weightSum = 0;

        for (const b of this.blobs) {
          const dx = (x - b.x) / (b.radius * 1.5);
          const dy = (y - b.y) / (b.radius * 0.8);
          const distSq = dx * dx + dy * dy;
          const contrib = 1 / (1 + distSq * 3);
          field += contrib;
          hueSum += b.hue * contrib;
          weightSum += contrib;
        }

        if (field > threshold * 0.2) {
          const norm = Math.min(field / threshold, 1);
          const charIdx = Math.floor(norm * (DENSITY.length - 1));
          const hue = weightSum > 0 ? hueSum / weightSum : 30;
          const sat = 80 + norm * 20;
          const light = 25 + norm * 45;
          this.grid.setCell(x, y, DENSITY[charIdx], `hsl(${hue},${sat}%,${light}%)`);
        } else {
          // Background warmth
          const bgHue = 280 + Math.sin(y * 0.2) * 20;
          this.grid.setCell(x, y, " ", `hsl(${bgHue},20%,5%)`);
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#0a0005";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.spawnBlobs();
  }

  dispose(): void {}
}
