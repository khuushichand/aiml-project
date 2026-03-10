// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listPolicyAssignments: vi.fn(),
  createPolicyAssignment: vi.fn(),
  updatePolicyAssignment: vi.fn(),
  getPolicyAssignmentOverride: vi.fn(),
  upsertPolicyAssignmentOverride: vi.fn(),
  deletePolicyAssignmentOverride: vi.fn(),
  listPermissionProfiles: vi.fn(),
  listApprovalPolicies: vi.fn(),
  getEffectivePolicy: vi.fn(),
  listToolRegistry: vi.fn(),
  listToolRegistryModules: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listPolicyAssignments: (...args: unknown[]) => mocks.listPolicyAssignments(...args),
  createPolicyAssignment: (...args: unknown[]) => mocks.createPolicyAssignment(...args),
  updatePolicyAssignment: (...args: unknown[]) => mocks.updatePolicyAssignment(...args),
  getPolicyAssignmentOverride: (...args: unknown[]) => mocks.getPolicyAssignmentOverride(...args),
  upsertPolicyAssignmentOverride: (...args: unknown[]) => mocks.upsertPolicyAssignmentOverride(...args),
  deletePolicyAssignmentOverride: (...args: unknown[]) => mocks.deletePolicyAssignmentOverride(...args),
  listPermissionProfiles: (...args: unknown[]) => mocks.listPermissionProfiles(...args),
  listApprovalPolicies: (...args: unknown[]) => mocks.listApprovalPolicies(...args),
  getEffectivePolicy: (...args: unknown[]) => mocks.getEffectivePolicy(...args),
  listToolRegistry: (...args: unknown[]) => mocks.listToolRegistry(...args),
  listToolRegistryModules: (...args: unknown[]) => mocks.listToolRegistryModules(...args)
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
        is_active: true,
        has_override: true,
        override_id: 31,
        override_active: true,
        override_updated_at: "2026-03-09T21:00:00Z"
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
    mocks.updatePolicyAssignment.mockResolvedValue({
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
      is_active: true,
      has_override: true,
      override_id: 31,
      override_active: true,
      override_updated_at: "2026-03-09T21:00:00Z"
    })
    mocks.getPolicyAssignmentOverride.mockResolvedValue({
      id: 31,
      assignment_id: 11,
      override_policy_document: {
        allowed_tools: ["remote.fetch"],
        approval_mode: "ask_outside_profile"
      },
      is_active: true
    })
    mocks.upsertPolicyAssignmentOverride.mockResolvedValue({
      id: 31,
      assignment_id: 11,
      override_policy_document: {
        allowed_tools: ["remote.fetch"],
        approval_mode: "ask_outside_profile"
      },
      is_active: true
    })
    mocks.deletePolicyAssignmentOverride.mockResolvedValue({ ok: true })
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
      sources: [],
      provenance: [
        {
          field: "allowed_tools",
          value: ["remote.fetch"],
          source_kind: "assignment_override",
          assignment_id: 11,
          profile_id: 5,
          override_id: 31,
          effect: "merged"
        }
      ]
    })
    mocks.listToolRegistry.mockResolvedValue([
      {
        tool_name: "sandbox.run",
        display_name: "sandbox.run",
        module: "sandbox",
        category: "execution",
        risk_class: "high",
        capabilities: ["process.execute"],
        mutates_state: true,
        uses_filesystem: true,
        uses_processes: true,
        uses_network: false,
        uses_credentials: false,
        supports_arguments_preview: true,
        path_boundable: false,
        metadata_source: "heuristic",
        metadata_warnings: []
      }
    ])
    mocks.listToolRegistryModules.mockResolvedValue([
      {
        module: "sandbox",
        display_name: "sandbox",
        tool_count: 1,
        risk_summary: { low: 0, medium: 0, high: 1, unclassified: 0 },
        metadata_warnings: []
      }
    ])
  })

  it("loads assignments and shows the current effective preview", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    expect(await screen.findByText("researcher")).toBeTruthy()
    expect(await screen.findByText("process.execute")).toBeTruthy()
    expect(screen.getByText("Bash(git *)")).toBeTruthy()
    expect(screen.getByText("override active")).toBeTruthy()
    expect(screen.getByText("Why This Applies")).toBeTruthy()
    expect(screen.getByText(/allowed_tools/i)).toBeTruthy()
    expect(screen.getByText(/assignment override/i)).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new assignment/i }))
    expect(screen.getByLabelText(/target type/i)).toBeTruthy()
    expect(screen.getByText(/allowed modules and tools/i)).toBeTruthy()
  })

  it("loads the assignment override editor and saves the override independently", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    await screen.findByText("researcher")
    await user.click(screen.getByRole("button", { name: "Edit" }))

    expect(await screen.findByText("Assignment Override")).toBeTruthy()
    expect(screen.getByText("Base Assignment Policy")).toBeTruthy()
    expect(mocks.getPolicyAssignmentOverride).toHaveBeenCalledWith(11)

    await user.click(screen.getByRole("button", { name: /save override/i }))

    expect(mocks.upsertPolicyAssignmentOverride).toHaveBeenCalledWith(11, {
      override_policy_document: {
        allowed_tools: ["remote.fetch"],
        approval_mode: "ask_outside_profile"
      },
      is_active: true
    })
  })
})
