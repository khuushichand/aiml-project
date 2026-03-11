// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listWorkspaceSetObjects: vi.fn(),
  createWorkspaceSetObject: vi.fn(),
  updateWorkspaceSetObject: vi.fn(),
  deleteWorkspaceSetObject: vi.fn(),
  listSharedWorkspaces: vi.fn(),
  listWorkspaceSetMembers: vi.fn(),
  addWorkspaceSetMember: vi.fn(),
  deleteWorkspaceSetMember: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listWorkspaceSetObjects: (...args: unknown[]) => mocks.listWorkspaceSetObjects(...args),
  createWorkspaceSetObject: (...args: unknown[]) => mocks.createWorkspaceSetObject(...args),
  updateWorkspaceSetObject: (...args: unknown[]) => mocks.updateWorkspaceSetObject(...args),
  deleteWorkspaceSetObject: (...args: unknown[]) => mocks.deleteWorkspaceSetObject(...args),
  listSharedWorkspaces: (...args: unknown[]) => mocks.listSharedWorkspaces(...args),
  listWorkspaceSetMembers: (...args: unknown[]) => mocks.listWorkspaceSetMembers(...args),
  addWorkspaceSetMember: (...args: unknown[]) => mocks.addWorkspaceSetMember(...args),
  deleteWorkspaceSetMember: (...args: unknown[]) => mocks.deleteWorkspaceSetMember(...args)
}))

import { WorkspaceSetsTab } from "../WorkspaceSetsTab"

describe("WorkspaceSetsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listWorkspaceSetObjects.mockResolvedValue([
      {
        id: 51,
        name: "Primary Workspace Set",
        description: "User-scoped reusable workspaces",
        owner_scope_type: "user",
        owner_scope_id: 7,
        is_active: true
      }
    ])
    mocks.listSharedWorkspaces.mockResolvedValue([])
    mocks.listWorkspaceSetMembers.mockResolvedValue([
      {
        workspace_set_object_id: 51,
        workspace_id: "workspace-alpha"
      }
    ])
    mocks.createWorkspaceSetObject.mockResolvedValue({
      id: 52,
      name: "Docs Workspaces",
      owner_scope_type: "user",
      owner_scope_id: 7,
      is_active: true
    })
    mocks.addWorkspaceSetMember.mockResolvedValue({
      workspace_set_object_id: 52,
      workspace_id: "workspace-docs"
    })
    vi.stubGlobal("confirm", vi.fn(() => true))
  })

  it("renders existing workspace sets and creates a new one with members", async () => {
    const user = userEvent.setup()
    render(<WorkspaceSetsTab />)

    expect(await screen.findByText("Primary Workspace Set")).toBeTruthy()
    expect(screen.getByText(/workspace-alpha/i)).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new workspace set/i }))
    await user.type(screen.getByLabelText(/workspace set name/i), "Docs Workspaces")
    await user.type(screen.getByLabelText(/workspace ids/i), "workspace-docs")
    await user.click(screen.getByRole("button", { name: /save workspace set/i }))

    expect(mocks.createWorkspaceSetObject).toHaveBeenCalledWith({
      name: "Docs Workspaces",
      description: null,
      owner_scope_type: "user",
      owner_scope_id: null,
      is_active: true
    })
    expect(mocks.addWorkspaceSetMember).toHaveBeenCalledWith(52, "workspace-docs")
  })
})
