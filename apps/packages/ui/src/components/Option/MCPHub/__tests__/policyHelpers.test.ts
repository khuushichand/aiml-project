import { describe, expect, it } from "vitest"

import type { McpHubToolRegistryEntry } from "@/services/tldw/mcp-hub"

import {
  buildSimplePolicyDocument,
  createPresetSelection,
  getDerivedCapabilities,
  getAdvancedPolicyKeys,
  getExternalBlockedReasonLabel,
  getManagedExternalServers,
  getPolicyAllowedToolSelection
} from "../policyHelpers"

const TOOL_REGISTRY: McpHubToolRegistryEntry[] = [
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
    path_argument_hints: ["path"],
    metadata_source: "explicit",
    metadata_warnings: []
  },
  {
    tool_name: "sandbox.run",
    display_name: "sandbox.run",
    module: "sandbox",
    category: "execution",
    risk_class: "high",
    capabilities: ["process.execute"],
    mutates_state: true,
    uses_filesystem: true,
    uses_processes: true,
    uses_network: false,
    uses_credentials: false,
    supports_arguments_preview: true,
    path_boundable: false,
    path_argument_hints: [],
    metadata_source: "heuristic",
    metadata_warnings: []
  },
  {
    tool_name: "remote.fetch",
    display_name: "remote.fetch",
    module: "remote",
    category: "retrieval",
    risk_class: "medium",
    capabilities: ["network.external"],
    mutates_state: false,
    uses_filesystem: false,
    uses_processes: false,
    uses_network: true,
    uses_credentials: true,
    supports_arguments_preview: true,
    path_boundable: false,
    path_argument_hints: [],
    metadata_source: "heuristic",
    metadata_warnings: []
  }
]

describe("policyHelpers", () => {
  it("builds simple policy documents with exact allowed tools and preserved advanced fields", () => {
    const next = buildSimplePolicyDocument({
      currentPolicy: {
        allowed_tools: ["notes.search", "Bash(git *)"],
        denied_tools: ["sandbox.run"],
        capabilities: ["filesystem.read", "mcp.server.connect"],
        approval_mode: "ask_every_time",
        path_scope_mode: "workspace_root",
        path_scope_enforcement: "approval_required_when_unenforceable"
      },
      selectedTools: ["notes.search", "remote.fetch"],
      deniedTools: ["sandbox.run"],
      registryEntries: TOOL_REGISTRY
    })

    expect(next.allowed_tools).toEqual(["Bash(git *)", "notes.search", "remote.fetch"])
    expect(next.denied_tools).toEqual(["sandbox.run"])
    expect(next.capabilities).toEqual(["filesystem.read", "mcp.server.connect", "network.external"])
    expect(next.approval_mode).toEqual("ask_every_time")
    expect(next.path_scope_mode).toEqual("workspace_root")
    expect(next.path_scope_enforcement).toEqual("approval_required_when_unenforceable")
  })

  it("treats path scope and allowlist fields as guided policy fields rather than advanced keys", () => {
    const advancedKeys = getAdvancedPolicyKeys({
      allowed_tools: ["notes.search"],
      capabilities: ["filesystem.read"],
      path_scope_mode: "workspace_root",
      path_scope_enforcement: "approval_required_when_unenforceable",
      path_allowlist_prefixes: ["src"]
    })

    expect(advancedKeys).not.toContain("path_scope_mode")
    expect(advancedKeys).not.toContain("path_scope_enforcement")
    expect(advancedKeys).not.toContain("path_allowlist_prefixes")
  })

  it("derives read-only presets from registry metadata and preserves pattern separation", () => {
    const preset = createPresetSelection("read_only", TOOL_REGISTRY)
    const selection = getPolicyAllowedToolSelection(["notes.search", "Bash(git *)"], TOOL_REGISTRY)
    const capabilities = getDerivedCapabilities(preset.selectedTools, TOOL_REGISTRY, [])

    expect(preset.selectedTools).toEqual(["notes.search"])
    expect(selection.selectedTools).toEqual(["notes.search"])
    expect(selection.preservedPatterns).toEqual(["Bash(git *)"])
    expect(capabilities).toEqual(["filesystem.read"])
  })

  it("maps external server helpers to managed-only selections and readable blocked reasons", () => {
    const managedServers = getManagedExternalServers([
      {
        id: "docs-managed",
        name: "Docs Managed",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: true,
        server_source: "managed",
        runtime_executable: true
      },
      {
        id: "docs-legacy",
        name: "Docs Legacy",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: false,
        server_source: "legacy",
        runtime_executable: false
      }
    ])

    expect(managedServers.map((server) => server.id)).toEqual(["docs-managed"])
    expect(getExternalBlockedReasonLabel("disabled_by_assignment")).toEqual("Disabled by assignment")
    expect(getExternalBlockedReasonLabel("missing_secret")).toEqual("Missing secret")
  })
})
