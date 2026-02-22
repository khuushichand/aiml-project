import { describe, expect, it } from "vitest"

import { SPLASH_CARDS } from "../../../../data/splash-cards"
import Starfield from "../effects/environmental/Starfield"
import AsciiMorph from "../effects/classic/AsciiMorph"
import TextExplosion from "../effects/classic/TextExplosion"
import Spotlight from "../effects/classic/Spotlight"
import SoundBars from "../effects/gaming/SoundBars"
import Raindrops from "../effects/environmental/Raindrops"
import OldFilm from "../effects/classic/OldFilm"
import PixelZoom from "../effects/classic/PixelZoom"
import Glitch from "../effects/classic/Glitch"
import GlitchReveal from "../effects/classic/GlitchReveal"

function createMockCtx(width = 800, height = 480): CanvasRenderingContext2D {
  return {
    canvas: { width, height },
    fillStyle: "#000",
    font: "",
    textBaseline: "top",
    fillRect: () => undefined,
    fillText: () => undefined,
    createRadialGradient: () => ({
      addColorStop: () => undefined,
    }),
  } as unknown as CanvasRenderingContext2D
}

const CONSUMED_EFFECT_CONFIG_KEYS: Record<string, Set<string>> = {
  glitch: new Set(["glitch_chars"]),
  pulse: new Set(["color"]),
  blink: new Set(["blink_targets"]),
  loading_bar: new Set(["fill_char", "text_above"]),
  starfield: new Set(["num_stars", "warp_factor"]),
  terminal_boot: new Set(["boot_sequence"]),
  glitch_reveal: new Set(["glitch_chars", "start_intensity"]),
  ascii_morph: new Set(["start_art_name", "end_art_name"]),
  scrolling_credits: new Set(["credits_list"]),
  spotlight: new Set(["spotlight_radius", "path_type"]),
  sound_bars: new Set(["num_bars"]),
  raindrops: new Set(["spawn_rate", "max_concurrent_ripples"]),
  pixel_zoom: new Set(["max_pixel_size"]),
  text_explosion: new Set(["text_to_animate", "effect_direction", "particle_spread"]),
  old_film: new Set(["frames_art_names", "shake_intensity", "grain_density"]),
}

const INTENTIONALLY_IGNORED_EFFECT_CONFIG_KEYS: Record<string, Record<string, string>> = {}

describe("Splash Stage 3 config fidelity", () => {
  it("Starfield consumes num_stars and warp_factor", () => {
    const effect = new Starfield()
    effect.init(createMockCtx(), 800, 480, { num_stars: 123, warp_factor: 0.4 })
    expect((effect as any).stars.length).toBe(123)
    expect((effect as any).speed).not.toBe(0.015)
  })

  it("AsciiMorph supports art-name based configs", () => {
    const effect = new AsciiMorph()
    effect.init(createMockCtx(), 800, 480, {
      start_art_name: "loading_bar_frame",
      end_art_name: "morph_art_end",
    })
    expect((effect as any).morphCells.length).toBeGreaterThan(0)
  })

  it("TextExplosion consumes text_to_animate, effect_direction, and particle_spread", () => {
    const effect = new TextExplosion()
    effect.init(createMockCtx(), 800, 480, {
      text_to_animate: "HELLO",
      effect_direction: "implode",
      particle_spread: 60,
    })
    expect((effect as any).text).toBe("HELLO")
    expect((effect as any).mode).toBe("implode")
    expect((effect as any).particleSpread).toBe(60)
  })

  it("Spotlight consumes spotlight_radius and path_type", () => {
    const effect = new Spotlight()
    effect.init(createMockCtx(), 800, 480, {
      spotlight_radius: 9,
      path_type: "circle",
    })
    expect((effect as any).radius).toBe(9)
    expect((effect as any).pathType).toBe("circle")
  })

  it("SoundBars consumes num_bars", () => {
    const effect = new SoundBars()
    effect.init(createMockCtx(), 800, 480, { num_bars: 25 })
    expect((effect as any).barCount).toBe(25)
    expect((effect as any).barHeights.length).toBe(25)
  })

  it("Raindrops consumes spawn_rate and max_concurrent_ripples", () => {
    const effect = new Raindrops()
    effect.init(createMockCtx(), 800, 480, {
      spawn_rate: 3.5,
      max_concurrent_ripples: 7,
    })
    expect((effect as any).spawnRatePerSec).toBe(3.5)
    expect((effect as any).maxConcurrentRipples).toBe(7)
  })

  it("OldFilm consumes frames_art_names, shake_intensity, and grain_density", () => {
    const effect = new OldFilm()
    effect.init(createMockCtx(), 800, 480, {
      frames_art_names: ["film_generic_frame"],
      shake_intensity: 2,
      grain_density: 0.2,
    })
    expect((effect as any).contentLines.join("\n")).toContain("TLDW PRESENTS")
    expect((effect as any).shakeIntensity).toBe(2)
    expect((effect as any).grainDensity).toBe(0.2)
  })

  it("PixelZoom consumes max_pixel_size", () => {
    const effect = new PixelZoom()
    effect.init(createMockCtx(), 800, 480, { max_pixel_size: 12 })
    expect((effect as any).maxPixelSize).toBe(12)
  })

  it("Glitch consumes glitch_chars", () => {
    const effect = new Glitch()
    effect.init(createMockCtx(), 800, 480, { glitch_chars: "XYZ" })
    expect((effect as any).glitchChars).toBe("XYZ")
  })

  it("GlitchReveal consumes glitch_chars", () => {
    const effect = new GlitchReveal()
    effect.init(createMockCtx(), 800, 480, { glitch_chars: "XYZ", start_intensity: 0.8 })
    expect((effect as any).glitchChars).toBe("XYZ")
  })

  it("every splash card effectConfig key is consumed or explicitly documented as ignored", () => {
    for (const card of SPLASH_CARDS) {
      if (!card.effectConfig) continue
      const effectKey = card.effect ?? "__static__"
      const consumedKeys = CONSUMED_EFFECT_CONFIG_KEYS[effectKey] ?? new Set<string>()
      const ignoredKeys = INTENTIONALLY_IGNORED_EFFECT_CONFIG_KEYS[effectKey] ?? {}

      for (const key of Object.keys(card.effectConfig)) {
        const isConsumed = consumedKeys.has(key)
        const ignoreReason = ignoredKeys[key]
        const isIgnoredWithReason = typeof ignoreReason === "string" && ignoreReason.trim().length > 0
        expect(
          isConsumed || isIgnoredWithReason,
          `Unmapped effectConfig key "${key}" for effect "${card.effect}" (card "${card.name}")`
        ).toBe(true)
      }
    }
  })
})
