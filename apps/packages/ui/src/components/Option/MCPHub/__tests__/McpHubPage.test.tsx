// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

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

import { McpHubPage } from "../McpHubPage"

describe("McpHubPage", () => {
  it("renders the audit tab alongside the existing MCP Hub tabs", async () => {
    render(<McpHubPage />)

    expect(screen.getByText("Profiles")).toBeTruthy()
    expect(screen.getByText("Assignments")).toBeTruthy()
    expect(screen.getByText("Audit")).toBeTruthy()
  })
})

