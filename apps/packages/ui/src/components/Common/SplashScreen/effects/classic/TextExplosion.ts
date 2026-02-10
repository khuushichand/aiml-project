import { CharGrid } from "../../engine/CharGrid";
import { ParticlePool } from "../../engine/ParticlePool";
import type { SplashEffect } from "../../types";

export default class TextExplosionEffect implements SplashEffect {
  private grid!: CharGrid;
  private pool!: ParticlePool;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private text = "tldw";
  private mode: "explode" | "implode" = "explode";
  private spawned = false;
  private implodeTargets: Array<{ x: number; y: number; ch: string }> = [];
  private duration = 2000;
  private particleSpread = 20;

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.pool = new ParticlePool();
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.text = (config?.text as string) ?? (config?.text_to_animate as string) ?? "tldw";
    this.mode = (config?.mode as "explode" | "implode")
      ?? (config?.effect_direction as "explode" | "implode")
      ?? "explode";
    this.duration = (config?.duration as number) ?? 2000;
    this.particleSpread = (config?.particle_spread as number) ?? 20;
    this.spawned = false;
    this.implodeTargets = [];

    const cx = Math.floor((80 - this.text.length) / 2);
    const cy = 12;
    for (let i = 0; i < this.text.length; i++) {
      this.implodeTargets.push({ x: cx + i, y: cy, ch: this.text[i] });
    }
  }

  update(elapsed: number, dt: number): void {
    this.grid.clear();

    if (!this.spawned) {
      this.spawned = true;

      for (const target of this.implodeTargets) {
        if (this.mode === "explode") {
          // Start at text position, fly outward
          const angle = Math.random() * Math.PI * 2;
          const spreadScale = Math.max(0.5, this.particleSpread / 20);
          const speed = (8 + Math.random() * 20) * spreadScale;
          this.pool.spawn({
            x: target.x,
            y: target.y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            char: target.ch,
            color: "rgb(255,200,50)",
            life: this.duration / 1000,
          });
        } else {
          // Start at random positions, converge to text position
          const spreadRadius = Math.max(5, this.particleSpread * 0.6);
          const angle = Math.random() * Math.PI * 2;
          const radius = Math.random() * spreadRadius;
          const sx = 40 + Math.cos(angle) * radius;
          const sy = 12 + Math.sin(angle) * radius * 0.5;
          const pull = Math.max(1, this.particleSpread / 20);
          this.pool.spawn({
            x: sx,
            y: sy,
            vx: (target.x - sx) * 1.5 * pull,
            vy: (target.y - sy) * 1.5 * pull,
            char: target.ch,
            color: "rgb(100,200,255)",
            life: this.duration / 1000,
          });
        }
      }
    }

    this.pool.update(dt);
    this.pool.toGrid(this.grid);

    // If implode mode and near end, show final text solidly
    if (this.mode === "implode" && elapsed > this.duration * 0.7) {
      for (const t of this.implodeTargets) {
        this.grid.setCell(t.x, t.y, t.ch, "rgb(255,255,255)");
      }
    }

    // Explosion trail sparkles
    if (this.mode === "explode" && elapsed < this.duration * 0.5) {
      for (let s = 0; s < 3; s++) {
        const sx = Math.floor(Math.random() * 80);
        const sy = Math.floor(Math.random() * 24);
        this.grid.setCell(sx, sy, "*", "rgb(255,255,100)");
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.spawned = false;
    this.pool.clear();
  }

  dispose(): void {
    this.pool.clear();
    this.implodeTargets = [];
  }
}
