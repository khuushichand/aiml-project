import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface CharPortrait {
  face: string[];
  name: string;
  color: string;
}

export default class CharacterSelectEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private cursorIdx = 0;
  private moveTimer = 0;
  private blinkTimer = 0;
  private blinkOn = true;

  private chars: CharPortrait[] = [
    { face: [" .-. ", "(o.o)", " |=| "], name: "WIZARD", color: "#a0f" },
    { face: [" /-\\ ", "(>.<)", " /|\\ "], name: "KNIGHT", color: "#fa0" },
    { face: [" ___ ", "(@_@)", " /_\\ "], name: "ROGUE", color: "#0f0" },
    { face: [" {o} ", "(^_^)", " )_( "], name: "CLERIC", color: "#0af" },
    { face: [" *** ", "(O_O)", " |X| "], name: "BARBAR", color: "#f00" },
    { face: [" ~~~ ", "(-.o)", " /~\\ "], name: "RANGER", color: "#5a0" },
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.cursorIdx = 0;
    this.moveTimer = 0;
    this.blinkTimer = 0;
    this.blinkOn = true;
  }

  update(_elapsed: number, dt: number): void {
    this.moveTimer += dt;
    if (this.moveTimer > 800) {
      this.moveTimer = 0;
      this.cursorIdx = (this.cursorIdx + 1) % this.chars.length;
    }
    this.blinkTimer += dt;
    if (this.blinkTimer > 300) {
      this.blinkTimer = 0;
      this.blinkOn = !this.blinkOn;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);
    this.grid.writeCentered(1, "╔══════ CHARACTER SELECT ══════╗", "#ff0");
    this.grid.writeCentered(2, "║   CHOOSE YOUR HERO           ║", "#ff0");
    this.grid.writeCentered(3, "╚══════════════════════════════╝", "#ff0");

    for (let i = 0; i < 6; i++) {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const bx = 12 + col * 20;
      const by = 6 + row * 8;
      const ch = this.chars[i];
      const selected = i === this.cursorIdx;
      const borderColor = selected ? "#fff" : "#333";

      // Draw border
      this.grid.writeString(bx, by, "┌─────────┐", borderColor);
      for (let r = 1; r <= 4; r++) {
        this.grid.setCell(bx, by + r, "│", borderColor);
        this.grid.setCell(bx + 10, by + r, "│", borderColor);
      }
      this.grid.writeString(bx, by + 5, "└─────────┘", borderColor);

      // Draw face
      for (let f = 0; f < ch.face.length; f++) {
        this.grid.writeString(bx + 3, by + 1 + f, ch.face[f], selected ? ch.color : "#555");
      }

      // Draw name
      const nameX = bx + Math.floor((11 - ch.name.length) / 2);
      this.grid.writeString(nameX, by + 4, ch.name, selected ? "#fff" : "#666");

      // Selection arrow
      if (selected && this.blinkOn) {
        this.grid.setCell(bx + 4, by + 5, "▲", "#ff0");
      }
    }

    const sel = this.chars[this.cursorIdx];
    this.grid.writeCentered(22, `> ${sel.name} SELECTED <`, sel.color);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.cursorIdx = 0;
    this.moveTimer = 0;
  }

  dispose(): void {}
}
