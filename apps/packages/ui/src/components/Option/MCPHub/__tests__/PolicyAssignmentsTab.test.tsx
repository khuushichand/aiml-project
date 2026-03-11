// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listPolicyAssignments: vi.fn(),
  createPolicyAssignment: vi.fn(),
  updatePolicyAssignment: vi.fn(),
  listPathScopeObjects: vi.fn(),
  listWorkspaceSetObjects: vi.fn(),
  listPolicyAssignmentWorkspaces: vi.fn(),
  addPolicyAssignmentWorkspace: vi.fn(),
  deletePolicyAssignmentWorkspace: vi.fn(),
  getPolicyAssignmentOverride: vi.fn(),
  upsertPolicyAssignmentOverride: vi.fn(),
  deletePolicyAssignmentOverride: vi.fn(),
  listPermissionProfiles: vi.fn(),
  listApprovalPolicies: vi.fn(),
  getEffectivePolicy: vi.fn(),
  getToolRegistrySummary: vi.fn(),
  listExternalServers: vi.fn(),
  listAssignmentCredentialBindings: vi.fn(),
  upsertAssignmentCredentialBinding: vi.fn(),
  deleteAssignmentCredentialBinding: vi.fn(),
  getAssignmentExternalAccess: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listPolicyAssignments: (...args: unknown[]) => mocks.listPolicyAssignments(...args),
  createPolicyAssignment: (...args: unknown[]) => mocks.createPolicyAssignment(...args),
  updatePolicyAssignment: (...args: unknown[]) => mocks.updatePolicyAssignment(...args),
  listPathScopeObjects: (...args: unknown[]) => mocks.listPathScopeObjects(...args),
  listWorkspaceSetObjects: (...args: unknown[]) => mocks.listWorkspaceSetObjects(...args),
  listPolicyAssignmentWorkspaces: (...args: unknown[]) => mocks.listPolicyAssignmentWorkspaces(...args),
  addPolicyAssignmentWorkspace: (...args: unknown[]) => mocks.addPolicyAssignmentWorkspace(...args),
  deletePolicyAssignmentWorkspace: (...args: unknown[]) => mocks.deletePolicyAssignmentWorkspace(...args),
  getPolicyAssignmentOverride: (...args: unknown[]) => mocks.getPolicyAssignmentOverride(...args),
  upsertPolicyAssignmentOverride: (...args: unknown[]) => mocks.upsertPolicyAssignmentOverride(...args),
  deletePolicyAssignmentOverride: (...args: unknown[]) => mocks.deletePolicyAssignmentOverride(...args),
  listPermissionProfiles: (...args: unknown[]) => mocks.listPermissionProfiles(...args),
  listApprovalPolicies: (...args: unknown[]) => mocks.listApprovalPolicies(...args),
  getEffectivePolicy: (...args: unknown[]) => mocks.getEffectivePolicy(...args),
  getToolRegistrySummary: (...args: unknown[]) => mocks.getToolRegistrySummary(...args),
  listExternalServers: (...args: unknown[]) => mocks.listExternalServers(...args),
  listAssignmentCredentialBindings: (...args: unknown[]) => mocks.listAssignmentCredentialBindings(...args),
  upsertAssignmentCredentialBinding: (...args: unknown[]) => mocks.upsertAssignmentCredentialBinding(...args),
  deleteAssignmentCredentialBinding: (...args: unknown[]) => mocks.deleteAssignmentCredentialBinding(...args),
  getAssignmentExternalAccess: (...args: unknown[]) => mocks.getAssignmentExternalAccess(...args)
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
        path_scope_object_id: 41,
        workspace_source_mode: "named",
        workspace_set_object_id: 51,
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
      path_scope_object_id: null,
      workspace_source_mode: "inline",
      workspace_set_object_id: null,
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
      path_scope_object_id: 41,
      workspace_source_mode: "named",
      workspace_set_object_id: 51,
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
    mocks.listPathScopeObjects.mockResolvedValue([
      {
        id: 41,
        name: "Docs Only",
        owner_scope_type: "global",
        path_scope_document: {
          path_scope_mode: "workspace_root",
          path_allowlist_prefixes: ["docs"]
        },
        is_active: true
      }
    ])
    mocks.listWorkspaceSetObjects.mockResolvedValue([
      {
        id: 51,
        name: "Primary Workspace Set",
        owner_scope_type: "user",
        owner_scope_id: 7,
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
      policy_document: {
        path_scope_mode: "workspace_root",
        path_scope_enforcement: "approval_required_when_unenforceable"
      },
      selected_assignment_id: 11,
      selected_workspace_source_mode: "named",
      selected_workspace_set_object_id: 51,
      selected_workspace_set_object_name: "Primary Workspace Set",
      selected_assignment_workspace_ids: ["workspace-alpha"],
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
    mocks.getToolRegistrySummary.mockResolvedValue({
      entries: [
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
          path_argument_hints: ["cwd", "files[].path"],
          metadata_source: "heuristic",
          metadata_warnings: []
        }
      ],
      modules: [
        {
          module: "sandbox",
          display_name: "sandbox",
          tool_count: 1,
          risk_summary: { low: 0, medium: 0, high: 1, unclassified: 0 },
          metadata_warnings: []
        }
      ]
    })
    mocks.listExternalServers.mockResolvedValue([
      {
        id: "docs-managed",
        name: "Docs Managed",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: true,
        server_source: "managed",
        binding_count: 1,
        runtime_executable: true,
        credential_slots: [
          {
            server_id: "docs-managed",
            slot_name: "token_readonly",
            display_name: "Read-only token",
            secret_kind: "bearer_token",
            privilege_class: "read",
            is_required: true,
            secret_configured: true
          }
        ]
      },
      {
        id: "search-api",
        name: "Search API",
        enabled: true,
        owner_scope_type: "global",
        transport: "websocket",
        config: {},
        secret_configured: false,
        server_source: "managed",
        binding_count: 0,
        runtime_executable: true,
        credential_slots: [
          {
            server_id: "search-api",
            slot_name: "token_write",
            display_name: "Write token",
            secret_kind: "bearer_token",
            privilege_class: "write",
            is_required: true,
            secret_configured: false
          }
        ]
      },
      {
        id: "legacy-search",
        name: "Legacy Search",
        enabled: true,
        owner_scope_type: "global",
        transport: "websocket",
        config: {},
        secret_configured: false,
        server_source: "legacy",
        binding_count: 0,
        runtime_executable: false,
        credential_slots: []
      }
    ])
    mocks.listAssignmentCredentialBindings.mockResolvedValue([
      {
        id: 52,
        binding_target_type: "policy_assignment",
        binding_target_id: "11",
        external_server_id: "docs-managed",
        slot_name: "token_readonly",
        credential_ref: "slot",
        binding_mode: "disable",
        usage_rules: {}
      }
    ])
    mocks.upsertAssignmentCredentialBinding.mockResolvedValue({
      id: 53,
      binding_target_type: "policy_assignment",
      binding_target_id: "11",
      external_server_id: "search-api",
      slot_name: "token_write",
      credential_ref: "slot",
      binding_mode: "grant",
      usage_rules: {}
    })
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
    mocks.listPolicyAssignmentWorkspaces.mockResolvedValue([
      { assignment_id: 11, workspace_id: "workspace-alpha" }
    ])
    mocks.addPolicyAssignmentWorkspace.mockResolvedValue({
      assignment_id: 11,
      workspace_id: "workspace-beta"
    })
    mocks.deletePolicyAssignmentWorkspace.mockResolvedValue({ ok: true })
  })

  it("loads assignments and shows the current effective preview", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    expect(await screen.findByText("researcher")).toBeTruthy()
    expect(await screen.findByText("process.execute")).toBeTruthy()
    expect(screen.getByText("Bash(git *)")).toBeTruthy()
    expect(screen.getByText("override active")).toBeTruthy()
    expect(screen.getByText(/workspaces workspace-alpha/i)).toBeTruthy()
    expect(screen.getAllByText(/workspace set primary workspace set/i).length).toBeGreaterThan(0)
    expect(screen.getByText("Why This Applies")).toBeTruthy()
    expect(screen.getByText(/allowed_tools/i)).toBeTruthy()
    expect(screen.getByText(/assignment override/i)).toBeTruthy()
    expect(screen.getByText("Workspace root")).toBeTruthy()
    expect(screen.getByText("Path approval fallback")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new assignment/i }))
    expect(screen.getByLabelText(/target type/i)).toBeTruthy()
    expect(screen.getByText(/allowed modules and tools/i)).toBeTruthy()
    await user.click(screen.getByRole("checkbox", { name: /sandbox\.run/i }))
    expect(screen.getByText(/local file scope/i)).toBeTruthy()
  })

  it("loads the assignment override editor and saves the override independently", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    await screen.findByText("researcher")
    await user.click(screen.getByRole("button", { name: "Edit" }))

    expect(await screen.findByText("Assignment Override")).toBeTruthy()
    expect(screen.getByText("Path Scope Source")).toBeTruthy()
    expect(screen.getByText("Workspace Access")).toBeTruthy()
    expect(screen.getByText("Base Assignment Policy")).toBeTruthy()
    expect(screen.getAllByText(/approval fallback/i).length).toBeGreaterThan(0)
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

  it("manages assignment external service bindings and explains blocked access", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    await screen.findByText("researcher")
    await user.click(screen.getByRole("button", { name: "Edit" }))

    expect(await screen.findByText("External Service Bindings")).toBeTruthy()
    expect(screen.getByLabelText("Docs Managed Read-only token")).toBeTruthy()
    expect(screen.getByLabelText("Search API Write token")).toBeTruthy()
    expect(screen.queryByText("Legacy Search")).toBeNull()
    expect(screen.getAllByText(/disabled by assignment/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/missing secret/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText("Read-only token").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Write token").length).toBeGreaterThan(0)

    await user.selectOptions(screen.getByLabelText("Search API Write token"), "grant")

    expect(mocks.upsertAssignmentCredentialBinding).toHaveBeenCalledWith(
      11,
      "search-api",
      { binding_mode: "grant" },
      "token_write"
    )
  })

  it("saves named workspace source without syncing inline assignment workspaces", async () => {
    const user = userEvent.setup()
    render(<PolicyAssignmentsTab />)

    await screen.findByText("researcher")
    await user.click(screen.getByRole("button", { name: /new assignment/i }))

    await user.selectOptions(screen.getByLabelText(/target type/i), "persona")
    await user.type(screen.getByLabelText(/target id/i), "analyst")
    await user.click(screen.getByRole("radio", { name: /use named workspace set/i }))
    await user.selectOptions(screen.getByLabelText(/assignment named workspace set/i), "51")
    await user.click(screen.getByRole("button", { name: /save assignment/i }))

    expect(mocks.createPolicyAssignment).toHaveBeenCalledWith({
      target_type: "persona",
      target_id: "analyst",
      owner_scope_type: "user",
      profile_id: null,
      path_scope_object_id: null,
      workspace_source_mode: "named",
      workspace_set_object_id: 51,
      approval_policy_id: null,
      inline_policy_document: {},
      is_active: true
    })
    expect(mocks.addPolicyAssignmentWorkspace).not.toHaveBeenCalled()
    expect(mocks.deletePolicyAssignmentWorkspace).not.toHaveBeenCalled()
  })

  it("surfaces structured multi-root overlap validation details from assignment saves", async () => {
    const user = userEvent.setup()
    const error = Object.assign(
      new Error("Named workspace source contains overlapping roots for multi-root execution."),
      {
        details: {
          detail: {
            code: "assignment_multi_root_overlap",
            message: "Named workspace source contains overlapping roots for multi-root execution.",
            conflicting_workspace_ids: ["workspace-alpha", "workspace-beta"],
            conflicting_workspace_roots: ["/repo", "/repo/docs"],
            workspace_source_mode: "named"
          }
        }
      }
    )
    mocks.createPolicyAssignment.mockRejectedValueOnce(error)

    render(<PolicyAssignmentsTab />)

    await screen.findByText("researcher")
    await user.click(screen.getByRole("button", { name: /new assignment/i }))
    await user.selectOptions(screen.getByLabelText(/target type/i), "persona")
    await user.type(screen.getByLabelText(/target id/i), "overlap-case")
    await user.click(screen.getByRole("radio", { name: /use named workspace set/i }))
    await user.selectOptions(screen.getByLabelText(/assignment named workspace set/i), "51")
    await user.click(screen.getByRole("button", { name: /save assignment/i }))

    const alert = await screen.findByRole("alert")
    expect(alert.textContent).toMatch(/named workspace source contains overlapping roots for multi-root execution/i)
    expect(alert.textContent).toMatch(/workspace-alpha, workspace-beta/i)
    expect(alert.textContent).toMatch(/\/repo, \/repo\/docs/i)
  })
})
