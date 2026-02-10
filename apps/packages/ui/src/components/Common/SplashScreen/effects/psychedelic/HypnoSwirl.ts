import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const RING_CHARS = "/-\\|/-\\|";

export default class HypnoSwirl implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private angleOffset = 0;
  private pulsePhase = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.angleOffset = 0;
    this.pulsePhase = 0;
  }

  update(elapsed: number, dt: number): void {
    this.angleOffset = elapsed * 0.001;
    this.pulsePhase = elapsed * 0.003;

    const cx = 40;
    const cy = 12;

    this.grid.clear("#000");

    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 80; x++) {
        const dx = (x - cx) / 40;
        const dy = (y - cy) / 12;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);

        // Spiral formula: combine angle and distance
        const spiral = angle + dist * 5 - this.angleOffset * 2;
        const ringVal = Math.sin(spiral * 3);

        // Concentric ring modulation
        const ring = Math.sin(dist * 12 - this.angleOffset * 4);
        const combined = ringVal * 0.6 + ring * 0.4;

        if (dist > 1.05) {
          this.grid.setCell(x, y, " ", "#000");
          continue;
        }

        // Choose char based on spiral phase
        const charIdx = Math.floor(((combined + 1) / 2) * (RING_CHARS.length - 1));
        const ch = combined > 0.3 ? RING_CHARS[charIdx] : combined > -0.3 ? "." : " ";

        // Pulse accent color
        const pulseVal = Math.sin(this.pulsePhase + dist * 3);
        let color: string;
        if (pulseVal > 0.6) {
          const hue = (elapsed * 0.08 + dist * 120) % 360;
          color = `hsl(${hue},100%,65%)`;
        } else if (combined > 0) {
          color = "#ffffff";
        } else {
          color = "#444444";
        }

        this.grid.setCell(x, y, ch, color);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.angleOffset = 0;
    this.pulsePhase = 0;
  }

  dispose(): void {}
}
