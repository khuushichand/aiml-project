import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PromptPageErrorBoundary } from "../PromptPageErrorBoundary"

describe("PromptPageErrorBoundary", () => {
  it("renders fallback when a child throws and recovers on retry", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
    let shouldThrow = true

    const FlakyChild = () => {
      if (shouldThrow) {
        throw new Error("boom")
      }
      return <div data-testid="prompt-boundary-child-ok">ok</div>
    }

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
    consoleSpy.mockRestore()
  })

  it("provides reload and route recovery actions", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
    const onReload = vi.fn()
    const onNavigateToChat = vi.fn()

    const BrokenChild = () => {
      throw new Error("still broken")
    }

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
    consoleSpy.mockRestore()
  })
})
