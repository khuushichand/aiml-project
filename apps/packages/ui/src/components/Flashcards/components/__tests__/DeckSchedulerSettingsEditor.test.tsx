import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { DeckSchedulerSettingsEditor } from "../DeckSchedulerSettingsEditor"
import { useDeckSchedulerDraft } from "../../hooks/useDeckSchedulerDraft"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      const interpolate = (
        template: string,
        values?: {
          [key: string]: unknown
        }
      ) =>
        template.replace(/\{\{\s*([^\s}]+)\s*\}\}/g, (_match, token: string) => {
          const value = values?.[token]
          return value == null ? "" : String(value)
        })

      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) {
        return interpolate(defaultValueOrOptions.defaultValue, defaultValueOrOptions)
      }
      return key
    }
  })
}))

const Harness = () => {
  const schedulerDraft = useDeckSchedulerDraft()
  const [validatedJson, setValidatedJson] = React.useState("")

  return (
    <div>
      <DeckSchedulerSettingsEditor
        draft={schedulerDraft.draft}
        errors={schedulerDraft.errors}
        summary={schedulerDraft.summary}
        onFieldChange={schedulerDraft.updateField}
        onApplyPreset={schedulerDraft.applyPreset}
        onResetDefaults={schedulerDraft.resetToDefaults}
      />
      <button
        type="button"
        onClick={() => {
          const settings = schedulerDraft.getValidatedSettings()
          setValidatedJson(settings ? JSON.stringify(settings) : "")
        }}
      >
        Validate draft
      </button>
      <output data-testid="deck-scheduler-editor-validated-json">{validatedJson}</output>
    </div>
  )
}

describe("DeckSchedulerSettingsEditor", () => {
  it("updates the summary when a preset is selected", () => {
    render(<Harness />)

    expect(screen.getByTestId("deck-scheduler-editor-summary")).toHaveTextContent(
      "1m,10m -> 1d / easy 4d / leech 8 / fuzz off"
    )

    fireEvent.click(screen.getByTestId("deck-scheduler-editor-preset-fast_acquisition"))

    expect(screen.getByTestId("deck-scheduler-editor-summary")).toHaveTextContent(
      "1m,5m,15m -> 1d / easy 3d / leech 10 / fuzz off"
    )
  })

  it("validates advanced edits into a full scheduler settings object", () => {
    render(<Harness />)

    fireEvent.click(screen.getByTestId("deck-scheduler-editor-toggle-advanced"))
    fireEvent.change(screen.getByTestId("deck-scheduler-editor-field-leech-threshold"), {
      target: { value: "12" }
    })
    fireEvent.click(screen.getByRole("button", { name: /validate draft/i }))

    expect(screen.getByTestId("deck-scheduler-editor-validated-json")).toHaveTextContent(
      '"leech_threshold":12'
    )
    expect(screen.getByTestId("deck-scheduler-editor-validated-json")).toHaveTextContent(
      '"new_steps_minutes":[1,10]'
    )
  })

  it("resets back to defaults after changes", () => {
    render(<Harness />)

    fireEvent.click(screen.getByTestId("deck-scheduler-editor-preset-conservative_review"))
    fireEvent.click(screen.getByTestId("deck-scheduler-editor-reset"))

    expect(screen.getByTestId("deck-scheduler-editor-summary")).toHaveTextContent(
      "1m,10m -> 1d / easy 4d / leech 8 / fuzz off"
    )
  })

  it("keeps validation errors local to the editor", () => {
    render(<Harness />)

    fireEvent.click(screen.getByTestId("deck-scheduler-editor-toggle-advanced"))
    fireEvent.change(screen.getByTestId("deck-scheduler-editor-field-leech-threshold"), {
      target: { value: "0" }
    })
    fireEvent.click(screen.getByRole("button", { name: /validate draft/i }))

    expect(screen.getByText(/leech threshold must be >= 1/i)).toBeInTheDocument()
    expect(screen.getByTestId("deck-scheduler-editor-validated-json")).toHaveTextContent("")
  })
})
