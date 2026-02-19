import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PromptPageErrorBoundary } from "../PromptPageErrorBoundary"

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

describe("PromptPageErrorBoundary", () => {
  it("renders fallback when a child throws and recovers on retry", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
    const restoreWindowError = suppressExpectedWindowError("boom")
    let shouldThrow = true

    const FlakyChild = () => {
      if (shouldThrow) {
        throw new Error("boom")
      }
      return <div data-testid="prompt-boundary-child-ok">ok</div>
    }

    try {
      render(
        <PromptPageErrorBoundary>
          <FlakyChild />
        </PromptPageErrorBoundary>
      )

      expect(await screen.findByTestId("prompts-error-boundary")).toBeInTheDocument()
      shouldThrow = false
      fireEvent.click(screen.getByTestId("prompts-error-retry"))

      await waitFor(() => {
        expect(screen.getByTestId("prompt-boundary-child-ok")).toBeInTheDocument()
      })
    } finally {
      restoreWindowError()
      consoleSpy.mockRestore()
    }
  })

  it("provides reload and route recovery actions", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
    const restoreWindowError = suppressExpectedWindowError("still broken")
    const onReload = vi.fn()
    const onNavigateToChat = vi.fn()

    const BrokenChild = () => {
      throw new Error("still broken")
    }

    try {
      render(
        <PromptPageErrorBoundary
          onReload={onReload}
          onNavigateToChat={onNavigateToChat}
        >
          <BrokenChild />
        </PromptPageErrorBoundary>
      )

      expect(await screen.findByTestId("prompts-error-boundary")).toBeInTheDocument()
      fireEvent.click(screen.getByTestId("prompts-error-reload"))
      fireEvent.click(screen.getByTestId("prompts-error-go-chat"))

      expect(onReload).toHaveBeenCalledTimes(1)
      expect(onNavigateToChat).toHaveBeenCalledTimes(1)
    } finally {
      restoreWindowError()
      consoleSpy.mockRestore()
    }
  })
})
