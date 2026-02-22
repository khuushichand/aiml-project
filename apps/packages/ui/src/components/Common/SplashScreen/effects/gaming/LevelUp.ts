import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface StatAnim {
  label: string;
  value: number;
  color: string;
  shown: boolean;
}

export default class LevelUpEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private timer = 0;
  private level = 1;
  private xpFill = 0;
  private ringRadius = 0;
  private flashOn = true;
  private flashTimer = 0;
  private phase: "xp_fill" | "flash" | "stats" | "idle" = "xp_fill";
  private statTimer = 0;
  private stats: StatAnim[] = [];

  private resetStats(): void {
    this.stats = [
      { label: "STR", value: Math.floor(Math.random() * 3) + 1, color: "#f55", shown: false },
      { label: "DEX", value: Math.floor(Math.random() * 3) + 1, color: "#5f5", shown: false },
      { label: "INT", value: Math.floor(Math.random() * 3) + 1, color: "#55f", shown: false },
      { label: "WIS", value: Math.floor(Math.random() * 2) + 1, color: "#ff5", shown: false },
      { label: "CON", value: Math.floor(Math.random() * 2) + 1, color: "#f5f", shown: false },
      { label: "CHA", value: Math.floor(Math.random() * 2) + 1, color: "#5ff", shown: false },
    ];
  }

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.level = 1;
    this.xpFill = 0;
    this.phase = "xp_fill";
    this.ringRadius = 0;
    this.timer = 0;
    this.resetStats();
  }

  update(_elapsed: number, dt: number): void {
    this.timer += dt;
    this.flashTimer += dt;
    if (this.flashTimer > 150) {
      this.flashTimer = 0;
      this.flashOn = !this.flashOn;
    }

    switch (this.phase) {
      case "xp_fill":
        this.xpFill += dt * 0.04;
        if (this.xpFill >= 100) {
          this.xpFill = 100;
          this.phase = "flash";
          this.timer = 0;
          this.ringRadius = 0;
        }
        break;
      case "flash":
        this.ringRadius += dt * 0.02;
        if (this.timer > 1200) {
          this.phase = "stats";
          this.timer = 0;
          this.statTimer = 0;
          this.level++;
        }
        break;
      case "stats":
        this.statTimer += dt;
        const idx = Math.floor(this.statTimer / 350);
        for (let i = 0; i <= idx && i < this.stats.length; i++) {
          this.stats[i].shown = true;
        }
        if (this.statTimer > 350 * this.stats.length + 1500) {
          this.phase = "idle";
          this.timer = 0;
        }
        break;
      case "idle":
        if (this.timer > 1000) {
          this.phase = "xp_fill";
          this.xpFill = 0;
          this.timer = 0;
          this.resetStats();
        }
        break;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    // XP Bar
    this.grid.writeString(15, 20, "EXP [", "#aaa");
    const barLen = 40;
    const filled = Math.floor((this.xpFill / 100) * barLen);
    for (let i = 0; i < barLen; i++) {
      this.grid.setCell(20 + i, 20, i < filled ? "█" : "░", i < filled ? "#0f0" : "#333");
    }
    this.grid.writeString(60, 20, `] ${Math.floor(this.xpFill)}%`, "#aaa");

    // Level display
    this.grid.writeCentered(2, `── LEVEL ${this.level} ──`, "#fff");

    if (this.phase === "flash" || this.phase === "stats" || this.phase === "idle") {
      // Flash text
      if (this.flashOn || this.phase !== "flash") {
        this.grid.writeCentered(6, "╔═══════════════════╗", "#ff0");
        this.grid.writeCentered(7, "║   L E V E L  U P !  ║", "#ff0");
        this.grid.writeCentered(8, "╚═══════════════════╝", "#ff0");
      }

      // Star ring
      const ringChars = "*+★☆·";
      const r = Math.min(Math.floor(this.ringRadius), 15);
      const cy = 7;
      const cx = 40;
      for (let a = 0; a < 16; a++) {
        const angle = (a / 16) * Math.PI * 2;
        const sx = cx + Math.round(Math.cos(angle) * r * 2);
        const sy = cy + Math.round(Math.sin(angle) * r * 0.5);
        if (sx >= 0 && sx < 80 && sy >= 0 && sy < 24) {
          this.grid.setCell(sx, sy, ringChars[a % ringChars.length], "#ff0");
        }
      }
    }

    // Stats
    if (this.phase === "stats" || this.phase === "idle") {
      for (let i = 0; i < this.stats.length; i++) {
        if (!this.stats[i].shown) continue;
        const s = this.stats[i];
        const y = 11 + i;
        this.grid.writeString(28, y, `${s.label}`, "#aaa");
        this.grid.writeString(34, y, `+${s.value}`, s.color);
        this.grid.writeString(38, y, "▲", s.color);
      }
    }

    this.grid.writeCentered(22, "── ADVENTURE CONTINUES ──", "#555");
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.level = 1;
    this.xpFill = 0;
    this.phase = "xp_fill";
    this.timer = 0;
    this.resetStats();
  }

  dispose(): void {
    this.stats = [];
  }
}
