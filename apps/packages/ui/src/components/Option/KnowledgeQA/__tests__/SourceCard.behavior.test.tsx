import React from "react"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { SourceCard } from "../SourceCard"

describe("SourceCard copy interactions", () => {
  it("ignores stale clipboard completions so the latest copy action owns the UI state", async () => {
    let resolveFirstCopy: (() => void) | null = null
    let callCount = 0
    const writeTextMock = vi.fn().mockImplementation(() => {
      callCount += 1
      if (callCount === 1) {
        return new Promise<void>((resolve) => {
          resolveFirstCopy = resolve
        })
      }
      return Promise.resolve(undefined)
    })

    Object.defineProperty(globalThis.navigator, "clipboard", {
      value: { writeText: writeTextMock },
      configurable: true,
    })

    render(
      <SourceCard
        result={{
          id: "source-1",
          content: "Important quoted source text",
          metadata: {
            title: "Source A",
            url: "https://example.com/source-a",
            source_type: "web",
          },
          score: 0.91,
        }}
        index={1}
        isCited={false}
        isFocused={false}
        onSourceHover={vi.fn()}
        onAskAbout={vi.fn()}
        onViewFull={vi.fn()}
        onSourceFeedback={vi.fn()}
        onRetrySourceFeedback={vi.fn()}
        onTogglePin={vi.fn()}
        onJumpToCitation={vi.fn()}
        feedbackThumb={null}
        feedbackSubmitting={false}
        feedbackError={null}
        isPinned={false}
        highlightTerms={[]}
        citationUsages={[]}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Copy text/i }))
    fireEvent.click(screen.getByRole("button", { name: /Copy citation/i }))

    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByRole("button", { name: /Copied citation/i })).toBeInTheDocument()

    resolveFirstCopy?.()
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByRole("button", { name: /Copied citation/i })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Copied text/i })).not.toBeInTheDocument()
  })

  it("keeps the latest copy confirmation visible until its own timeout completes", async () => {
    vi.useFakeTimers()
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(globalThis.navigator, "clipboard", {
      value: { writeText: writeTextMock },
      configurable: true,
    })

    render(
      <SourceCard
        result={{
          id: "source-1",
          content: "Important quoted source text",
          metadata: {
            title: "Source A",
            url: "https://example.com/source-a",
            source_type: "web",
          },
          score: 0.91,
        }}
        index={1}
        isCited={false}
        isFocused={false}
        onSourceHover={vi.fn()}
        onAskAbout={vi.fn()}
        onViewFull={vi.fn()}
        onSourceFeedback={vi.fn()}
        onRetrySourceFeedback={vi.fn()}
        onTogglePin={vi.fn()}
        onJumpToCitation={vi.fn()}
        feedbackThumb={null}
        feedbackSubmitting={false}
        feedbackError={null}
        isPinned={false}
        highlightTerms={[]}
        citationUsages={[]}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Copy text/i }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByRole("button", { name: /Copied text/i })).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    fireEvent.click(screen.getByRole("button", { name: /Copy citation/i }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByRole("button", { name: /Copied citation/i })).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole("button", { name: /Copied citation/i })).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole("button", { name: /Copy citation/i })).toBeInTheDocument()

    vi.useRealTimers()
  })

  it("does not schedule a copied-state reset after unmount when clipboard resolves late", async () => {
    let resolveCopy: (() => void) | null = null
    const setTimeoutSpy = vi.spyOn(window, "setTimeout")
    const writeTextMock = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveCopy = resolve
        })
    )
    Object.defineProperty(globalThis.navigator, "clipboard", {
      value: { writeText: writeTextMock },
      configurable: true,
    })

    const { unmount } = render(
      <SourceCard
        result={{
          id: "source-1",
          content: "Important quoted source text",
          metadata: {
            title: "Source A",
            url: "https://example.com/source-a",
            source_type: "web",
          },
          score: 0.91,
        }}
        index={1}
        isCited={false}
        isFocused={false}
        onSourceHover={vi.fn()}
        onAskAbout={vi.fn()}
        onViewFull={vi.fn()}
        onSourceFeedback={vi.fn()}
        onRetrySourceFeedback={vi.fn()}
        onTogglePin={vi.fn()}
        onJumpToCitation={vi.fn()}
        feedbackThumb={null}
        feedbackSubmitting={false}
        feedbackError={null}
        isPinned={false}
        highlightTerms={[]}
        citationUsages={[]}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Copy text/i }))
    unmount()

    resolveCopy?.()
    await act(async () => {
      await Promise.resolve()
    })

    expect(setTimeoutSpy).not.toHaveBeenCalled()
    setTimeoutSpy.mockRestore()
  })
})
