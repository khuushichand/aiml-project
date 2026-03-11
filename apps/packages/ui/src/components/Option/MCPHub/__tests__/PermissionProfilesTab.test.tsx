// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listPermissionProfiles: vi.fn(),
  createPermissionProfile: vi.fn(),
  getToolRegistrySummary: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listPermissionProfiles: (...args: unknown[]) => mocks.listPermissionProfiles(...args),
  createPermissionProfile: (...args: unknown[]) => mocks.createPermissionProfile(...args),
  getToolRegistrySummary: (...args: unknown[]) => mocks.getToolRegistrySummary(...args)
}))

import { PermissionProfilesTab } from "../PermissionProfilesTab"

describe("PermissionProfilesTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listPermissionProfiles.mockResolvedValue([
      {
        id: 5,
        name: "Process Exec",
        owner_scope_type: "user",
        owner_scope_id: 7,
        mode: "custom",
        policy_document: {
          capabilities: ["process.execute"],
          allowed_tools: ["Bash(git *)"]
        },
        is_active: true
      }
    ])
    mocks.createPermissionProfile.mockResolvedValue({
      id: 6,
      name: "Read Only",
      owner_scope_type: "global",
      owner_scope_id: null,
      mode: "preset",
      policy_document: {
        capabilities: ["filesystem.read"]
      },
      is_active: true
    })
    mocks.getToolRegistrySummary.mockResolvedValue({
      entries: [
        {
          tool_name: "notes.search",
          display_name: "notes.search",
          module: "notes",
          category: "search",
          risk_class: "low",
          capabilities: ["filesystem.read"],
          mutates_state: false,
          uses_filesystem: false,
          uses_processes: false,
          uses_network: false,
          uses_credentials: false,
          supports_arguments_preview: true,
          path_boundable: false,
          metadata_source: "explicit",
          metadata_warnings: []
        }
      ],
      modules: [
        {
          module: "notes",
          display_name: "notes",
          tool_count: 1,
          risk_summary: { low: 1, medium: 0, high: 0, unclassified: 0 },
          metadata_warnings: []
        }
      ]
    })
  })

  it("renders saved permission profiles and opens the create form", async () => {
    const user = userEvent.setup()
    render(<PermissionProfilesTab />)

    expect(await screen.findByText("Process Exec")).toBeTruthy()
    expect(screen.getByText("process.execute")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new profile/i }))
    expect(screen.getByLabelText(/profile name/i)).toBeTruthy()
    expect(screen.getByText(/allowed modules and tools/i)).toBeTruthy()
    expect(screen.getByText(/no additional restrictions/i)).toBeTruthy()
  })
})
