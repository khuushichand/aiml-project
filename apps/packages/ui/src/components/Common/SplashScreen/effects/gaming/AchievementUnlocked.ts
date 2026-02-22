import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Achievement {
  title: string;
  desc: string;
  points: number;
}

export default class AchievementUnlockedEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private slideY = 24;
  private displayTimer = 0;
  private phase: "slide_in" | "display" | "slide_out" | "wait" = "slide_in";
  private achIdx = 0;
  private sparkTimer = 0;
  private sparkOn = true;

  private achievements: Achievement[] = [
    { title: "FIRST STEPS", desc: "Ingested your first media item", points: 10 },
    { title: "BOOKWORM", desc: "Processed 100 documents", points: 50 },
    { title: "KNOWLEDGE SEEKER", desc: "Ran 50 RAG queries", points: 25 },
    { title: "NIGHT OWL", desc: "Used the app past midnight", points: 15 },
    { title: "POLYGLOT", desc: "Transcribed audio in 5 languages", points: 75 },
    { title: "DATA WIZARD", desc: "Created 10 custom embeddings", points: 100 },
  ];

  private trophy = [
    "   ___   ",
    "  |   |  ",
    "  | ★ |  ",
    "  |___|  ",
    "   )_(   ",
    "  /___\\  ",
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.slideY = 24;
    this.phase = "slide_in";
    this.achIdx = 0;
    this.displayTimer = 0;
  }

  update(_elapsed: number, dt: number): void {
    this.sparkTimer += dt;
    if (this.sparkTimer > 200) {
      this.sparkTimer = 0;
      this.sparkOn = !this.sparkOn;
    }

    const ach = this.achievements[this.achIdx];
    switch (this.phase) {
      case "slide_in":
        this.slideY -= dt * 0.012;
        if (this.slideY <= 7) {
          this.slideY = 7;
          this.phase = "display";
          this.displayTimer = 0;
        }
        break;
      case "display":
        this.displayTimer += dt;
        if (this.displayTimer > 2500) {
          this.phase = "slide_out";
        }
        break;
      case "slide_out":
        this.slideY -= dt * 0.015;
        if (this.slideY < -10) {
          this.phase = "wait";
          this.displayTimer = 0;
        }
        break;
      case "wait":
        this.displayTimer += dt;
        if (this.displayTimer > 600) {
          this.achIdx = (this.achIdx + 1) % this.achievements.length;
          this.slideY = 24;
          this.phase = "slide_in";
        }
        break;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    const ach = this.achievements[this.achIdx];
    const by = Math.round(this.slideY);

    // Box border
    const boxTop = by - 1;
    const boxBot = by + 8;
    if (boxTop >= 0 && boxTop < 24) {
      this.grid.writeString(15, boxTop, "╔══════════════════════════════════════════════════╗", "#da0");
    }
    for (let r = by; r < by + 8 && r < 24; r++) {
      if (r >= 0) {
        this.grid.setCell(15, r, "║", "#da0");
        this.grid.setCell(65, r, "║", "#da0");
      }
    }
    if (boxBot >= 0 && boxBot < 24) {
      this.grid.writeString(15, boxBot, "╚══════════════════════════════════════════════════╝", "#da0");
    }

    // Trophy
    for (let i = 0; i < this.trophy.length; i++) {
      const ty = by + 1 + i;
      if (ty >= 0 && ty < 24) {
        this.grid.writeString(18, ty, this.trophy[i], "#ff0");
      }
    }

    // Text content
    if (by + 1 >= 0 && by + 1 < 24) {
      const sparkChar = this.sparkOn ? "★" : "☆";
      this.grid.writeString(30, by + 1, `${sparkChar} ACHIEVEMENT UNLOCKED ${sparkChar}`, "#fff");
    }
    if (by + 3 >= 0 && by + 3 < 24) {
      this.grid.writeString(30, by + 3, ach.title, "#ff0");
    }
    if (by + 5 >= 0 && by + 5 < 24) {
      this.grid.writeString(30, by + 5, ach.desc, "#aaa");
    }
    if (by + 7 >= 0 && by + 7 < 24) {
      this.grid.writeString(30, by + 7, `${ach.points}G`, "#0f0");
    }

    this.grid.writeCentered(1, "GAMERSCORE", "#555");
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.slideY = 24;
    this.phase = "slide_in";
    this.achIdx = 0;
  }

  dispose(): void {}
}
