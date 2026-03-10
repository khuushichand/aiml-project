// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listPolicyAssignments: vi.fn(),
  createPolicyAssignment: vi.fn(),
  listPermissionProfiles: vi.fn(),
  listApprovalPolicies: vi.fn(),
  getEffectivePolicy: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listPolicyAssignments: (...args: unknown[]) => mocks.listPolicyAssignments(...args),
  createPolicyAssignment: (...args: unknown[]) => mocks.createPolicyAssignment(...args),
  listPermissionProfiles: (...args: unknown[]) => mocks.listPermissionProfiles(...args),
  listApprovalPolicies: (...args: unknown[]) => mocks.listApprovalPolicies(...args),
  getEffectivePolicy: (...args: unknown[]) => mocks.getEffectivePolicy(...args)
}))

import { PolicyAssignmentsTab } from "../PolicyAssignmentsTab"

describe("PolicyAssignmentsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listPolicyAssignments.mockResolvedValue([
      {
        id: 11,
        target_type: "persona",
        target_id: "researcher",
        owner_scope_type: "user",
        owner_scope_id: 7,
        profile_id: 5,
        inline_policy_document: {
          capabilities: ["network.external"]
        },
        approval_policy_id: 17,
        is_active: true
      }
    ])
    mocks.createPolicyAssignment.mockResolvedValue({
      id: 12,
      target_type: "default",
      target_id: null,
      owner_scope_type: "global",
      owner_scope_id: null,
      profile_id: 5,
      inline_policy_document: {},
      approval_policy_id: null,
      is_active: true
    })
    mocks.listPermissionProfiles.mockResolvedValue([
      {
        id: 5,
        name: "Process Exec",
        owner_scope_type: "user",
        mode: "custom",
        policy_document: { capabilities: ["process.execute"] },
        is_active: true
      }
    ])
    mocks.listApprovalPolicies.mockResolvedValue([
      {
        id: 17,
        name: "Outside Profile",
        owner_scope_type: "user",
        mode: "ask_outside_profile",
        rules: {},
        is_active: true
      }
    ])
    mocks.getEffectivePolicy.mockResolvedValue({
      enabled: true,
      allowed_tools: ["Bash(git *)"],
      denied_tools: [],
      capabilities: ["process.execute", "network.external"],
      approval_policy_id: 17,
      approval_mode: "ask_outside_profile",
      policy_document: {},
      sources: []
    })
  })

  it("loads assignments and shows the current effective preview", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    expect(await screen.findByText("researcher")).toBeTruthy()
    expect(await screen.findByText("process.execute")).toBeTruthy()
    expect(screen.getByText("Bash(git *)")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new assignment/i }))
    expect(screen.getByLabelText(/target type/i)).toBeTruthy()
  })
})
