// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { LoadingStatus } from "../ActionInfo"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string, options?: Record<string, unknown>) => {
      const template =
        typeof defaultValue === "string" && defaultValue.length > 0
          ? defaultValue
          : key
      if (!options) return template
      return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
        const value = options[token]
        return value == null ? "" : String(value)
      })
    }
  })
}))

describe("LoadingStatus accessibility announcements", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("announces streaming start, progress checkpoints, and completion", () => {
    let progressCallback: (() => void) | null = null
    vi.spyOn(window, "setInterval").mockImplementation((cb: TimerHandler) => {
      progressCallback = cb as () => void
      return 1 as unknown as number
    })
    vi.spyOn(window, "clearInterval").mockImplementation(() => {})

    const { rerender } = render(<LoadingStatus isStreaming />)

    expect(
      screen.getByText("Generating response... started")
    ).toBeInTheDocument()
    expect(progressCallback).not.toBeNull()

    act(() => {
      progressCallback?.()
    })
    expect(
      screen.getByText("Still generating response (checkpoint 1).")
    ).toBeInTheDocument()

    rerender(<LoadingStatus isStreaming={false} isProcessing={false} />)
    expect(screen.getByText("Response complete")).toBeInTheDocument()
  })
})
