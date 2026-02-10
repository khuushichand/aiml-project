import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class PacmanEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private pacX = 0;
  private mouthOpen = true;
  private mouthTimer = 0;
  private ghostX = -8;
  private dots: boolean[] = [];
  private score = 0;
  private row = 12;
  private ghostColors = ["#f00", "#f0f", "#0ff", "#fa0"];
  private ghostOffsets = [0, -3, -6, -9];
  private loopCount = 0;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.resetDots();
    this.pacX = 0;
    this.ghostX = -8;
    this.score = 0;
    this.loopCount = 0;
  }

  private resetDots(): void {
    this.dots = [];
    for (let i = 0; i < 80; i++) {
      this.dots.push(i % 2 === 0);
    }
  }

  update(_elapsed: number, dt: number): void {
    this.mouthTimer += dt;
    if (this.mouthTimer > 150) {
      this.mouthTimer = 0;
      this.mouthOpen = !this.mouthOpen;
    }
    this.pacX += dt * 0.025;
    this.ghostX += dt * 0.022;

    const px = Math.floor(this.pacX);
    if (px >= 0 && px < 80 && this.dots[px]) {
      this.dots[px] = false;
      this.score += 10;
    }

    if (this.pacX > 85) {
      this.pacX = -2;
      this.ghostX = -12;
      this.resetDots();
      this.loopCount++;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    // Top border
    this.grid.fillRow(0, "═", "#00f");
    this.grid.writeCentered(1, "PAC-MAN", "#ff0");
    this.grid.writeString(2, 3, `SCORE: ${this.score}`, "#fff");
    this.grid.writeString(55, 3, `ROUND: ${this.loopCount + 1}`, "#fff");

    // Maze walls
    this.grid.fillRow(this.row - 2, "─", "#00f");
    this.grid.fillRow(this.row + 2, "─", "#00f");

    // Dots
    for (let i = 0; i < 80; i++) {
      if (this.dots[i]) {
        const isPower = i % 20 === 0;
        this.grid.setCell(i, this.row, isPower ? "●" : "·", isPower ? "#fff" : "#ffb");
      }
    }

    // Pacman
    const px = Math.floor(this.pacX);
    if (px >= 0 && px < 80) {
      this.grid.setCell(px, this.row, this.mouthOpen ? "C" : "O", "#ff0");
    }

    // Ghosts
    for (let g = 0; g < 4; g++) {
      const gx = Math.floor(this.ghostX + this.ghostOffsets[g]);
      if (gx >= 0 && gx < 80) {
        this.grid.setCell(gx, this.row, "M", this.ghostColors[g]);
      }
    }

    // Lives
    this.grid.writeString(2, 20, "LIVES: C C C", "#ff0");

    // Bottom decorations
    this.grid.writeCentered(22, "·····  WAKA WAKA WAKA  ·····", "#555");
    this.grid.fillRow(23, "═", "#00f");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.pacX = 0;
    this.ghostX = -8;
    this.score = 0;
    this.loopCount = 0;
    this.resetDots();
  }

  dispose(): void {
    this.dots = [];
  }
}
