import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Rock { x: number; y: number; size: number }

const SAND_COLOR = "#c8b898";
const RAKE_COLOR = "#a09070";
const ROCK_COLOR = "#667766";
const DARK_SAND = "#b0a080";
const BG = "#d8c8a8";

export default class ZenGardenEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private rocks: Rock[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.rocks = [
      { x: 20, y: 10, size: 2 },
      { x: 55, y: 8, size: 3 },
      { x: 38, y: 16, size: 1 },
      { x: 65, y: 15, size: 2 },
    ];
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.grid.clear(BG);

    // draw rake lines (horizontal flowing curves)
    for (let y = 0; y < this.grid.rows; y++) {
      for (let x = 0; x < this.grid.cols; x++) {
        // check proximity to any rock for ripple patterns
        let nearRock = false;
        let rippleDist = 999;
        for (const rock of this.rocks) {
          const dx = (x - rock.x) / (rock.size * 2 + 1);
          const dy = (y - rock.y) / (rock.size + 0.5);
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 1) { nearRock = true; break; }
          if (d < rippleDist) rippleDist = d;
        }

        if (nearRock) continue;

        // concentric ripples around rocks
        let isRipple = false;
        for (const rock of this.rocks) {
          const dx = x - rock.x;
          const dy = (y - rock.y) * 2;
          const d = Math.sqrt(dx * dx + dy * dy);
          const ring = (d + this.time * 0.3) % 4;
          if (d < (rock.size + 1) * 5 && d > rock.size * 2 && ring < 1.2) {
            isRipple = true;
            break;
          }
        }

        if (isRipple) {
          this.grid.setCell(x, y, "~", RAKE_COLOR);
        } else {
          // flowing horizontal rake lines
          const wave = Math.sin(x * 0.15 + this.time * 0.2) + Math.sin(y * 0.5 + this.time * 0.1);
          if (y % 2 === 0 && Math.abs(wave) < 0.8) {
            this.grid.setCell(x, y, "-", DARK_SAND);
          } else {
            this.grid.setCell(x, y, ".", SAND_COLOR);
          }
        }
      }
    }

    // draw rocks
    for (const rock of this.rocks) {
      for (let dy = -rock.size; dy <= rock.size; dy++) {
        for (let dx = -rock.size * 2; dx <= rock.size * 2; dx++) {
          const rx = rock.x + dx;
          const ry = rock.y + dy;
          const nd = Math.sqrt((dx / 2) ** 2 + dy ** 2);
          if (nd <= rock.size && rx >= 0 && rx < this.grid.cols && ry >= 0 && ry < this.grid.rows) {
            const ch = nd < rock.size * 0.5 ? "@" : "#";
            this.grid.setCell(rx, ry, ch, ROCK_COLOR);
          }
        }
      }
    }

    // border bamboo fence
    for (let x = 0; x < this.grid.cols; x++) {
      this.grid.setCell(x, 0, "=", "#668844");
      this.grid.setCell(x, this.grid.rows - 1, "=", "#668844");
    }
    for (let y = 0; y < this.grid.rows; y++) {
      this.grid.setCell(0, y, "|", "#668844");
      this.grid.setCell(this.grid.cols - 1, y, "|", "#668844");
    }

    this.grid.writeCentered(0, "= Zen Garden =", "#557744");
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; }
  dispose(): void { this.rocks = []; }
}
