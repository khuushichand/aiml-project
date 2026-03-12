// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listGovernanceAuditFindings: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listGovernanceAuditFindings: (...args: unknown[]) => mocks.listGovernanceAuditFindings(...args)
}))

import { GovernanceAuditTab } from "../GovernanceAuditTab"

describe("GovernanceAuditTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listGovernanceAuditFindings.mockResolvedValue({
      items: [
        {
          finding_type: "assignment_validation_blocker",
          severity: "error",
          scope_type: "user",
          scope_id: 7,
          object_kind: "policy_assignment",
          object_id: "11",
          object_label: "researcher",
          message: "Named workspace source contains overlapping roots for multi-root execution.",
          details: {
            conflicting_workspace_ids: ["workspace-alpha", "workspace-beta"]
          },
          navigate_to: {
            tab: "assignments",
            object_kind: "policy_assignment",
            object_id: "11"
          },
          related_object_kind: "workspace_set_object",
          related_object_id: "51",
          related_object_label: "Primary Workspace Set"
        },
        {
          finding_type: "workspace_source_readiness_warning",
          severity: "warning",
          scope_type: "user",
          scope_id: 7,
          object_kind: "workspace_set_object",
          object_id: "51",
          object_label: "Primary Workspace Set",
          message: "May overlap with another trusted root in multi-root assignments.",
          details: {},
          navigate_to: {
            tab: "workspace-sets",
            object_kind: "workspace_set_object",
            object_id: "51"
          }
        },
        {
          finding_type: "external_server_configuration_issue",
          severity: "error",
          scope_type: "global",
          scope_id: null,
          object_kind: "external_server",
          object_id: "docs-managed",
          object_label: "Docs Managed",
          message: "required_slot_secret_missing",
          details: {},
          navigate_to: {
            tab: "credentials",
            object_kind: "external_server",
            object_id: "docs-managed"
          }
        }
      ],
      total: 3,
      counts: {
        error: 2,
        warning: 1
      }
    })
  })

  it("groups findings by type, filters client-side, and preserves open behavior", async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<GovernanceAuditTab onOpen={onOpen} />)

    expect(await screen.findByText("Assignment blockers")).toBeTruthy()
    expect(screen.getByText("Multi-root readiness")).toBeTruthy()
    expect(screen.getByText("External config")).toBeTruthy()
    expect(screen.getByText("3 findings")).toBeTruthy()
    expect(screen.getByText("2 errors")).toBeTruthy()
    expect(screen.getByText("1 warnings")).toBeTruthy()
    expect(screen.getByText("Related to: Primary Workspace Set (workspace_set_object)")).toBeTruthy()

    const blockerSection = screen.getByTestId("audit-group-assignment_validation_blocker")
    expect(within(blockerSection).getByText("researcher")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Has related object" }))
    expect(screen.getByText("1 findings")).toBeTruthy()
    expect(screen.queryByText("Docs Managed")).toBeNull()
    expect(screen.queryByText("Primary Workspace Set")).toBeNull()
    expect(screen.getByText("researcher")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Has related object" }))
    await user.click(screen.getByRole("button", { name: "All severities" }))
    await user.click(screen.getByRole("button", { name: "Object kind External servers" }))

    expect(screen.getByText("1 findings")).toBeTruthy()
    expect(screen.getByText("Docs Managed")).toBeTruthy()
    expect(screen.queryByText("researcher")).toBeNull()

    await user.click(screen.getByRole("button", { name: /open/i }))
    expect(onOpen).toHaveBeenCalledWith({
      tab: "credentials",
      object_kind: "external_server",
      object_id: "docs-managed"
    })
  })
})
