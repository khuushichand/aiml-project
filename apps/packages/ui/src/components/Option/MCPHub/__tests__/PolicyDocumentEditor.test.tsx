// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { PolicyDocumentEditor } from "../PolicyDocumentEditor"
import type {
  McpHubToolRegistryEntry,
  McpHubToolRegistryModule
} from "@/services/tldw/mcp-hub"

const REGISTRY_ENTRIES: McpHubToolRegistryEntry[] = [
  {
    tool_name: "files.read",
    display_name: "files.read",
    module: "files",
    category: "search",
    risk_class: "low",
    capabilities: ["filesystem.read"],
    mutates_state: false,
    uses_filesystem: true,
    uses_processes: false,
    uses_network: false,
    uses_credentials: false,
    supports_arguments_preview: true,
    path_boundable: true,
    path_argument_hints: ["path"],
    metadata_source: "explicit",
    metadata_warnings: []
  }
]

const REGISTRY_MODULES: McpHubToolRegistryModule[] = [
  {
    module: "files",
    display_name: "files",
    tool_count: 1,
    risk_summary: { low: 1, medium: 0, high: 0, unclassified: 0 },
    metadata_warnings: []
  }
]

describe("PolicyDocumentEditor", () => {
  it("shows workspace path allowlist controls when path scope is enabled", () => {
    render(
      <PolicyDocumentEditor
        formId="policy-document-editor"
        policy={{
          allowed_tools: ["files.read"],
          capabilities: ["filesystem.read"],
          path_scope_mode: "workspace_root",
          path_scope_enforcement: "approval_required_when_unenforceable",
          path_allowlist_prefixes: ["src"]
        }}
        onChange={() => undefined}
        registryEntries={[...REGISTRY_ENTRIES]}
        registryModules={[...REGISTRY_MODULES]}
      />
    )

    expect(screen.getByText("Allowed workspace paths")).toBeInTheDocument()
  })

  it("clears path allowlist state when local file scope is set back to none", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(
      <PolicyDocumentEditor
        formId="policy-document-editor"
        policy={{
          allowed_tools: ["files.read"],
          capabilities: ["filesystem.read"],
          path_scope_mode: "workspace_root",
          path_scope_enforcement: "approval_required_when_unenforceable",
          path_allowlist_prefixes: ["src"]
        }}
        onChange={onChange}
        registryEntries={[...REGISTRY_ENTRIES]}
        registryModules={[...REGISTRY_MODULES]}
      />
    )

    await user.click(screen.getByLabelText("No additional path restriction"))

    expect(onChange).toHaveBeenCalledWith(
      expect.not.objectContaining({
        path_scope_mode: expect.anything(),
        path_scope_enforcement: expect.anything(),
        path_allowlist_prefixes: expect.anything()
      })
    )
  })
})
