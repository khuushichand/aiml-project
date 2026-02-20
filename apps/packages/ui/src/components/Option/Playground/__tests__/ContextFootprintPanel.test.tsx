// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ContextFootprintPanel } from "../ContextFootprintPanel"

const t = ((key: string, fallback?: string) => fallback || key) as any

describe("ContextFootprintPanel", () => {
  it("renders contributor rows and runs trim/clear actions", async () => {
    const user = userEvent.setup()
    const onClearPromptContext = vi.fn()
    const onClearPinnedSourceContext = vi.fn()
    const onClearHistoryContext = vi.fn()
    const onReviewCharacterContext = vi.fn()
    const onTrimLargestContextContributor = vi.fn()

    render(
      <ContextFootprintPanel
        t={t}
        rows={[
          { id: "character", label: "Character + world book", tokens: 420 },
          { id: "prompt", label: "System/prompt steering", tokens: 260 }
        ]}
        nonMessageContextPercent={47}
        showNonMessageContextWarning
        thresholdPercent={40}
        onClearPromptContext={onClearPromptContext}
        onClearPinnedSourceContext={onClearPinnedSourceContext}
        onClearHistoryContext={onClearHistoryContext}
        onReviewCharacterContext={onReviewCharacterContext}
        onTrimLargestContextContributor={onTrimLargestContextContributor}
      />
    )

    expect(screen.getByText("Context footprint estimate")).toBeInTheDocument()
    expect(screen.getByText("Character + world book")).toBeInTheDocument()
    expect(screen.getByText("420 tokens")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Non-message context exceeds {{threshold}}% of your context window."
      )
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Clear prompts" }))
    await user.click(
      screen.getByRole("button", { name: "Clear pinned sources" })
    )
    await user.click(screen.getByRole("button", { name: "Clear history" }))
    await user.click(screen.getByRole("button", { name: "Review character" }))
    await user.click(
      screen.getByRole("button", { name: "Trim largest contributor" })
    )

    expect(onClearPromptContext).toHaveBeenCalledTimes(1)
    expect(onClearPinnedSourceContext).toHaveBeenCalledTimes(1)
    expect(onClearHistoryContext).toHaveBeenCalledTimes(1)
    expect(onReviewCharacterContext).toHaveBeenCalledTimes(1)
    expect(onTrimLargestContextContributor).toHaveBeenCalledTimes(1)
  })

  it("shows empty-state copy when no contributor tokens are present", () => {
    render(
      <ContextFootprintPanel
        t={t}
        rows={[
          { id: "character", label: "Character + world book", tokens: 0 },
          { id: "prompt", label: "System/prompt steering", tokens: 0 }
        ]}
        nonMessageContextPercent={null}
        showNonMessageContextWarning={false}
        thresholdPercent={40}
        onClearPromptContext={vi.fn()}
        onClearPinnedSourceContext={vi.fn()}
        onClearHistoryContext={vi.fn()}
        onReviewCharacterContext={vi.fn()}
        onTrimLargestContextContributor={vi.fn()}
      />
    )

    expect(
      screen.getByText("No additional context contributors detected.")
    ).toBeInTheDocument()
  })
})
