import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

export default class VersusScreenEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private slideTimer = 0;
  private leftX = -20;
  private rightX = 100;
  private vsScale = 0;
  private lightningTimer = 0;
  private lightningOn = false;
  private matchIdx = 0;
  private holdTimer = 0;
  private phase: "slide" | "vs" | "hold" = "slide";

  private fighters = [
    { name: "SHADOW", title: "The Silent Blade" },
    { name: "BLAZE", title: "Inferno Master" },
    { name: "FROST", title: "Ice Queen" },
    { name: "THUNDER", title: "Storm Bringer" },
    { name: "VENOM", title: "Toxic Assassin" },
    { name: "NOVA", title: "Star Crusher" },
  ];

  private leftSilhouette = [
    "  ╔═╗  ",
    "  ║O║  ",
    " ╔╩═╩╗ ",
    " ║   ║ ",
    " ╠═══╣ ",
    "  ║ ║  ",
    " ═╝ ╚═ ",
  ];

  private rightSilhouette = [
    "  ╔═╗  ",
    "  ║X║  ",
    " ╔╩═╩╗ ",
    " ║   ║ ",
    " ╠═══╣ ",
    "  ║ ║  ",
    " ═╝ ╚═ ",
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.matchIdx = 0;
    this.startSlide();
  }

  private startSlide(): void {
    this.leftX = -20;
    this.rightX = 100;
    this.vsScale = 0;
    this.phase = "slide";
    this.slideTimer = 0;
    this.holdTimer = 0;
  }

  update(_elapsed: number, dt: number): void {
    this.lightningTimer += dt;
    if (this.lightningTimer > 100) {
      this.lightningTimer = 0;
      this.lightningOn = Math.random() > 0.5;
    }

    switch (this.phase) {
      case "slide":
        this.slideTimer += dt;
        this.leftX += dt * 0.025;
        this.rightX -= dt * 0.025;
        if (this.leftX >= 5) {
          this.leftX = 5;
          this.rightX = 55;
          this.phase = "vs";
          this.slideTimer = 0;
        }
        break;
      case "vs":
        this.vsScale += dt * 0.004;
        if (this.vsScale >= 1) {
          this.vsScale = 1;
          this.phase = "hold";
          this.holdTimer = 0;
        }
        break;
      case "hold":
        this.holdTimer += dt;
        if (this.holdTimer > 2500) {
          this.matchIdx = (this.matchIdx + 2) % this.fighters.length;
          this.startSlide();
        }
        break;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    const lf = this.fighters[this.matchIdx % this.fighters.length];
    const rf = this.fighters[(this.matchIdx + 1) % this.fighters.length];

    // Background split - left red, right blue
    for (let y = 0; y < 24; y++) {
      for (let x = 0; x < 40; x++) {
        if (Math.random() < 0.03) this.grid.setCell(x, y, "░", "#300");
      }
      for (let x = 40; x < 80; x++) {
        if (Math.random() < 0.03) this.grid.setCell(x, y, "░", "#003");
      }
    }

    // Divider
    for (let y = 0; y < 24; y++) {
      this.grid.setCell(39, y, "│", this.lightningOn ? "#ff0" : "#555");
      this.grid.setCell(40, y, "│", this.lightningOn ? "#ff0" : "#555");
    }

    // Left fighter
    const lx = Math.round(this.leftX);
    for (let i = 0; i < this.leftSilhouette.length; i++) {
      const y = 6 + i;
      if (y < 24) this.grid.writeString(Math.max(0, lx), y, this.leftSilhouette[i], "#f44");
    }
    if (lx >= 0) {
      this.grid.writeString(Math.max(0, lx), 14, lf.name, "#f88");
      this.grid.writeString(Math.max(0, lx), 15, lf.title, "#a55");
    }

    // Right fighter
    const rx = Math.round(this.rightX);
    for (let i = 0; i < this.rightSilhouette.length; i++) {
      const y = 6 + i;
      if (y < 24 && rx < 80) this.grid.writeString(Math.min(rx, 72), y, this.rightSilhouette[i], "#44f");
    }
    if (rx < 80) {
      this.grid.writeString(Math.min(rx, 72), 14, rf.name, "#88f");
      this.grid.writeString(Math.min(rx, 72), 15, rf.title, "#55a");
    }

    // VS text
    if (this.vsScale > 0) {
      const vsLines = [
        "██╗   ██╗███████╗",
        "██║   ██║██╔════╝",
        "██║   ██║███████╗",
        "╚██╗ ██╔╝╚════██║",
        " ╚████╔╝ ███████║",
        "  ╚═══╝  ╚══════╝",
      ];
      const show = Math.floor(this.vsScale * vsLines.length);
      for (let i = 0; i < show; i++) {
        this.grid.writeCentered(1 + i, vsLines[i], "#ff0");
      }
    }

    this.grid.writeCentered(22, "ROUND 1 ── FIGHT!", "#fff");
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.matchIdx = 0;
    this.startSlide();
  }

  dispose(): void {}
}
