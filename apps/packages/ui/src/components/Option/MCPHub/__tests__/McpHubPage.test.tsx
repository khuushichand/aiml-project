// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

vi.mock("../PermissionProfilesTab", () => ({
  PermissionProfilesTab: () => <div>profiles tab</div>
}))
vi.mock("../PolicyAssignmentsTab", () => ({
  PolicyAssignmentsTab: () => <div>assignments tab</div>
}))
vi.mock("../PathScopesTab", () => ({
  PathScopesTab: () => <div>path scopes tab</div>
}))
vi.mock("../WorkspaceSetsTab", () => ({
  WorkspaceSetsTab: () => <div>workspace sets tab</div>
}))
vi.mock("../SharedWorkspacesTab", () => ({
  SharedWorkspacesTab: () => <div>shared workspaces tab</div>
}))
vi.mock("../ApprovalPoliciesTab", () => ({
  ApprovalPoliciesTab: () => <div>approvals tab</div>
}))
vi.mock("../ToolCatalogsTab", () => ({
  ToolCatalogsTab: () => <div>catalog tab</div>
}))
vi.mock("../ExternalServersTab", () => ({
  ExternalServersTab: () => <div>credentials tab</div>
}))
vi.mock("../GovernanceAuditTab", () => ({
  GovernanceAuditTab: ({ onOpen }: { onOpen?: (target: { tab: string; object_kind: string; object_id: string }) => void }) => (
    <button
      type="button"
      onClick={() =>
        onOpen?.({
          tab: "assignments",
          object_kind: "policy_assignment",
          object_id: "11"
        })
      }
    >
      open assignment from audit
    </button>
  )
}))
vi.mock("../GovernancePacksTab", () => ({
  GovernancePacksTab: () => <div>governance packs tab</div>
}))

import { McpHubPage } from "../McpHubPage"

describe("McpHubPage", () => {
  it("renders the audit tab alongside the existing MCP Hub tabs", async () => {
    render(<McpHubPage />)

    expect(screen.getByText("Profiles")).toBeTruthy()
    expect(screen.getByText("Assignments")).toBeTruthy()
    expect(screen.getByText("Audit")).toBeTruthy()
    expect(screen.getByText("Governance Packs")).toBeTruthy()
  })

  it("opens the requested MCP Hub tab from the audit view", async () => {
    const user = userEvent.setup()
    render(<McpHubPage />)

    await user.click(screen.getByText("Audit"))
    await user.click(screen.getByRole("button", { name: /open assignment from audit/i }))

    expect(screen.getByText("assignments tab")).toBeTruthy()
  })
})
