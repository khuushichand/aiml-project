// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
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
          }
        }
      ],
      total: 1,
      counts: {
        error: 1,
        warning: 0
      }
    })
  })

  it("renders audit findings and opens the requested MCP Hub context", async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<GovernanceAuditTab onOpen={onOpen} />)

    expect(await screen.findByText("researcher")).toBeTruthy()
    expect(screen.getByText(/named workspace source contains overlapping roots/i)).toBeTruthy()
    expect(screen.getByText("1 findings")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /open/i }))

    expect(onOpen).toHaveBeenCalledWith({
      tab: "assignments",
      object_kind: "policy_assignment",
      object_id: "11"
    })
  })
})
