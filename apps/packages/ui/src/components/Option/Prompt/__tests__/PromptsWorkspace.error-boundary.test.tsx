import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { PromptsWorkspace } from "../PromptsWorkspace"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || ""
      }
      return ""
    }
  })
}))

vi.mock("..", () => ({
  PromptBody: () => {
    throw new Error("prompt body crash")
  }
}))

const suppressExpectedWindowError = (expectedMessage: string): (() => void) => {
  const handler = (event: ErrorEvent) => {
    const message =
      event.error instanceof Error
        ? event.error.message
        : typeof event.message === "string"
          ? event.message
          : ""

    if (message.includes(expectedMessage)) {
      event.preventDefault()
    }
  }

  window.addEventListener("error", handler)
  return () => window.removeEventListener("error", handler)
}

describe("PromptsWorkspace error boundary integration", () => {
  it("renders Prompts page fallback when PromptBody throws", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
    const restoreWindowError = suppressExpectedWindowError("prompt body crash")

    try {
      render(<PromptsWorkspace />)
      expect(await screen.findByTestId("prompts-error-boundary")).toBeInTheDocument()
    } finally {
      restoreWindowError()
      consoleSpy.mockRestore()
    }
  })
})
