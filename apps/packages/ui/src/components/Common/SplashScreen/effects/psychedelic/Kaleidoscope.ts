import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const KCHARS = " .+*xX#%@&";

export default class Kaleidoscope implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private rotation = 0;
  private shapes: { x: number; y: number; size: number; hue: number; speed: number }[] = [];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.rotation = 0;
    this.generateShapes();
  }

  private generateShapes(): void {
    this.shapes = Array.from({ length: 12 }, () => ({
      x: Math.random() * 0.5,
      y: Math.random() * 0.5,
      size: 0.05 + Math.random() * 0.15,
      hue: Math.random() * 360,
      speed: 0.2 + Math.random() * 0.8,
    }));
  }

  update(elapsed: number, dt: number): void {
    const t = elapsed / 1000;
    this.rotation = t * 0.15;

    const cx = 40;
    const cy = 12;
    const segments = 6;
    const segAngle = (2 * Math.PI) / segments;

    // Animate shapes in the source sector
    for (const s of this.shapes) {
      s.x = 0.1 + 0.3 * Math.sin(t * s.speed + s.hue);
      s.y = 0.1 + 0.3 * Math.cos(t * s.speed * 0.7 + s.hue * 2);
    }

    this.grid.clear("#000");

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const dx = (x - cx) / 40;
        const dy = (y - cy) / 12;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > 1.0) continue;

        let angle = Math.atan2(dy, dx) - this.rotation;
        if (angle < 0) angle += 2 * Math.PI;

        // Fold into source sector
        let fAngle = angle % segAngle;
        // Mirror alternate sectors
        const sector = Math.floor(angle / segAngle);
        if (sector % 2 === 1) fAngle = segAngle - fAngle;

        // Map back to source coordinates
        const srcX = dist * Math.cos(fAngle);
        const srcY = dist * Math.sin(fAngle);

        // Compute intensity from shapes
        let intensity = 0;
        let bestHue = 0;
        for (const s of this.shapes) {
          const sdx = srcX - s.x;
          const sdy = srcY - s.y;
          const sDist = Math.sqrt(sdx * sdx + sdy * sdy);
          if (sDist < s.size) {
            const contrib = 1 - sDist / s.size;
            if (contrib > intensity) {
              intensity = contrib;
              bestHue = s.hue + t * 30;
            }
          }
        }

        // Background pattern
        const bgPattern = Math.sin(srcX * 15 + t) * Math.cos(srcY * 15 - t * 0.5);
        const bgNorm = (bgPattern + 1) / 2;

        if (intensity > 0.05) {
          const charIdx = Math.floor(intensity * (KCHARS.length - 1));
          const hue = bestHue % 360;
          this.grid.setCell(x, y, KCHARS[charIdx], `hsl(${hue},95%,${40 + intensity * 40}%)`);
        } else if (bgNorm > 0.3) {
          const ci = Math.floor(bgNorm * 3);
          const hue = (dist * 200 + t * 20) % 360;
          this.grid.setCell(x, y, KCHARS[ci], `hsl(${hue},60%,25%)`);
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.rotation = 0;
    this.generateShapes();
  }

  dispose(): void {}
}
