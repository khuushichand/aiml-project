// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { AttachedResearchContextChip } from "../AttachedResearchContextChip"

const buildAttachedContext = (runId: string, query: string) => ({
  attached_at: "2026-03-18T21:00:00Z",
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

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

describe("AttachedResearchContextChip", () => {
  it("shows a separate pinned section when pinned differs from active", () => {
    const onRestorePinned = vi.fn()
    const onUnpin = vi.fn()

    render(
      <MemoryRouter>
        <AttachedResearchContextChip
          context={buildAttachedContext("run_active", "Active run")}
          pinned={buildAttachedContext("run_pinned", "Pinned run")}
          history={[buildAttachedContext("run_hist", "History run")]}
          onRemove={vi.fn()}
          onPin={vi.fn()}
          onUnpin={onUnpin}
          onRestorePinned={onRestorePinned}
          onSelectHistory={vi.fn()}
        />
      </MemoryRouter>
    )

    expect(screen.getByTestId("attached-research-context-pinned")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pin" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pinned run" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Pinned run" }))
    expect(onRestorePinned).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getAllByRole("button", { name: "Unpin" })[0])
    expect(onUnpin).toHaveBeenCalledTimes(1)
  })

  it("collapses duplicate display when the active attachment is already pinned", () => {
    render(
      <MemoryRouter>
        <AttachedResearchContextChip
          context={buildAttachedContext("run_active", "Active run")}
          pinned={buildAttachedContext("run_active", "Active run")}
          onRemove={vi.fn()}
          onUnpin={vi.fn()}
        />
      </MemoryRouter>
    )

    expect(
      screen.queryByTestId("attached-research-context-pinned")
    ).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Unpin" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Pin" })).not.toBeInTheDocument()
  })

  it("shows direct pin actions for recent history entries", () => {
    const onPinHistory = vi.fn()
    const onSelectHistory = vi.fn()

    render(
      <MemoryRouter>
        <AttachedResearchContextChip
          context={buildAttachedContext("run_active", "Active run")}
          history={[buildAttachedContext("run_hist", "History run")]}
          onRemove={vi.fn()}
          onPinHistory={onPinHistory}
          onSelectHistory={onSelectHistory}
        />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole("button", { name: "Pin History run" }))

    expect(onPinHistory).toHaveBeenCalledTimes(1)
    expect(onSelectHistory).not.toHaveBeenCalled()
  })
})
