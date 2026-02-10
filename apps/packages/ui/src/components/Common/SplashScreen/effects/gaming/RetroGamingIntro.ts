import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class RetroGamingIntro implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private titleY = -6;
  private blinkTimer = 0;
  private blinkOn = true;
  private stars: { x: number; y: number; char: string; color: string }[] = [];

  private titleLines = [
    "  ████████╗██╗     ██████╗ ██╗    ██╗",
    "  ╚══██╔══╝██║     ██╔══██╗██║    ██║",
    "     ██║   ██║     ██║  ██║██║ █╗ ██║",
    "     ██║   ██║     ██║  ██║██║███╗██║",
    "     ██║   ███████╗██████╔╝╚███╔███╔╝",
    "     ╚═╝   ╚══════╝╚═════╝  ╚══╝╚══╝ ",
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.titleY = -6;
    this.blinkTimer = 0;
    this.blinkOn = true;
    this.stars = [];
    for (let i = 0; i < 30; i++) {
      this.stars.push({
        x: Math.floor(Math.random() * 80),
        y: Math.floor(Math.random() * 24),
        char: ["*", ".", "+", "·"][Math.floor(Math.random() * 4)],
        color: ["#fff", "#aaa", "#ff0", "#0ff"][Math.floor(Math.random() * 4)],
      });
    }
  }

  update(elapsed: number, dt: number): void {
    const targetY = 4;
    if (this.titleY < targetY) {
      this.titleY += dt * 0.008;
      if (this.titleY > targetY) this.titleY = targetY;
    }
    this.blinkTimer += dt;
    if (this.blinkTimer > 500) {
      this.blinkTimer = 0;
      this.blinkOn = !this.blinkOn;
    }
    if (Math.random() < 0.05) {
      const idx = Math.floor(Math.random() * this.stars.length);
      this.stars[idx].x = Math.floor(Math.random() * 80);
      this.stars[idx].y = Math.floor(Math.random() * 24);
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);
    for (const s of this.stars) {
      this.grid.setCell(s.x, s.y, s.char, s.color);
    }
    const row = Math.round(this.titleY);
    for (let i = 0; i < this.titleLines.length; i++) {
      const y = row + i;
      if (y >= 0 && y < 24) {
        this.grid.writeCentered(y, this.titleLines[i], "#0f0");
      }
    }
    this.grid.writeCentered(12, "── THE ULTIMATE MEDIA COMPANION ──", "#0a0");
    this.grid.writeCentered(15, "© 2026  ALL RIGHTS RESERVED", "#555");
    if (this.blinkOn) {
      this.grid.writeCentered(20, "▶  PRESS START  ◀", "#ff0");
    }
    this.grid.writeCentered(22, "INSERT COIN", "#888");
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.titleY = -6;
    this.blinkTimer = 0;
    this.blinkOn = true;
  }

  dispose(): void {
    this.stars = [];
  }
}
