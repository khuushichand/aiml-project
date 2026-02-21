// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ContextFootprintPanel } from "../ContextFootprintPanel"

const t = ((
  key: string,
  fallback?: string,
  options?: Record<string, unknown>
) => {
  const template = fallback || key
  if (!options) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = options[token]
    return value == null ? "" : String(value)
  })
}) as any

describe("ContextFootprintPanel context-breakdown integration", () => {
  it("renders interpolated warning copy and executes all context controls", async () => {
    const user = userEvent.setup()
    const onClearPromptContext = vi.fn()
    const onClearPinnedSourceContext = vi.fn()
    const onClearHistoryContext = vi.fn()
    const onCreateSummaryCheckpoint = vi.fn()
    const onReviewCharacterContext = vi.fn()
    const onTrimLargestContextContributor = vi.fn()

    render(
      <ContextFootprintPanel
        t={t}
        rows={[
          { id: "character", label: "Character + world book", tokens: 540 },
          { id: "prompt", label: "System/prompt steering", tokens: 280 },
          { id: "pinned", label: "Pinned sources", tokens: 140 }
        ]}
        nonMessageContextPercent={46.7}
        showNonMessageContextWarning
        thresholdPercent={40}
        onClearPromptContext={onClearPromptContext}
        onClearPinnedSourceContext={onClearPinnedSourceContext}
        onClearHistoryContext={onClearHistoryContext}
        onCreateSummaryCheckpoint={onCreateSummaryCheckpoint}
        onReviewCharacterContext={onReviewCharacterContext}
        onTrimLargestContextContributor={onTrimLargestContextContributor}
      />
    )

    expect(screen.getByText("Context footprint estimate")).toBeInTheDocument()
    expect(screen.getByText("Character + world book")).toBeInTheDocument()
    expect(screen.getByText("540 tokens")).toBeInTheDocument()
    expect(screen.getByText("Non-message context share: 47%")).toBeInTheDocument()
    expect(
      screen.getByText("Non-message context exceeds 40% of your context window.")
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Clear prompts" }))
    await user.click(
      screen.getByRole("button", { name: "Clear pinned sources" })
    )
    await user.click(screen.getByRole("button", { name: "Clear history" }))
    await user.click(
      screen.getByRole("button", { name: "Create checkpoint summary" })
    )
    await user.click(screen.getByRole("button", { name: "Review character" }))
    await user.click(
      screen.getByRole("button", { name: "Trim largest contributor" })
    )

    expect(onClearPromptContext).toHaveBeenCalledTimes(1)
    expect(onClearPinnedSourceContext).toHaveBeenCalledTimes(1)
    expect(onClearHistoryContext).toHaveBeenCalledTimes(1)
    expect(onCreateSummaryCheckpoint).toHaveBeenCalledTimes(1)
    expect(onReviewCharacterContext).toHaveBeenCalledTimes(1)
    expect(onTrimLargestContextContributor).toHaveBeenCalledTimes(1)
  })
})
