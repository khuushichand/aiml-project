// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const mocks = vi.hoisted(() => ({
  getEffectivePolicy: vi.fn(),
  listPolicyAssignments: vi.fn(),
  getAssignmentExternalAccess: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  getEffectivePolicy: (...args: unknown[]) => mocks.getEffectivePolicy(...args),
  listPolicyAssignments: (...args: unknown[]) => mocks.listPolicyAssignments(...args),
  getAssignmentExternalAccess: (...args: unknown[]) => mocks.getAssignmentExternalAccess(...args)
}))

import { PersonaPolicySummary } from "../PersonaPolicySummary"

describe("PersonaPolicySummary", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getEffectivePolicy.mockResolvedValue({
      enabled: true,
      allowed_tools: ["Bash(git *)"],
      denied_tools: ["Bash(rm *)"],
      capabilities: ["process.execute"],
      approval_policy_id: 17,
      approval_mode: "ask_outside_profile",
      policy_document: {
        path_scope_mode: "workspace_root",
        path_scope_enforcement: "approval_required_when_unenforceable"
      },
      sources: [],
      provenance: [
        {
          field: "allowed_tools",
          value: ["Bash(git *)"],
          source_kind: "assignment_override",
          assignment_id: 11,
          profile_id: 5,
          override_id: 31,
          effect: "merged"
        }
      ]
    })
    mocks.listPolicyAssignments.mockResolvedValue([
      {
        id: 11,
        target_type: "persona",
        target_id: "researcher",
        owner_scope_type: "user",
        owner_scope_id: 7,
        profile_id: 5,
        inline_policy_document: {},
        approval_policy_id: 17,
        is_active: true
      }
    ])
    mocks.getAssignmentExternalAccess.mockResolvedValue({
      servers: [
        {
          server_id: "docs-managed",
          server_name: "Docs Managed",
          granted_by: "profile",
          disabled_by_assignment: true,
          server_source: "managed",
          secret_available: true,
          runtime_executable: true,
          blocked_reason: "disabled_by_assignment",
          slots: [
            {
              slot_name: "token_readonly",
              display_name: "Read-only token",
              granted_by: "profile",
              disabled_by_assignment: true,
              secret_available: true,
              runtime_usable: false,
              blocked_reason: "slot_disabled_by_assignment"
            }
          ]
        },
        {
          server_id: "search-api",
          server_name: "Search API",
          granted_by: "assignment",
          disabled_by_assignment: false,
          server_source: "managed",
          secret_available: false,
          runtime_executable: true,
          blocked_reason: "missing_secret",
          slots: [
            {
              slot_name: "token_write",
              display_name: "Write token",
              granted_by: "assignment",
              disabled_by_assignment: false,
              secret_available: false,
              runtime_usable: false,
              blocked_reason: "missing_required_slot_secret"
            }
          ]
        }
      ]
    })
  })

  it("renders the effective tool policy for a selected persona", async () => {
    render(<PersonaPolicySummary personaId="researcher" />)

    expect(await screen.findByText("process.execute")).toBeTruthy()
    expect(screen.getByText("Bash(git *)")).toBeTruthy()
    expect(screen.getByText("Bash(rm *)")).toBeTruthy()
    expect(screen.getByText("Override active")).toBeTruthy()
    expect(screen.getByText("Workspace root")).toBeTruthy()
    expect(screen.getByText("Path approval fallback")).toBeTruthy()
    expect(screen.getByText("Docs Managed")).toBeTruthy()
    expect(screen.getByText("Search API")).toBeTruthy()
    expect(screen.getByText("Read-only token")).toBeTruthy()
    expect(screen.getByText("Write token")).toBeTruthy()
    expect(screen.getAllByText(/disabled by assignment/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/missing secret/i).length).toBeGreaterThan(0)
    expect(screen.getByRole("link", { name: /open mcp hub/i })).toBeTruthy()
  })
})
