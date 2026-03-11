import type {
  McpHubApprovalDuration,
  McpHubApprovalMode,
  McpHubAssignmentTargetType,
  McpHubPermissionPolicyDocument,
  McpHubProfileMode,
  McpHubScopeType,
  McpHubToolRegistryEntry,
  McpHubToolRegistryModule
} from "@/services/tldw/mcp-hub"

export const MCP_HUB_SCOPE_OPTIONS: Array<{ label: string; value: McpHubScopeType }> = [
  { label: "Global", value: "global" },
  { label: "Org", value: "org" },
  { label: "Team", value: "team" },
  { label: "User", value: "user" }
]

export const MCP_HUB_PROFILE_MODE_OPTIONS: Array<{ label: string; value: McpHubProfileMode }> = [
  { label: "Custom", value: "custom" },
  { label: "Preset", value: "preset" }
]

export const MCP_HUB_TARGET_OPTIONS: Array<{ label: string; value: McpHubAssignmentTargetType }> = [
  { label: "Default", value: "default" },
  { label: "Group", value: "group" },
  { label: "Persona", value: "persona" }
]

export const MCP_HUB_APPROVAL_MODE_OPTIONS: Array<{ label: string; value: McpHubApprovalMode }> = [
  { label: "Allow silently", value: "allow_silently" },
  { label: "Ask every time", value: "ask_every_time" },
  { label: "Ask outside profile", value: "ask_outside_profile" },
  { label: "Ask on sensitive actions", value: "ask_on_sensitive_actions" },
  { label: "Temporary elevation", value: "temporary_elevation_allowed" }
]

export const MCP_HUB_APPROVAL_DURATION_OPTIONS: Array<{
  label: string
  value: McpHubApprovalDuration
}> = [
  { label: "Once", value: "once" },
  { label: "Session", value: "session" },
  { label: "Conversation", value: "conversation" }
]

export const parseLineList = (value: string): string[] =>
  value
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean)

export const parseCommaList = (value: string): string[] =>
  value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)

export const joinList = (values: string[] | undefined | null, separator = "\n"): string =>
  Array.isArray(values) ? values.filter(Boolean).join(separator) : ""

export const toggleStringValue = (
  values: string[],
  nextValue: string,
  enabled: boolean
): string[] => {
  if (enabled) {
    return Array.from(new Set([...values, nextValue]))
  }

  return values.filter((value) => value !== nextValue)
}

const SIMPLE_POLICY_KEYS = new Set(["allowed_tools", "denied_tools", "capabilities"])

const unique = (values: string[]): string[] => Array.from(new Set(values.filter(Boolean)))

export const getKnownRegistryCapabilities = (entries: McpHubToolRegistryEntry[]): string[] =>
  unique(entries.flatMap((entry) => entry.capabilities || [])).sort()

export const getToolEntriesByModule = (
  entries: McpHubToolRegistryEntry[],
  modules: McpHubToolRegistryModule[]
): Array<McpHubToolRegistryModule & { tools: McpHubToolRegistryEntry[] }> => {
  const byModule = new Map<string, McpHubToolRegistryEntry[]>()
  for (const entry of entries) {
    const existing = byModule.get(entry.module) || []
    existing.push(entry)
    byModule.set(entry.module, existing)
  }
  return modules.map((module) => ({
    ...module,
    tools: [...(byModule.get(module.module) || [])].sort((left, right) =>
      left.display_name.localeCompare(right.display_name)
    )
  }))
}

export const getPolicyAllowedToolSelection = (
  allowedTools: string[] | undefined,
  entries: McpHubToolRegistryEntry[]
): { selectedTools: string[]; preservedPatterns: string[] } => {
  const knownTools = new Set(entries.map((entry) => entry.tool_name))
  const selectedTools: string[] = []
  const preservedPatterns: string[] = []

  for (const toolName of allowedTools || []) {
    if (knownTools.has(toolName)) selectedTools.push(toolName)
    else preservedPatterns.push(toolName)
  }

  return { selectedTools: unique(selectedTools), preservedPatterns: unique(preservedPatterns) }
}

export const getAdvancedPolicyKeys = (policy: McpHubPermissionPolicyDocument): string[] =>
  Object.keys(policy || {}).filter((key) => !SIMPLE_POLICY_KEYS.has(key))

export const getDerivedCapabilities = (
  selectedTools: string[],
  entries: McpHubToolRegistryEntry[],
  existingCapabilities: string[] | undefined
): string[] => {
  const entryMap = new Map(entries.map((entry) => [entry.tool_name, entry]))
  const derived = unique(
    selectedTools.flatMap((toolName) => entryMap.get(toolName)?.capabilities || [])
  )
  const knownCapabilities = new Set(getKnownRegistryCapabilities(entries))
  const preserved = (existingCapabilities || []).filter((capability) => !knownCapabilities.has(capability))
  return unique([...preserved, ...derived]).sort()
}

export const buildSimplePolicyDocument = (input: {
  currentPolicy: McpHubPermissionPolicyDocument
  selectedTools: string[]
  deniedTools: string[]
  registryEntries: McpHubToolRegistryEntry[]
}): McpHubPermissionPolicyDocument => {
  const nextPolicy: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(input.currentPolicy || {})) {
    if (!SIMPLE_POLICY_KEYS.has(key)) {
      nextPolicy[key] = value
    }
  }

  const selection = getPolicyAllowedToolSelection(input.currentPolicy.allowed_tools, input.registryEntries)
  const allowedTools = unique([...input.selectedTools, ...selection.preservedPatterns]).sort()
  const capabilities = getDerivedCapabilities(
    input.selectedTools,
    input.registryEntries,
    input.currentPolicy.capabilities
  )

  nextPolicy.allowed_tools = allowedTools
  nextPolicy.denied_tools = unique(input.deniedTools).sort()
  nextPolicy.capabilities = capabilities

  return nextPolicy as McpHubPermissionPolicyDocument
}

export const createPresetSelection = (
  presetId: "none" | "read_only" | "write_manage" | "process_execution" | "external_services",
  entries: McpHubToolRegistryEntry[]
): { selectedTools: string[] } => {
  if (presetId === "none") {
    return { selectedTools: [] }
  }

  const selectedTools = entries
    .filter((entry) => {
      if (presetId === "read_only") {
        return !entry.mutates_state && !entry.uses_processes && !entry.uses_network && !entry.uses_credentials
      }
      if (presetId === "write_manage") {
        return entry.mutates_state && !entry.uses_processes && !entry.uses_network && !entry.uses_credentials
      }
      if (presetId === "process_execution") {
        return entry.uses_processes || entry.category === "execution"
      }
      if (presetId === "external_services") {
        return entry.uses_network || entry.uses_credentials
      }
      return false
    })
    .map((entry) => entry.tool_name)
    .sort()

  return { selectedTools }
}
