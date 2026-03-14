// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listGovernancePacks: vi.fn(),
  getGovernancePackDetail: vi.fn(),
  dryRunGovernancePack: vi.fn(),
  importGovernancePack: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listGovernancePacks: (...args: unknown[]) => mocks.listGovernancePacks(...args),
  getGovernancePackDetail: (...args: unknown[]) => mocks.getGovernancePackDetail(...args),
  dryRunGovernancePack: (...args: unknown[]) => mocks.dryRunGovernancePack(...args),
  importGovernancePack: (...args: unknown[]) => mocks.importGovernancePack(...args)
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
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
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

    expect(await screen.findByText("Researcher Pack")).toBeTruthy()

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
})
