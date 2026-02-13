import { describe, expect, it } from "vitest"
import { getBuiltinPresets } from "../presets"
import {
  auditThemeTextContrast,
  contrastRatio,
  meetsNonTextContrast,
  meetsTextContrast,
} from "../contrast"

describe("theme contrast baseline", () => {
  const presets = getBuiltinPresets()
  const coreThemeIds = new Set(["default", "high-contrast"])

  it("enforces AA text contrast on primary reading surfaces for all built-in themes", () => {
    const failures: string[] = []

    for (const preset of presets.filter((item) => coreThemeIds.has(item.id))) {
      for (const [mode, tokens] of Object.entries(preset.palette)) {
        const pairFailures = auditThemeTextContrast(tokens).filter((item) => {
          if (item.pair.startsWith("textSubtle/")) {
            return item.ratio < 3
          }
          return !item.passesAA
        })
        if (pairFailures.length > 0) {
          failures.push(
            `${preset.id}/${mode}: ${pairFailures
              .map((item) => `${item.pair}=${item.ratio.toFixed(2)}`)
              .join(", ")}`
          )
        }
      }
    }

    expect(failures, failures.join(" | ")).toEqual([])
  })

  it("keeps focus indicator at 3:1 non-text contrast minimum on main surfaces", () => {
    const failures: string[] = []

    for (const preset of presets.filter((item) => coreThemeIds.has(item.id))) {
      for (const [mode, tokens] of Object.entries(preset.palette)) {
        const focusOnBg = contrastRatio(tokens.focus, tokens.bg)
        const focusOnSurface = contrastRatio(tokens.focus, tokens.surface)
        if (!meetsNonTextContrast(tokens.focus, tokens.bg)) {
          failures.push(`${preset.id}/${mode}: focus/bg=${focusOnBg.toFixed(2)}`)
        }
        if (!meetsNonTextContrast(tokens.focus, tokens.surface)) {
          failures.push(`${preset.id}/${mode}: focus/surface=${focusOnSurface.toFixed(2)}`)
        }
      }
    }

    expect(failures, failures.join(" | ")).toEqual([])
  })

  it("provides a deterministic contrast helper baseline for regression safety", () => {
    expect(meetsTextContrast("0 0 0", "255 255 255")).toBe(true)
    expect(meetsTextContrast("120 120 120", "255 255 255")).toBe(false)
    expect(contrastRatio("0 0 0", "255 255 255")).toBeCloseTo(21, 5)
  })
})
