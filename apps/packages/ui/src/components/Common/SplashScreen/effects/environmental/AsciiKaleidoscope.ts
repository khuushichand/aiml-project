import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

const KALEI_CHARS = "\u2591\u2592\u2593\u2588*+#@%&";

function hslHex(h: number, s: number, l: number): string {
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * c).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

export default class AsciiKaleidoscopeEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear("#000000");
    const halfX = Math.floor(this.grid.cols / 2);
    const halfY = Math.floor(this.grid.rows / 2);

    for (let y = 0; y <= halfY; y++) {
      for (let x = 0; x <= halfX; x++) {
        const dx = x - halfX;
        const dy = y - halfY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const val = Math.sin(dist * 0.3 - this.time * 2)
          + Math.sin(angle * 4 + this.time * 1.5)
          + Math.sin((dist + angle) * 0.5 + this.time);
        const norm = (val + 3) / 6;
        const ci = Math.floor(norm * (KALEI_CHARS.length - 1));
        const hue = (norm * 360 + this.time * 40) % 360;
        const ch = KALEI_CHARS[ci];
        const color = hslHex(hue, 0.85, 0.5);

        // mirror across both axes
        const mx = this.grid.cols - 1 - x;
        const my = this.grid.rows - 1 - y;
        this.grid.setCell(x, y, ch, color);
        this.grid.setCell(mx, y, ch, color);
        this.grid.setCell(x, my, ch, color);
        this.grid.setCell(mx, my, ch, color);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.time = 0;
    this.grid.clear("#000000");
  }

  dispose(): void { /* nothing */ }
}
