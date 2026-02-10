import { describe, expect, it, vi } from "vitest"

import TerminalBoot from "../effects/tech/TerminalBoot"
import TextExplosion from "../effects/classic/TextExplosion"
import QuantumParticles from "../effects/environmental/QuantumParticles"
import SpyVsSpy from "../effects/tech/SpyVsSpy"

function createMockCtx(width = 800, height = 480): CanvasRenderingContext2D {
  return {
    canvas: { width, height },
    fillStyle: "#000",
    font: "",
    textBaseline: "top",
    fillRect: vi.fn(),
    fillText: vi.fn(),
    createRadialGradient: vi.fn(() => ({
      addColorStop: vi.fn(),
    })),
  } as unknown as CanvasRenderingContext2D
}

describe("Splash Stage 2 effect fixes", () => {
  it("TerminalBoot accepts object-based boot_sequence configs without crashing", () => {
    const effect = new TerminalBoot()
    const ctx = createMockCtx()

    const bootSequence = [
      { text: "Booting TLDW...", typeSpeed: 0.02, pauseAfter: 100, style: "#ffffff" },
      { text: "Loading services [OK]", typeSpeed: 0.01, pauseAfter: 50, style: "bold green" },
      { text: "Ready", delayBefore: 0.1, style: "cyan" },
    ]

    expect(() => effect.init(ctx, 800, 480, { boot_sequence: bootSequence })).not.toThrow()
    expect(() => effect.update(0, 16)).not.toThrow()
    expect(() => effect.update(2000, 16)).not.toThrow()
    expect(() => effect.render(ctx)).not.toThrow()
  })

  it("TextExplosion forwards dt in milliseconds to ParticlePool.update", () => {
    const effect = new TextExplosion()
    const ctx = createMockCtx()
    effect.init(ctx, 800, 480, { text: "TEST" })

    const updateSpy = vi.spyOn((effect as any).pool, "update")
    effect.update(100, 1000)

    expect(updateSpy).toHaveBeenCalledWith(1000)
  })

  it("QuantumParticles respawns when alive particle count is below threshold", () => {
    const effect = new QuantumParticles()
    const ctx = createMockCtx()
    effect.init(ctx, 800, 480)

    const spawnSpy = vi.spyOn(effect as any, "spawnOrbital")
    const pool = (effect as any).pool
    pool.alive = vi.fn(() => [{ life: 1 }])
    pool.update = vi.fn()
    pool.toGrid = vi.fn()

    effect.update(1200, 16)

    expect(spawnSpy).toHaveBeenCalled()
  })

  it("SpyVsSpy render path uses CharGrid.getChar and remains stable", () => {
    const effect = new SpyVsSpy()
    const ctx = createMockCtx()
    effect.init(ctx, 800, 480)
    effect.update(500, 16)

    const grid = (effect as any).grid
    const getCharSpy = vi.spyOn(grid, "getChar")

    expect(() => effect.render(ctx)).not.toThrow()
    expect(getCharSpy).toHaveBeenCalled()
  })
})

