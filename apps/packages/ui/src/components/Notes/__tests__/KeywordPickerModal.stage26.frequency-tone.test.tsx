import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import KeywordPickerModal from "../KeywordPickerModal"

const t = (
  key: string,
  defaultValueOrOptions?:
    | string
    | {
        defaultValue?: string
        [key: string]: unknown
      }
) => {
  if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
  if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
  return key
}

const renderModal = (keywordNoteCountByKey: Record<string, number>, filteredKeywordPickerOptions: string[]) =>
  render(
    <KeywordPickerModal
      open
      availableKeywords={filteredKeywordPickerOptions}
      filteredKeywordPickerOptions={filteredKeywordPickerOptions}
      recentKeywordPickerOptions={[]}
      keywordNoteCountByKey={keywordNoteCountByKey}
      sortMode="frequency_desc"
      keywordPickerQuery=""
      keywordPickerSelection={[]}
      onCancel={vi.fn()}
      onApply={vi.fn()}
      onSortModeChange={vi.fn()}
      onToggleRecentKeyword={vi.fn()}
      onQueryChange={vi.fn()}
      onSelectionChange={vi.fn()}
      onSelectAll={vi.fn()}
      onClear={vi.fn()}
      t={t as any}
    />
  )

describe("KeywordPickerModal stage 26 frequency hierarchy cues", () => {
  it("renders high/medium/low frequency tones for keyword options", async () => {
    renderModal(
      {
        alpha: 10,
        beta: 4,
        gamma: 1
      },
      ["alpha", "beta", "gamma"]
    )

    expect(
      await screen.findByTestId("notes-keyword-picker-option-label-alpha")
    ).toHaveAttribute("data-frequency-tone", "high")
    expect(screen.getByTestId("notes-keyword-picker-option-label-beta")).toHaveAttribute(
      "data-frequency-tone",
      "medium"
    )
    expect(screen.getByTestId("notes-keyword-picker-option-label-gamma")).toHaveAttribute(
      "data-frequency-tone",
      "low"
    )
  })

  it("falls back to neutral tone when note counts are missing", async () => {
    renderModal(
      {
        alpha: 3
      },
      ["alpha", "unknown-keyword"]
    )

    expect(
      await screen.findByTestId("notes-keyword-picker-option-label-unknown-keyword")
    ).toHaveAttribute("data-frequency-tone", "none")
  })
})
