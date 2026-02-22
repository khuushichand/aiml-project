import { CharGrid } from "./CharGrid";

/** A single particle used by particle-based effects. */
export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  char: string;
  color: string;
  life: number;
  maxLife: number;
  /** Per-particle extra data effects can stash here. */
  data?: Record<string, unknown>;
}

/**
 * Object-pool for particles. Avoids GC pressure by reusing dead particles.
 * Used by ~25% of effects (fireworks, text explosion, quantum particles, etc.)
 */
export class ParticlePool {
  particles: Particle[] = [];
  private maxParticles: number;

  constructor(maxParticles = 500) {
    this.maxParticles = maxParticles;
  }

  /** Spawn a new particle (or recycle a dead one). */
  spawn(config: Partial<Particle>): Particle {
    // Try to recycle
    let p = this.particles.find((p) => p.life <= 0);
    if (!p) {
      if (this.particles.length >= this.maxParticles) return this.particles[0];
      p = { x: 0, y: 0, vx: 0, vy: 0, char: "*", color: "#fff", life: 1, maxLife: 1 };
      this.particles.push(p);
    }
    Object.assign(p, { x: 0, y: 0, vx: 0, vy: 0, char: "*", color: "#fff", life: 1, maxLife: 1, ...config });
    return p;
  }

  /** Update all living particles: apply velocity, decrement life. */
  update(dt: number): void {
    const dtSec = dt / 1000;
    for (const p of this.particles) {
      if (p.life <= 0) continue;
      p.x += p.vx * dtSec;
      p.y += p.vy * dtSec;
      p.life -= dtSec;
    }
  }

  /** Write living particles into a CharGrid. */
  toGrid(grid: CharGrid): void {
    for (const p of this.particles) {
      if (p.life <= 0) continue;
      const gx = Math.round(p.x);
      const gy = Math.round(p.y);
      grid.setCell(gx, gy, p.char, p.color);
    }
  }

  /** Get all living particles. */
  alive(): Particle[] {
    return this.particles.filter((p) => p.life > 0);
  }

  /** Kill all particles. */
  clear(): void {
    for (const p of this.particles) p.life = 0;
  }
}
