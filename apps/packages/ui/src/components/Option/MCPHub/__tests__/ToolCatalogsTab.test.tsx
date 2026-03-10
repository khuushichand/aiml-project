// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const mocks = vi.hoisted(() => ({
  getToolRegistrySummary: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  getToolRegistrySummary: (...args: unknown[]) => mocks.getToolRegistrySummary(...args)
}))

import { ToolCatalogsTab } from "../ToolCatalogsTab"

describe("ToolCatalogsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it("renders registry-backed module and tool metadata", async () => {
    render(<ToolCatalogsTab />)

    expect(await screen.findByText("notes")).toBeTruthy()
    expect(screen.getByText("notes.search")).toBeTruthy()
    expect(screen.getByText("filesystem.read")).toBeTruthy()
  })
})
