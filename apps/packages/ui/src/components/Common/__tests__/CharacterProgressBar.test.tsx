import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { CharacterProgressBar } from "../CharacterProgressBar"

describe("CharacterProgressBar", () => {
  it("renders count and max text", () => {
    render(<CharacterProgressBar count={1240} max={8000} />)
    expect(screen.getByText("1,240 / 8,000 chars")).toBeInTheDocument()
  })

  it("shows green color when under warnAt", () => {
    render(<CharacterProgressBar count={500} max={8000} />)
    const fill = screen.getByRole("progressbar").querySelector("[data-color]")
    expect(fill).toHaveAttribute("data-color", "green")
    expect(fill).toHaveClass("bg-green-500")
  })

  it("shows amber color between warnAt and dangerAt", () => {
    render(<CharacterProgressBar count={3000} max={8000} />)
    const fill = screen.getByRole("progressbar").querySelector("[data-color]")
    expect(fill).toHaveAttribute("data-color", "amber")
    expect(fill).toHaveClass("bg-amber-500")
  })

  it("shows red color over dangerAt", () => {
    render(<CharacterProgressBar count={7000} max={8000} />)
    const fill = screen.getByRole("progressbar").querySelector("[data-color]")
    expect(fill).toHaveAttribute("data-color", "red")
    expect(fill).toHaveClass("bg-red-500")
  })

  it("has correct ARIA attributes", () => {
    render(<CharacterProgressBar count={1240} max={8000} />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "1240")
    expect(bar).toHaveAttribute("aria-valuemax", "8000")
    expect(bar).toHaveAttribute("aria-label", "Character count")
  })
})
