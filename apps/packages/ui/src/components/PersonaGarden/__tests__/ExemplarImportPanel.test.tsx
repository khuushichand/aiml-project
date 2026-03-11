import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  importPersonaExemplars: vi.fn(),
  reviewPersonaExemplar: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    importPersonaExemplars: (...args: unknown[]) =>
      (mocks.importPersonaExemplars as (...args: unknown[]) => unknown)(...args),
    reviewPersonaExemplar: (...args: unknown[]) =>
      (mocks.reviewPersonaExemplar as (...args: unknown[]) => unknown)(...args)
  }
}))

import { ExemplarImportPanel } from "../ExemplarImportPanel"

describe("ExemplarImportPanel", () => {
  beforeEach(() => {
    mocks.importPersonaExemplars.mockReset()
    mocks.reviewPersonaExemplar.mockReset()
    mocks.importPersonaExemplars.mockResolvedValue([
      {
        id: "candidate-1",
        persona_id: "persona-1",
        kind: "style",
        content: "Imported candidate",
        tone: "neutral",
        scenario_tags: ["general"],
        capability_tags: [],
        priority: 1,
        enabled: false,
        source_type: "generated_candidate"
      }
    ])
    mocks.reviewPersonaExemplar.mockImplementation(
      async (_personaId: string, exemplarId: string, payload: Record<string, unknown>) => ({
        id: exemplarId,
        persona_id: "persona-1",
        kind: "style",
        content: "Imported candidate",
        tone: "neutral",
        scenario_tags: ["general"],
        capability_tags: [],
        priority: 1,
        enabled: payload.action === "approve",
        source_type: "generated_candidate",
        notes: String(payload.action)
      })
    )
  })

  it("validates transcript input and imports candidate exemplars", async () => {
    const onCandidatesImported = vi.fn()

    render(
      <ExemplarImportPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        candidates={[]}
        onCandidatesImported={onCandidatesImported}
        onCandidateReviewed={vi.fn()}
      />
    )

    fireEvent.click(screen.getByTestId("exemplar-import-submit"))
    expect(screen.getByText("Transcript is required")).toBeInTheDocument()

    fireEvent.change(screen.getByTestId("exemplar-import-transcript-input"), {
      target: {
        value: "Speaker: Hello there, let's keep this grounded and thoughtful."
      }
    })
    fireEvent.click(screen.getByTestId("exemplar-import-submit"))

    await waitFor(() =>
      expect(mocks.importPersonaExemplars).toHaveBeenCalledWith(
        "persona-1",
        expect.objectContaining({
          transcript: "Speaker: Hello there, let's keep this grounded and thoughtful."
        })
      )
    )
    expect(onCandidatesImported).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          id: "candidate-1",
          source_type: "generated_candidate"
        })
      ])
    )
  })

  it("reviews generated candidates with approve and reject actions", async () => {
    const onCandidateReviewed = vi.fn()

    render(
      <ExemplarImportPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        candidates={[
          {
            id: "candidate-1",
            persona_id: "persona-1",
            kind: "style",
            content: "Imported candidate",
            tone: "neutral",
            scenario_tags: ["general"],
            capability_tags: [],
            priority: 1,
            enabled: false,
            source_type: "generated_candidate"
          }
        ]}
        onCandidatesImported={vi.fn()}
        onCandidateReviewed={onCandidateReviewed}
      />
    )

    fireEvent.click(screen.getByTestId("exemplar-import-approve-candidate-1"))
    await waitFor(() =>
      expect(mocks.reviewPersonaExemplar).toHaveBeenCalledWith(
        "persona-1",
        "candidate-1",
        { action: "approve" }
      )
    )

    fireEvent.click(screen.getByTestId("exemplar-import-reject-candidate-1"))
    await waitFor(() =>
      expect(mocks.reviewPersonaExemplar).toHaveBeenCalledWith(
        "persona-1",
        "candidate-1",
        { action: "reject" }
      )
    )
    expect(onCandidateReviewed).toHaveBeenCalled()
  })
})
