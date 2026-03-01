import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { FamilyGuardrailsWizard } from "../FamilyGuardrailsWizard"

const {
  createHouseholdDraftMock,
  updateHouseholdDraftMock,
  addHouseholdMemberDraftMock,
  saveRelationshipDraftMock,
  saveGuardrailPlanDraftMock,
  getActivationSummaryMock
} = vi.hoisted(() => ({
  createHouseholdDraftMock: vi.fn(),
  updateHouseholdDraftMock: vi.fn(),
  addHouseholdMemberDraftMock: vi.fn(),
  saveRelationshipDraftMock: vi.fn(),
  saveGuardrailPlanDraftMock: vi.fn(),
  getActivationSummaryMock: vi.fn()
}))

vi.mock("@/services/family-wizard", () => ({
  createHouseholdDraft: createHouseholdDraftMock,
  updateHouseholdDraft: updateHouseholdDraftMock,
  addHouseholdMemberDraft: addHouseholdMemberDraftMock,
  saveRelationshipDraft: saveRelationshipDraftMock,
  saveGuardrailPlanDraft: saveGuardrailPlanDraftMock,
  getActivationSummary: getActivationSummaryMock
}))

describe("FamilyGuardrailsWizard", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn()
      }))
    })
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    createHouseholdDraftMock.mockReset()
    updateHouseholdDraftMock.mockReset()
    addHouseholdMemberDraftMock.mockReset()
    saveRelationshipDraftMock.mockReset()
    saveGuardrailPlanDraftMock.mockReset()
    getActivationSummaryMock.mockReset()
    getActivationSummaryMock.mockResolvedValue({
      household_draft_id: "draft-1",
      status: "invites_pending",
      active_count: 1,
      pending_count: 1,
      failed_count: 0,
      items: []
    })
  })

  it("renders all core wizard steps", () => {
    render(<FamilyGuardrailsWizard />)

    expect(screen.getByText("Household Basics")).toBeInTheDocument()
    expect(screen.getByText("Invite + Acceptance Tracker")).toBeInTheDocument()
    expect(screen.getByText("Review + Activate")).toBeInTheDocument()
  })

  it("shows mixed activation statuses for pending and active dependents", async () => {
    getActivationSummaryMock.mockResolvedValue({
      household_draft_id: "draft-1",
      status: "partially_active",
      active_count: 1,
      pending_count: 1,
      failed_count: 0,
      items: [
        {
          dependent_user_id: "child-1",
          relationship_status: "pending",
          plan_status: "queued",
          message: "Queued until acceptance"
        },
        {
          dependent_user_id: "child-2",
          relationship_status: "active",
          plan_status: "active",
          message: null
        }
      ]
    })

    render(
      <FamilyGuardrailsWizard
        initialStep={6}
        initialDraft={{
          id: "draft-1",
          owner_user_id: "guardian-1",
          name: "Home",
          mode: "family",
          status: "invites_pending",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z"
        }}
      />
    )

    await waitFor(() => {
      expect(screen.getAllByText("Queued until acceptance").length).toBeGreaterThan(0)
      expect(screen.getAllByText("Active").length).toBeGreaterThan(0)
    })
  })
})
