import type {
  McpHubApprovalMode,
  McpHubAssignmentTargetType,
  McpHubPermissionPolicyDocument,
  McpHubProfileMode,
  McpHubScopeType
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

export const MCP_HUB_CAPABILITY_OPTIONS = [
  "filesystem.read",
  "filesystem.write",
  "filesystem.delete",
  "process.execute",
  "network.external",
  "credentials.use",
  "mcp.server.connect",
  "tool.invoke"
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

export const toggleStringValue = (values: string[], nextValue: string, checked: boolean): string[] => {
  const next = new Set(values)
  if (checked) next.add(nextValue)
  else next.delete(nextValue)
  return Array.from(next)
}

export const buildPolicyDocument = (input: {
  capabilities: string[]
  allowedToolsText: string
  deniedToolsText: string
}): McpHubPermissionPolicyDocument => {
  return {
    capabilities: input.capabilities,
    allowed_tools: parseLineList(input.allowedToolsText),
    denied_tools: parseLineList(input.deniedToolsText)
  }
}
