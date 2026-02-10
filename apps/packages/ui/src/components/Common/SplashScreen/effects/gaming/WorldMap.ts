import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Marker {
  x: number;
  y: number;
  label: string;
  color: string;
}

export default class WorldMapEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private blinkTimer = 0;
  private blinkOn = true;
  private routeProgress = 0;
  private markers: Marker[] = [];
  private routeOrder: number[] = [];

  private mapLines = [
    "                         .  ~~~~                        ",
    "        ___,__    .  ~~~~  ~~~                          ",
    "       /      \\~~~~  ATLANTIC  ~~    ,--.              ",
    "      |  NA   |  ~~~~  ~~~  ~~~~   / EU  \\   ___      ",
    "      |       |   ~~~~   ~~~~     |      |  / AS \\    ",
    "       \\_____/      ~~~~         \\_,--._/ |      |   ",
    "          |           ~~~~   ___    |  ME  | \\____/    ",
    "          |            ~~   / AF\\   |_____|            ",
    "                            |    |                      ",
    "                            \\___/    INDIAN            ",
    "                                      ~~~~              ",
    "                 PACIFIC               ~~~~    ___      ",
    "                  ~~~~                  ~~    / AU\\    ",
    "                   ~~~~                       \\___/    ",
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.routeProgress = 0;
    this.blinkTimer = 0;
    this.blinkOn = true;
    this.markers = [
      { x: 15, y: 7, label: "NYC", color: "#f55" },
      { x: 38, y: 6, label: "LON", color: "#5f5" },
      { x: 48, y: 9, label: "DXB", color: "#ff5" },
      { x: 58, y: 7, label: "DEL", color: "#f5f" },
      { x: 65, y: 8, label: "TYO", color: "#5ff" },
      { x: 55, y: 15, label: "SYD", color: "#fa5" },
    ];
    this.routeOrder = [0, 1, 2, 3, 4, 5];
  }

  update(elapsed: number, dt: number): void {
    this.blinkTimer += dt;
    if (this.blinkTimer > 400) {
      this.blinkTimer = 0;
      this.blinkOn = !this.blinkOn;
    }
    this.routeProgress += dt * 0.0004;
    if (this.routeProgress > this.markers.length) {
      this.routeProgress = 0;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);
    this.grid.writeCentered(0, "═══════ WORLD MAP ═══════", "#0af");
    for (let i = 0; i < this.mapLines.length; i++) {
      this.grid.writeString(10, 2 + i, this.mapLines[i], "#145");
    }
    // Draw route
    const segments = Math.floor(this.routeProgress);
    for (let s = 0; s < segments && s < this.routeOrder.length - 1; s++) {
      const a = this.markers[this.routeOrder[s]];
      const b = this.markers[this.routeOrder[s + 1]];
      const steps = Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y));
      for (let t = 0; t < steps; t += 2) {
        const px = Math.round(a.x + (b.x - a.x) * (t / steps));
        const py = Math.round(a.y + (b.y - a.y) * (t / steps));
        if (px >= 0 && px < 80 && py >= 0 && py < 24) {
          this.grid.setCell(px, py, "·", "#555");
        }
      }
    }
    // Draw markers
    for (let i = 0; i < this.markers.length; i++) {
      const m = this.markers[i];
      const active = i <= segments;
      if (active && this.blinkOn) {
        this.grid.setCell(m.x, m.y, "◉", m.color);
      } else {
        this.grid.setCell(m.x, m.y, "○", "#444");
      }
      this.grid.writeString(m.x - 1, m.y + 1, m.label, active ? m.color : "#444");
    }
    this.grid.writeCentered(19, "── TRACKING GLOBAL KNOWLEDGE ──", "#088");
    this.grid.writeCentered(21, `Destinations visited: ${segments}/${this.markers.length}`, "#aaa");
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.routeProgress = 0;
    this.blinkTimer = 0;
  }

  dispose(): void {
    this.markers = [];
  }
}
