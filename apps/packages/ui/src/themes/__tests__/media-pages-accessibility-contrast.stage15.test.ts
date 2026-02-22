import { describe, expect, it } from "vitest"
import { contrastRatio } from "../contrast"
import { getBuiltinPresets } from "../presets"

type ContrastRequirement = {
  pair: string
  foreground: keyof ReturnType<typeof getBuiltinPresets>[number]["palette"]["light"]
  background: keyof ReturnType<typeof getBuiltinPresets>[number]["palette"]["light"]
  minimum: number
}

const MEDIA_PAGE_CONTRAST_REQUIREMENTS: ContrastRequirement[] = [
  { pair: "text/bg", foreground: "text", background: "bg", minimum: 4.5 },
  { pair: "text/surface", foreground: "text", background: "surface", minimum: 4.5 },
  {
    pair: "textMuted/surface2",
    foreground: "textMuted",
    background: "surface2",
    minimum: 4.5,
  },
  {
    pair: "textSubtle/surface2",
    foreground: "textSubtle",
    background: "surface2",
    minimum: 3,
  },
  { pair: "focus/surface", foreground: "focus", background: "surface", minimum: 3 },
  { pair: "focus/bg", foreground: "focus", background: "bg", minimum: 3 },
]

const DOCUMENTED_MINIMUM_FLOORS: Record<string, number> = {
  "text/bg": 6.5,
  "text/surface": 6.9,
  "textMuted/surface2": 4.5,
  "textSubtle/surface2": 3,
  "focus/surface": 3.1,
  "focus/bg": 3.49,
}

describe("media pages stage 15 contrast coverage", () => {
  const presets = getBuiltinPresets()

  it("meets WCAG contrast thresholds for media-page text and focus token pairings", () => {
    const failures: string[] = []

    for (const preset of presets) {
      for (const [mode, tokens] of Object.entries(preset.palette)) {
        for (const requirement of MEDIA_PAGE_CONTRAST_REQUIREMENTS) {
          const ratio = contrastRatio(
            tokens[requirement.foreground],
            tokens[requirement.background]
          )
          if (ratio < requirement.minimum) {
            failures.push(
              `${preset.id}/${mode} ${requirement.pair}=${ratio.toFixed(
                2
              )} (<${requirement.minimum.toFixed(2)})`
            )
          }
        }
      }
    }

    expect(failures, failures.join(" | ")).toEqual([])
  })

  it("keeps documented minimum contrast floors stable for media pages", () => {
    const minimumByPair = new Map<string, number>()

    for (const requirement of MEDIA_PAGE_CONTRAST_REQUIREMENTS) {
      minimumByPair.set(requirement.pair, Number.POSITIVE_INFINITY)
    }

    for (const preset of presets) {
      for (const tokens of Object.values(preset.palette)) {
        for (const requirement of MEDIA_PAGE_CONTRAST_REQUIREMENTS) {
          const ratio = contrastRatio(
            tokens[requirement.foreground],
            tokens[requirement.background]
          )
          const currentMin = minimumByPair.get(requirement.pair) ?? Number.POSITIVE_INFINITY
          minimumByPair.set(requirement.pair, Math.min(currentMin, ratio))
        }
      }
    }

    const regressions: string[] = []
    for (const [pair, floor] of Object.entries(DOCUMENTED_MINIMUM_FLOORS)) {
      const measured = minimumByPair.get(pair) ?? 0
      if (measured < floor) {
        regressions.push(`${pair}=${measured.toFixed(2)} (<${floor.toFixed(2)})`)
      }
    }

    expect(regressions, regressions.join(" | ")).toEqual([])
  })
})
