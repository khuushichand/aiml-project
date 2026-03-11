// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listPathScopeObjects: vi.fn(),
  createPathScopeObject: vi.fn(),
  updatePathScopeObject: vi.fn(),
  deletePathScopeObject: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listPathScopeObjects: (...args: unknown[]) => mocks.listPathScopeObjects(...args),
  createPathScopeObject: (...args: unknown[]) => mocks.createPathScopeObject(...args),
  updatePathScopeObject: (...args: unknown[]) => mocks.updatePathScopeObject(...args),
  deletePathScopeObject: (...args: unknown[]) => mocks.deletePathScopeObject(...args)
}))

import { PathScopesTab } from "../PathScopesTab"

describe("PathScopesTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    mocks.createPathScopeObject.mockResolvedValue({
      id: 42,
      name: "Src Only",
      owner_scope_type: "global",
      path_scope_document: {
        path_scope_mode: "workspace_root",
        path_allowlist_prefixes: ["src"]
      },
      is_active: true
    })
    mocks.updatePathScopeObject.mockResolvedValue({
      id: 41,
      name: "Docs Only Updated",
      owner_scope_type: "global",
      path_scope_document: {
        path_scope_mode: "workspace_root",
        path_allowlist_prefixes: ["docs/api"]
      },
      is_active: true
    })
    mocks.deletePathScopeObject.mockResolvedValue({ ok: true })
    vi.stubGlobal("confirm", vi.fn(() => true))
  })

  it("renders existing path scopes and creates a new one", async () => {
    const user = userEvent.setup()
    render(<PathScopesTab />)

    expect(await screen.findByText("Docs Only")).toBeTruthy()
    expect(screen.getByText("Workspace root")).toBeTruthy()
    expect(screen.getByText(/allowed paths: docs/i)).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new path scope/i }))
    await user.type(screen.getByLabelText(/path scope name/i), "Src Only")
    await user.click(screen.getByRole("radio", { name: /workspace root/i }))
    await user.type(screen.getByLabelText(/allowed workspace paths/i), "src")
    await user.click(screen.getByRole("button", { name: /save path scope/i }))

    expect(mocks.createPathScopeObject).toHaveBeenCalledWith({
      name: "Src Only",
      description: null,
      owner_scope_type: "global",
      path_scope_document: {
        path_scope_mode: "workspace_root",
        path_scope_enforcement: "approval_required_when_unenforceable",
        path_allowlist_prefixes: ["src"]
      },
      is_active: true
    })
  })
})
