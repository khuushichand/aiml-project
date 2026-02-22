import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const RING_PATTERNS = [
  "+-+-+-+-",
  "oOoOoOoO",
  ".*.*.*.*",
  "=#=#=#=#",
  "<>|<>|<>",
  "~^~^~^~^",
  "xXxXxXxX",
  "@*@*@*@*",
  ":.:.:.:",
  "##++##++",
  "&%&%&%&%",
  "(){}(){}",
];

export default class AsciiMandala implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private currentRing = 0;
  private ringTimer = 0;
  private maxRings = 12;
  private hueOffset = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.currentRing = 0;
    this.ringTimer = 0;
    this.hueOffset = 0;
  }

  update(elapsed: number, dt: number): void {
    this.hueOffset = (elapsed * 0.03) % 360;
    this.ringTimer += dt;

    // Add a new ring every 600ms
    if (this.ringTimer > 600 && this.currentRing < this.maxRings) {
      this.currentRing++;
      this.ringTimer = 0;
    }

    // Reset cycle when all rings drawn and some time passed
    if (this.currentRing >= this.maxRings && this.ringTimer > 2000) {
      this.currentRing = 0;
      this.ringTimer = 0;
    }

    const cx = 40;
    const cy = 12;

    this.grid.clear("#000");

    // Draw rings from outermost visible to innermost
    for (let ring = 0; ring < this.currentRing; ring++) {
      const radius = (ring + 1) * 0.9;
      const pattern = RING_PATTERNS[ring % RING_PATTERNS.length];
      const symmetry = 8;
      const hue = (this.hueOffset + ring * 30) % 360;
      const light = 40 + (ring % 4) * 10;

      // Draw points around the ring
      const circumference = Math.floor(2 * Math.PI * radius * 5);
      for (let i = 0; i < circumference; i++) {
        const angle = (i / circumference) * 2 * Math.PI;

        // Decorative radius modulation for ornate shapes
        const modRadius = radius + 0.3 * Math.sin(angle * symmetry + elapsed * 0.001);

        const px = Math.round(cx + modRadius * Math.cos(angle) * 4);
        const py = Math.round(cy + modRadius * Math.sin(angle) * 1.8);

        if (px < 0 || px >= 80 || py < 0 || py >= 24) continue;

        const ch = pattern[i % pattern.length];
        const cellHue = (hue + i * 2) % 360;
        this.grid.setCell(px, py, ch, `hsl(${cellHue},85%,${light}%)`);
      }
    }

    // Center ornament
    if (this.currentRing > 0) {
      const centerHue = (this.hueOffset + elapsed * 0.1) % 360;
      this.grid.setCell(cx, cy, "@", `hsl(${centerHue},100%,70%)`);
      this.grid.setCell(cx - 1, cy, "<", `hsl(${centerHue},100%,60%)`);
      this.grid.setCell(cx + 1, cy, ">", `hsl(${centerHue},100%,60%)`);
      this.grid.setCell(cx, cy - 1, "^", `hsl(${centerHue},100%,60%)`);
      this.grid.setCell(cx, cy + 1, "v", `hsl(${centerHue},100%,60%)`);
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.currentRing = 0;
    this.ringTimer = 0;
    this.hueOffset = 0;
  }

  dispose(): void {}
}
