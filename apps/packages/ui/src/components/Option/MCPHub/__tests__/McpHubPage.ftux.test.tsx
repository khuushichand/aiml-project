// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest"
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
  GovernanceAuditTab: () => <div>audit tab</div>
}))
vi.mock("../GovernancePacksTab", () => ({
  GovernancePacksTab: () => <div>governance packs tab</div>
}))
vi.mock("../CapabilityMappingsTab", () => ({
  CapabilityMappingsTab: () => <div>capability mappings tab</div>
}))

import { McpHubPage } from "../McpHubPage"

describe("McpHubPage FTUX", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("renders the subtitle with Model Context Protocol text", () => {
    render(<McpHubPage />)
    expect(screen.getByText(/Model Context Protocol/)).toBeTruthy()
  })

  it("shows the explainer card on first visit", () => {
    render(<McpHubPage />)
    expect(screen.getByTestId("mcp-hub-explainer")).toBeTruthy()
  })

  it("hides the explainer card after dismissal and persists to localStorage", async () => {
    const user = userEvent.setup()
    render(<McpHubPage />)

    const explainer = screen.getByTestId("mcp-hub-explainer")
    expect(explainer).toBeTruthy()

    const closeButton = explainer.querySelector(".ant-alert-close-icon")
    expect(closeButton).toBeTruthy()
    await user.click(closeButton!)

    expect(screen.queryByTestId("mcp-hub-explainer")).toBeNull()
    expect(localStorage.getItem("tldw:mcp-hub:explainer-dismissed")).toBe("true")
  })

  it("does not show the explainer card if previously dismissed", () => {
    localStorage.setItem("tldw:mcp-hub:explainer-dismissed", "true")
    render(<McpHubPage />)
    expect(screen.queryByTestId("mcp-hub-explainer")).toBeNull()
  })

  it("migrates the legacy explainer dismissal key on read", () => {
    localStorage.setItem("tldw_mcp_hub_explainer_dismissed", "true")

    render(<McpHubPage />)

    expect(screen.queryByTestId("mcp-hub-explainer")).toBeNull()
    expect(localStorage.getItem("tldw:mcp-hub:explainer-dismissed")).toBe("true")
    expect(localStorage.getItem("tldw_mcp_hub_explainer_dismissed")).toBeNull()
  })

  it("defaults to the Tool Catalog tab", () => {
    render(<McpHubPage />)
    expect(screen.getByText("catalog tab")).toBeTruthy()
  })

  it("has data-testid attributes on shell and tabs", () => {
    render(<McpHubPage />)
    expect(screen.getByTestId("mcp-hub-shell")).toBeTruthy()
    expect(screen.getByTestId("mcp-hub-tabs")).toBeTruthy()
  })
})
