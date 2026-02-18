import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  CharacterGalleryCard,
  getAvatarFallbackTokens,
  hashNameToHue
} from "../CharacterGalleryCard"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

describe("CharacterGalleryCard", () => {
  const parseHsl = (value: string) => {
    const match = value.match(/hsl\(([-\d.]+)\s+([-\d.]+)%\s+([-\d.]+)%\)/)
    if (!match) return null
    return {
      h: Number(match[1]),
      s: Number(match[2]),
      l: Number(match[3])
    }
  }

  const hslToRgb = ({ h, s, l }: { h: number; s: number; l: number }) => {
    const sat = s / 100
    const light = l / 100
    const chroma = (1 - Math.abs(2 * light - 1)) * sat
    const x = chroma * (1 - Math.abs((h / 60) % 2 - 1))
    const m = light - chroma / 2
    let red = 0
    let green = 0
    let blue = 0

    if (h < 60) {
      red = chroma
      green = x
    } else if (h < 120) {
      red = x
      green = chroma
    } else if (h < 180) {
      green = chroma
      blue = x
    } else if (h < 240) {
      green = x
      blue = chroma
    } else if (h < 300) {
      red = x
      blue = chroma
    } else {
      red = chroma
      blue = x
    }

    return { r: red + m, g: green + m, b: blue + m }
  }

  const contrastRatio = (a: string, b: string) => {
    const colorA = parseHsl(a)
    const colorB = parseHsl(b)
    if (!colorA || !colorB) return 0

    const toLuminance = (rgb: { r: number; g: number; b: number }) => {
      const linearize = (value: number) =>
        value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
      const r = linearize(rgb.r)
      const g = linearize(rgb.g)
      const b = linearize(rgb.b)
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }

    const luminanceA = toLuminance(hslToRgb(colorA))
    const luminanceB = toLuminance(hslToRgb(colorB))
    const bright = Math.max(luminanceA, luminanceB)
    const dark = Math.min(luminanceA, luminanceB)
    return (bright + 0.05) / (dark + 0.05)
  }

  it("renders description and up to three tags for scanning", () => {
    render(
      <CharacterGalleryCard
        character={{
          id: "char-1",
          name: "Writer Coach",
          description: "Helps improve draft structure and tone.",
          tags: ["writing", "coach", "editing", "extra"]
        }}
        onClick={vi.fn()}
        conversationCount={12}
      />
    )

    expect(screen.getByText("Writer Coach")).toBeInTheDocument()
    expect(screen.getByText("Helps improve draft structure and tone.")).toBeInTheDocument()
    expect(screen.getByText("writing")).toBeInTheDocument()
    expect(screen.getByText("coach")).toBeInTheDocument()
    expect(screen.getByText("editing")).toBeInTheDocument()
    expect(screen.queryByText("extra")).not.toBeInTheDocument()
  })

  it("uses deterministic fallback color and monogram when avatar is absent", () => {
    const tokensA = getAvatarFallbackTokens("Writer Coach")
    const tokensB = getAvatarFallbackTokens("Writer Coach")
    const tokensC = getAvatarFallbackTokens("Interview Trainer")

    expect(hashNameToHue("writer coach")).toBe(hashNameToHue("writer coach"))
    expect(tokensA.backgroundColor).toBe(tokensB.backgroundColor)
    expect(tokensA.color).toBe(tokensB.color)
    expect(tokensA.initial).toBe("W")
    expect(tokensA.backgroundColor).not.toBe(tokensC.backgroundColor)
    expect(contrastRatio(tokensA.backgroundColor, tokensA.color)).toBeGreaterThanOrEqual(4.5)

    render(
      <CharacterGalleryCard
        character={{ id: "no-avatar-1", name: "Writer Coach" }}
        onClick={vi.fn()}
      />
    )

    expect(screen.getByText("W")).toBeInTheDocument()
    expect(screen.getByTestId("character-gallery-fallback-avatar")).toHaveStyle({
      backgroundColor: tokensA.backgroundColor,
      color: tokensA.color
    })
  })

  it("hides description and tags in compact density mode", () => {
    render(
      <CharacterGalleryCard
        character={{
          id: "char-compact",
          name: "Compact Card",
          description: "Hidden in compact mode",
          tags: ["one", "two", "three"]
        }}
        density="compact"
        onClick={vi.fn()}
      />
    )

    expect(screen.getByText("Compact Card")).toBeInTheDocument()
    expect(screen.queryByText("Hidden in compact mode")).not.toBeInTheDocument()
    expect(screen.queryByText("one")).not.toBeInTheDocument()
  })

  it("invokes onClick when the card is activated", async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <CharacterGalleryCard
        character={{
          id: "char-2",
          name: "Tutor"
        }}
        onClick={onClick}
      />
    )

    await user.click(screen.getByRole("button", { name: /Click to preview/i }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("includes reduced-motion transition guard on the card container", () => {
    render(
      <CharacterGalleryCard
        character={{
          id: "char-motion",
          name: "Reduced Motion"
        }}
        onClick={vi.fn()}
      />
    )

    const cardButton = screen.getByRole("button", {
      name: /Click to preview/i
    })
    expect(cardButton.className).toContain("motion-reduce:transition-none")
  })
})
