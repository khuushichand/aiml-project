// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listGovernancePacks: vi.fn(),
  getGovernancePackDetail: vi.fn(),
  dryRunGovernancePack: vi.fn(),
  importGovernancePack: vi.fn(),
  dryRunGovernancePackUpgrade: vi.fn(),
  executeGovernancePackUpgrade: vi.fn(),
  listGovernancePackUpgradeHistory: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listGovernancePacks: (...args: unknown[]) => mocks.listGovernancePacks(...args),
  getGovernancePackDetail: (...args: unknown[]) => mocks.getGovernancePackDetail(...args),
  dryRunGovernancePack: (...args: unknown[]) => mocks.dryRunGovernancePack(...args),
  importGovernancePack: (...args: unknown[]) => mocks.importGovernancePack(...args),
  dryRunGovernancePackUpgrade: (...args: unknown[]) => mocks.dryRunGovernancePackUpgrade(...args),
  executeGovernancePackUpgrade: (...args: unknown[]) => mocks.executeGovernancePackUpgrade(...args),
  listGovernancePackUpgradeHistory: (...args: unknown[]) => mocks.listGovernancePackUpgradeHistory(...args)
}))

import { GovernancePacksTab } from "../GovernancePacksTab"

describe("GovernancePacksTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listGovernancePacks.mockResolvedValue([
      {
        id: 81,
        pack_id: "researcher-pack",
        pack_version: "1.0.0",
        title: "Researcher Pack",
        description: "Portable research governance pack",
        owner_scope_type: "user",
        owner_scope_id: 7,
        bundle_digest: "a".repeat(64),
        is_active_install: true,
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack"
        }
      },
      {
        id: 80,
        pack_id: "researcher-pack",
        pack_version: "0.9.0",
        title: "Researcher Pack",
        description: "Superseded pack",
        owner_scope_type: "user",
        owner_scope_id: 7,
        bundle_digest: "b".repeat(64),
        is_active_install: false,
        superseded_by_governance_pack_id: 81,
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "0.9.0",
          title: "Researcher Pack"
        }
      }
    ])
    mocks.getGovernancePackDetail.mockResolvedValue({
      id: 81,
      pack_id: "researcher-pack",
      pack_version: "1.0.0",
      title: "Researcher Pack",
      description: "Portable research governance pack",
      owner_scope_type: "user",
      owner_scope_id: 7,
      bundle_digest: "a".repeat(64),
      is_active_install: true,
      manifest: {
        pack_id: "researcher-pack",
        pack_version: "1.0.0",
        title: "Researcher Pack"
      },
      normalized_ir: {
        data: {
          profiles: [{ profile_id: "researcher.profile" }]
        }
      },
      imported_objects: [
        {
          object_type: "permission_profile",
          object_id: "5",
          source_object_id: "researcher.profile"
        }
      ]
    })
    mocks.listGovernancePackUpgradeHistory.mockResolvedValue([
      {
        id: 12,
        pack_id: "researcher-pack",
        owner_scope_type: "user",
        owner_scope_id: 7,
        from_governance_pack_id: 80,
        to_governance_pack_id: 81,
        from_pack_version: "0.9.0",
        to_pack_version: "1.0.0",
        status: "executed",
        plan_summary: {
          object_diff_count: 2,
          dependency_impact_count: 1
        },
        accepted_resolutions: {},
        planned_at: "2026-03-14T00:00:00Z",
        executed_at: "2026-03-14T00:05:00Z"
      }
    ])
    mocks.dryRunGovernancePackUpgrade.mockResolvedValue({
      plan: {
        source_governance_pack_id: 81,
        source_manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack"
        },
        target_manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.1.0",
          title: "Researcher Pack"
        },
        object_diff: [
          {
            object_type: "permission_profile",
            source_object_id: "researcher.profile",
            change_type: "modified",
            previous_digest: "1".repeat(64),
            next_digest: "2".repeat(64)
          }
        ],
        dependency_impact: [],
        structural_conflicts: [],
        behavioral_conflicts: [],
        warnings: [],
        planner_inputs_fingerprint: "plan-fingerprint",
        adapter_state_fingerprint: "adapter-fingerprint",
        upgradeable: true
      }
    })
    mocks.executeGovernancePackUpgrade.mockResolvedValue({
      upgrade_id: 13,
      source_governance_pack_id: 81,
      target_governance_pack_id: 82,
      from_pack_version: "1.0.0",
      to_pack_version: "1.1.0",
      planner_inputs_fingerprint: "plan-fingerprint",
      adapter_state_fingerprint: "adapter-fingerprint",
      imported_object_ids: {
        approval_policies: [31],
        permission_profiles: [41],
        policy_assignments: [51]
      },
      imported_object_counts: {
        approval_policies: 1,
        permission_profiles: 1,
        policy_assignments: 1
      }
    })
    mocks.dryRunGovernancePack.mockResolvedValue({
      report: {
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack",
          description: "Portable research governance pack"
        },
        digest: "a".repeat(64),
        resolved_capabilities: ["filesystem.read", "tool.invoke.research"],
        unresolved_capabilities: [],
        warnings: [],
        blocked_objects: [],
        verdict: "importable"
      }
    })
    mocks.importGovernancePack.mockResolvedValue({
      governance_pack_id: 81,
      imported_object_counts: {
        approval_policies: 1,
        permission_profiles: 1,
        policy_assignments: 1
      },
      blocked_objects: [],
      report: {
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack",
          description: "Portable research governance pack"
        },
        digest: "a".repeat(64),
        resolved_capabilities: ["filesystem.read", "tool.invoke.research"],
        unresolved_capabilities: [],
        warnings: [],
        blocked_objects: [],
        verdict: "importable"
      }
    })
  })

  it("renders dry-run compatibility findings before import", async () => {
    const user = userEvent.setup()
    render(<GovernancePacksTab />)

    expect((await screen.findAllByText("Researcher Pack")).length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText(/governance pack json/i), {
      target: {
        value: JSON.stringify({
          manifest: {
            pack_id: "researcher-pack",
            pack_version: "1.0.0",
            pack_schema_version: 1,
            capability_taxonomy_version: 1,
            adapter_contract_version: 1,
            title: "Researcher Pack"
          },
          profiles: [
            {
              profile_id: "researcher.profile",
              name: "Researcher",
              capabilities: { allow: ["filesystem.read", "tool.invoke.research"] },
              approval_intent: "ask",
              environment_requirements: ["workspace_bounded_read"]
            }
          ],
          approvals: [
            { approval_template_id: "researcher.ask", name: "Ask Before Use", mode: "ask" }
          ],
          personas: [],
          assignments: []
        })
      }
    })
    await user.click(screen.getByRole("button", { name: /preview pack/i }))

    expect(await screen.findByText("Resolved capabilities")).toBeTruthy()
    expect(screen.getByText("tool.invoke.research")).toBeTruthy()
    expect(screen.getByText("Importable")).toBeTruthy()
  })

  it("surfaces detail load failures without clearing the inventory", async () => {
    mocks.getGovernancePackDetail.mockRejectedValueOnce(new Error("boom"))

    render(<GovernancePacksTab />)

    expect((await screen.findAllByText("Researcher Pack")).length).toBeGreaterThan(0)
    expect(await screen.findByText("Failed to load pack details.")).toBeTruthy()
    expect(screen.getByText("Installed Packs")).toBeTruthy()
  })

  it("handles non-array inventory responses without crashing", async () => {
    mocks.listGovernancePacks.mockResolvedValueOnce({ rows: [] })

    render(<GovernancePacksTab />)

    expect(await screen.findByText("No governance packs imported yet")).toBeTruthy()
    expect(screen.getByText("Installed Packs")).toBeTruthy()
  })

  it("renders install state badges and upgrade history for the selected pack", async () => {
    render(<GovernancePacksTab />)

    expect(await screen.findByText("Active install")).toBeTruthy()
    expect(await screen.findByText("Inactive install")).toBeTruthy()
    expect(await screen.findByText("Upgrade History")).toBeTruthy()
    expect(screen.getByText("0.9.0 -> 1.0.0")).toBeTruthy()
  })

  it("opens the upgrade modal and renders dry-run object diffs", async () => {
    const user = userEvent.setup()
    render(<GovernancePacksTab />)

    expect((await screen.findAllByText("Researcher Pack")).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText(/governance pack json/i), {
      target: {
        value: JSON.stringify({
          manifest: {
            pack_id: "researcher-pack",
            pack_version: "1.1.0",
            pack_schema_version: 1,
            capability_taxonomy_version: 1,
            adapter_contract_version: 1,
            title: "Researcher Pack"
          },
          profiles: [],
          approvals: [],
          personas: [],
          assignments: []
        })
      }
    })

    await user.click(screen.getByRole("button", { name: /preview upgrade/i }))

    expect(await screen.findByRole("dialog")).toBeTruthy()
    expect(await screen.findByText("Modified objects")).toBeTruthy()
    expect((await screen.findAllByText("permission_profile:researcher.profile")).length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: /execute upgrade/i })).toBeEnabled()
  })

  it("blocks execute upgrade when the dry-run reports conflicts", async () => {
    mocks.dryRunGovernancePackUpgrade.mockResolvedValueOnce({
      plan: {
        source_governance_pack_id: 81,
        source_manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack"
        },
        target_manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.1.0",
          title: "Researcher Pack"
        },
        object_diff: [],
        dependency_impact: [],
        structural_conflicts: [],
        behavioral_conflicts: ["permission_profile:researcher.profile changed"],
        warnings: [],
        planner_inputs_fingerprint: "plan-fingerprint",
        adapter_state_fingerprint: "adapter-fingerprint",
        upgradeable: false
      }
    })
    const user = userEvent.setup()
    render(<GovernancePacksTab />)

    expect((await screen.findAllByText("Researcher Pack")).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText(/governance pack json/i), {
      target: {
        value: JSON.stringify({
          manifest: {
            pack_id: "researcher-pack",
            pack_version: "1.1.0",
            pack_schema_version: 1,
            capability_taxonomy_version: 1,
            adapter_contract_version: 1,
            title: "Researcher Pack"
          },
          profiles: [],
          approvals: [],
          personas: [],
          assignments: []
        })
      }
    })

    await user.click(screen.getByRole("button", { name: /preview upgrade/i }))

    expect(await screen.findByText("Blocking conflicts")).toBeTruthy()
    expect(screen.getByText("permission_profile:researcher.profile changed")).toBeTruthy()
    expect(screen.getByRole("button", { name: /execute upgrade/i })).toBeDisabled()
  })
})
