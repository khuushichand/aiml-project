// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { AttachedResearchContextChip } from "../AttachedResearchContextChip"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

const buildContext = (runId: string, query: string) => ({
  attached_at: "2026-03-08T20:00:00Z",
  run_id: runId,
  query,
  question: query,
  outline: [{ title: "Overview" }],
  key_claims: [{ text: "Claim one" }],
  unresolved_questions: ["Open question"],
  verification_summary: { unsupported_claim_count: 0 },
  source_trust_summary: { high_trust_count: 1 },
  research_url: `/research?run=${runId}`
})

describe("AttachedResearchContextChip", () => {
  it("renders recent research actions and restores a prior attachment immediately", () => {
    const onSelectHistory = vi.fn()

    render(
      <MemoryRouter>
        <AttachedResearchContextChip
          context={buildContext("run_active", "Active query")}
          history={[
            buildContext("run_hist_1", "History one"),
            buildContext("run_hist_2", "History two")
          ]}
          onPreview={vi.fn()}
          onRemove={vi.fn()}
          onSelectHistory={onSelectHistory}
        />
      </MemoryRouter>
    )

    expect(screen.getByTestId("attached-research-context-history")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "History one" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "History two" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "History one" }))

    expect(onSelectHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        run_id: "run_hist_1",
        query: "History one"
      })
    )
  })
})
