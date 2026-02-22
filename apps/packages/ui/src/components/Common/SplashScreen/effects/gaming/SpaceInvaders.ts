import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Bullet {
  x: number;
  y: number;
  dir: number; // -1 up, +1 down
}

export default class SpaceInvadersEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private aliens: { x: number; y: number; char: string; color: string; alive: boolean }[] = [];
  private alienDir = 1;
  private alienMoveTimer = 0;
  private playerX = 40;
  private playerDir = 1;
  private bullets: Bullet[] = [];
  private shootTimer = 0;
  private score = 0;
  private moveSpeed = 300;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.score = 0;
    this.spawnAliens();
    this.playerX = 40;
    this.bullets = [];
    this.alienDir = 1;
    this.moveSpeed = 300;
  }

  private spawnAliens(): void {
    this.aliens = [];
    const chars = ["W", "M", "Ω", "Ψ", "Ж"];
    const colors = ["#f00", "#f80", "#ff0", "#0f0", "#0ff"];
    for (let row = 0; row < 5; row++) {
      for (let col = 0; col < 11; col++) {
        this.aliens.push({
          x: 10 + col * 5,
          y: 3 + row * 2,
          char: chars[row],
          color: colors[row],
          alive: true,
        });
      }
    }
  }

  update(_elapsed: number, dt: number): void {
    // Move aliens
    this.alienMoveTimer += dt;
    if (this.alienMoveTimer > this.moveSpeed) {
      this.alienMoveTimer = 0;
      let hitEdge = false;
      for (const a of this.aliens) {
        if (!a.alive) continue;
        if ((a.x + this.alienDir >= 78) || (a.x + this.alienDir <= 1)) {
          hitEdge = true;
          break;
        }
      }
      if (hitEdge) {
        this.alienDir *= -1;
        for (const a of this.aliens) {
          if (a.alive) a.y += 1;
        }
        this.moveSpeed = Math.max(80, this.moveSpeed - 10);
      } else {
        for (const a of this.aliens) {
          if (a.alive) a.x += this.alienDir;
        }
      }
    }

    // Move player
    this.playerX += this.playerDir * dt * 0.03;
    if (this.playerX >= 76) { this.playerX = 76; this.playerDir = -1; }
    if (this.playerX <= 3) { this.playerX = 3; this.playerDir = 1; }

    // Shoot
    this.shootTimer += dt;
    if (this.shootTimer > 500) {
      this.shootTimer = 0;
      this.bullets.push({ x: Math.round(this.playerX), y: 20, dir: -1 });
    }

    // Alien shoots randomly
    const liveAliens = this.aliens.filter(a => a.alive);
    if (liveAliens.length > 0 && Math.random() < 0.01) {
      const a = liveAliens[Math.floor(Math.random() * liveAliens.length)];
      this.bullets.push({ x: a.x, y: a.y + 1, dir: 1 });
    }

    // Move bullets
    for (let i = this.bullets.length - 1; i >= 0; i--) {
      this.bullets[i].y += this.bullets[i].dir * dt * 0.02;
      const b = this.bullets[i];
      if (b.y < 0 || b.y > 23) {
        this.bullets.splice(i, 1);
        continue;
      }
      // Hit detection (player bullets vs aliens)
      if (b.dir === -1) {
        for (const a of this.aliens) {
          if (a.alive && Math.abs(a.x - b.x) < 2 && Math.abs(a.y - Math.round(b.y)) < 1) {
            a.alive = false;
            this.bullets.splice(i, 1);
            this.score += 10;
            break;
          }
        }
      }
    }

    // Respawn if all dead
    if (liveAliens.length === 0) {
      this.spawnAliens();
      this.moveSpeed = 300;
    }

    // Respawn if aliens reach bottom
    if (liveAliens.some(a => a.y >= 19)) {
      this.spawnAliens();
      this.moveSpeed = 300;
      this.score = 0;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    this.grid.writeString(2, 0, `SCORE: ${this.score}`, "#fff");
    this.grid.writeCentered(0, "SPACE INVADERS", "#0f0");

    // Aliens
    for (const a of this.aliens) {
      if (a.alive && a.y >= 0 && a.y < 24) {
        this.grid.setCell(a.x, a.y, a.char, a.color);
      }
    }

    // Player
    const px = Math.round(this.playerX);
    this.grid.setCell(px - 1, 21, "/", "#0f0");
    this.grid.setCell(px, 21, "A", "#0f0");
    this.grid.setCell(px + 1, 21, "\\", "#0f0");

    // Bullets
    for (const b of this.bullets) {
      const by = Math.round(b.y);
      if (by >= 0 && by < 24) {
        this.grid.setCell(b.x, by, "|", b.dir === -1 ? "#ff0" : "#f55");
      }
    }

    // Ground
    this.grid.fillRow(22, "─", "#0a0");
    this.grid.writeCentered(23, "◄══ DEFEND EARTH ══►", "#555");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.score = 0;
    this.spawnAliens();
    this.playerX = 40;
    this.bullets = [];
    this.moveSpeed = 300;
  }

  dispose(): void {
    this.aliens = [];
    this.bullets = [];
  }
}
