import { bgRequestClient } from "@/services/background-proxy"
import type { ClientPathOrUrlWithQuery } from "@/services/tldw/openapi-guard"

export type McpHubScopeType = "global" | "org" | "team" | "user"
export type McpHubProfileMode = "preset" | "custom"
export type McpHubAssignmentTargetType = "default" | "group" | "persona"
export type McpHubApprovalMode =
  | "allow_silently"
  | "ask_every_time"
  | "ask_outside_profile"
  | "ask_on_sensitive_actions"
  | "temporary_elevation_allowed"
export type McpHubApprovalDecision = "approved" | "denied"
export type McpHubApprovalDuration = "once" | "session" | "conversation"
export type McpHubToolRiskClass = "low" | "medium" | "high" | "unclassified"
export type McpHubToolMetadataSource = "explicit" | "heuristic" | "fallback"

export type McpHubProfile = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  profile: Record<string, unknown>
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubProfileCreateInput = {
  name: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  profile?: Record<string, unknown>
  is_active?: boolean
}

export type McpHubProfileUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  profile?: Record<string, unknown>
  is_active?: boolean
}

export type McpHubPermissionPolicyDocument = {
  capabilities?: string[]
  allowed_tools?: string[]
  denied_tools?: string[]
  tool_names?: string[]
  tool_patterns?: string[]
  approval_mode?: McpHubApprovalMode | null
}

export type McpHubPermissionProfile = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  mode: McpHubProfileMode
  policy_document: McpHubPermissionPolicyDocument
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubPermissionProfileCreateInput = {
  name: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  mode?: McpHubProfileMode
  policy_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubPermissionProfileUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  mode?: McpHubProfileMode
  policy_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubPolicyAssignment = {
  id: number
  target_type: McpHubAssignmentTargetType
  target_id?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  profile_id?: number | null
  inline_policy_document: McpHubPermissionPolicyDocument
  approval_policy_id?: number | null
  is_active: boolean
  has_override?: boolean
  override_id?: number | null
  override_active?: boolean
  override_updated_at?: string | null
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubPolicyAssignmentCreateInput = {
  target_type: McpHubAssignmentTargetType
  target_id?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  profile_id?: number | null
  inline_policy_document?: McpHubPermissionPolicyDocument
  approval_policy_id?: number | null
  is_active?: boolean
}

export type McpHubPolicyAssignmentUpdateInput = {
  target_type?: McpHubAssignmentTargetType
  target_id?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  profile_id?: number | null
  inline_policy_document?: McpHubPermissionPolicyDocument
  approval_policy_id?: number | null
  is_active?: boolean
}

export type McpHubApprovalPolicy = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  mode: McpHubApprovalMode
  rules: Record<string, unknown>
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubApprovalPolicyCreateInput = {
  name: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  mode: McpHubApprovalMode
  rules?: Record<string, unknown>
  is_active?: boolean
}

export type McpHubApprovalPolicyUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  mode?: McpHubApprovalMode
  rules?: Record<string, unknown>
  is_active?: boolean
}

export type McpHubApprovalDecisionCreateInput = {
  approval_policy_id?: number | null
  context_key: string
  conversation_id?: string | null
  tool_name: string
  scope_key: string
  decision: McpHubApprovalDecision
  duration: McpHubApprovalDuration
}

export type McpHubApprovalDecisionResponse = {
  id: number
  approval_policy_id?: number | null
  context_key: string
  conversation_id?: string | null
  tool_name: string
  scope_key: string
  decision: McpHubApprovalDecision
  consume_on_match: boolean
  expires_at?: string | null
  consumed_at?: string | null
  created_by?: number | null
  created_at?: string | null
}

export type McpHubPolicyOverride = {
  id: number
  assignment_id: number
  override_policy_document: McpHubPermissionPolicyDocument
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubPolicyOverrideUpsertInput = {
  override_policy_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubEffectivePolicySource = {
  assignment_id: number
  target_type: McpHubAssignmentTargetType
  target_id?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  profile_id?: number | null
}

export type McpHubEffectivePolicyProvenance = {
  field: string
  value: unknown
  source_kind: "profile" | "assignment_inline" | "assignment_override"
  assignment_id: number
  profile_id?: number | null
  override_id?: number | null
  effect: "merged" | "replaced"
}

export type McpHubEffectivePolicy = {
  enabled: boolean
  allowed_tools: string[]
  denied_tools: string[]
  capabilities: string[]
  approval_policy_id?: number | null
  approval_mode?: McpHubApprovalMode | null
  policy_document: Record<string, unknown>
  sources: McpHubEffectivePolicySource[]
  provenance: McpHubEffectivePolicyProvenance[]
}

export type McpHubToolRegistryEntry = {
  tool_name: string
  display_name: string
  description?: string | null
  module: string
  module_display_name?: string | null
  category: string
  risk_class: McpHubToolRiskClass
  capabilities: string[]
  mutates_state: boolean
  uses_filesystem: boolean
  uses_processes: boolean
  uses_network: boolean
  uses_credentials: boolean
  supports_arguments_preview: boolean
  path_boundable: boolean
  metadata_source: McpHubToolMetadataSource
  metadata_warnings: string[]
}

export type McpHubToolRegistryModule = {
  module: string
  display_name: string
  tool_count: number
  risk_summary: Record<string, number>
  metadata_warnings: string[]
}

export type McpHubToolRegistrySummary = {
  entries: McpHubToolRegistryEntry[]
  modules: McpHubToolRegistryModule[]
}

export type McpHubExternalServer = {
  id: string
  name: string
  enabled: boolean
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  transport: string
  config: Record<string, unknown>
  secret_configured: boolean
  key_hint?: string | null
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubExternalServerCreateInput = {
  server_id: string
  name: string
  transport: string
  config?: Record<string, unknown>
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  enabled?: boolean
}

export type McpHubExternalServerUpdateInput = {
  name?: string
  transport?: string
  config?: Record<string, unknown>
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  enabled?: boolean
}

export type McpHubSecretSetResponse = {
  server_id: string
  secret_configured: boolean
  key_hint?: string | null
  updated_at?: string | null
}

const withQuery = (
  path: string,
  params: Record<string, string | number | boolean | null | undefined>
): ClientPathOrUrlWithQuery => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) continue
    query.set(key, String(value))
  }
  const qs = query.toString()
  return (qs ? `${path}?${qs}` : path) as ClientPathOrUrlWithQuery
}

export const listAcpProfiles = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubProfile[]> => {
  return await bgRequestClient<McpHubProfile[]>({
    path: withQuery("/api/v1/mcp/hub/acp-profiles", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const createAcpProfile = async (
  payload: McpHubProfileCreateInput
): Promise<McpHubProfile> => {
  return await bgRequestClient<McpHubProfile>({
    path: "/api/v1/mcp/hub/acp-profiles",
    method: "POST",
    body: payload
  })
}

export const updateAcpProfile = async (
  profileId: number,
  payload: McpHubProfileUpdateInput
): Promise<McpHubProfile> => {
  return await bgRequestClient<McpHubProfile>({
    path: `/api/v1/mcp/hub/acp-profiles/${profileId}`,
    method: "PUT",
    body: payload
  })
}

export const deleteAcpProfile = async (
  profileId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/acp-profiles/${profileId}`,
    method: "DELETE"
  })
}

export const listExternalServers = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubExternalServer[]> => {
  return await bgRequestClient<McpHubExternalServer[]>({
    path: withQuery("/api/v1/mcp/hub/external-servers", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const createExternalServer = async (
  payload: McpHubExternalServerCreateInput
): Promise<McpHubExternalServer> => {
  return await bgRequestClient<McpHubExternalServer>({
    path: "/api/v1/mcp/hub/external-servers",
    method: "POST",
    body: payload
  })
}

export const updateExternalServer = async (
  serverId: string,
  payload: McpHubExternalServerUpdateInput
): Promise<McpHubExternalServer> => {
  return await bgRequestClient<McpHubExternalServer>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}`,
    method: "PUT",
    body: payload
  })
}

export const deleteExternalServer = async (
  serverId: string
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}`,
    method: "DELETE"
  })
}

export const setExternalServerSecret = async (
  serverId: string,
  secret: string
): Promise<McpHubSecretSetResponse> => {
  return await bgRequestClient<McpHubSecretSetResponse>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/secret`,
    method: "POST",
    body: { secret }
  })
}

export const listPermissionProfiles = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubPermissionProfile[]> => {
  return await bgRequestClient<McpHubPermissionProfile[]>({
    path: withQuery("/api/v1/mcp/hub/permission-profiles", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const listToolRegistry = async (): Promise<McpHubToolRegistryEntry[]> => {
  return await bgRequestClient<McpHubToolRegistryEntry[]>({
    path: "/api/v1/mcp/hub/tool-registry",
    method: "GET"
  })
}

export const listToolRegistryModules = async (): Promise<McpHubToolRegistryModule[]> => {
  return await bgRequestClient<McpHubToolRegistryModule[]>({
    path: "/api/v1/mcp/hub/tool-registry/modules",
    method: "GET"
  })
}

export const getToolRegistrySummary = async (): Promise<McpHubToolRegistrySummary> => {
  return await bgRequestClient<McpHubToolRegistrySummary>({
    path: "/api/v1/mcp/hub/tool-registry/summary",
    method: "GET"
  })
}

export const createPermissionProfile = async (
  payload: McpHubPermissionProfileCreateInput
): Promise<McpHubPermissionProfile> => {
  return await bgRequestClient<McpHubPermissionProfile>({
    path: "/api/v1/mcp/hub/permission-profiles",
    method: "POST",
    body: payload
  })
}

export const updatePermissionProfile = async (
  profileId: number,
  payload: McpHubPermissionProfileUpdateInput
): Promise<McpHubPermissionProfile> => {
  return await bgRequestClient<McpHubPermissionProfile>({
    path: `/api/v1/mcp/hub/permission-profiles/${profileId}`,
    method: "PUT",
    body: payload
  })
}

export const deletePermissionProfile = async (profileId: number): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/permission-profiles/${profileId}`,
    method: "DELETE"
  })
}

export const listPolicyAssignments = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  target_type?: McpHubAssignmentTargetType
  target_id?: string | null
} = {}): Promise<McpHubPolicyAssignment[]> => {
  return await bgRequestClient<McpHubPolicyAssignment[]>({
    path: withQuery("/api/v1/mcp/hub/policy-assignments", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id,
      target_type: params.target_type,
      target_id: params.target_id
    }),
    method: "GET"
  })
}

export const createPolicyAssignment = async (
  payload: McpHubPolicyAssignmentCreateInput
): Promise<McpHubPolicyAssignment> => {
  return await bgRequestClient<McpHubPolicyAssignment>({
    path: "/api/v1/mcp/hub/policy-assignments",
    method: "POST",
    body: payload
  })
}

export const updatePolicyAssignment = async (
  assignmentId: number,
  payload: McpHubPolicyAssignmentUpdateInput
): Promise<McpHubPolicyAssignment> => {
  return await bgRequestClient<McpHubPolicyAssignment>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}`,
    method: "PUT",
    body: payload
  })
}

export const deletePolicyAssignment = async (
  assignmentId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}`,
    method: "DELETE"
  })
}

export const getPolicyAssignmentOverride = async (
  assignmentId: number
): Promise<McpHubPolicyOverride> => {
  return await bgRequestClient<McpHubPolicyOverride>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/override`,
    method: "GET"
  })
}

export const upsertPolicyAssignmentOverride = async (
  assignmentId: number,
  payload: McpHubPolicyOverrideUpsertInput
): Promise<McpHubPolicyOverride> => {
  return await bgRequestClient<McpHubPolicyOverride>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/override`,
    method: "PUT",
    body: payload
  })
}

export const deletePolicyAssignmentOverride = async (
  assignmentId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/override`,
    method: "DELETE"
  })
}

export const listApprovalPolicies = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubApprovalPolicy[]> => {
  return await bgRequestClient<McpHubApprovalPolicy[]>({
    path: withQuery("/api/v1/mcp/hub/approval-policies", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const createApprovalPolicy = async (
  payload: McpHubApprovalPolicyCreateInput
): Promise<McpHubApprovalPolicy> => {
  return await bgRequestClient<McpHubApprovalPolicy>({
    path: "/api/v1/mcp/hub/approval-policies",
    method: "POST",
    body: payload
  })
}

export const updateApprovalPolicy = async (
  approvalPolicyId: number,
  payload: McpHubApprovalPolicyUpdateInput
): Promise<McpHubApprovalPolicy> => {
  return await bgRequestClient<McpHubApprovalPolicy>({
    path: `/api/v1/mcp/hub/approval-policies/${approvalPolicyId}`,
    method: "PUT",
    body: payload
  })
}

export const deleteApprovalPolicy = async (
  approvalPolicyId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/approval-policies/${approvalPolicyId}`,
    method: "DELETE"
  })
}

export const createApprovalDecision = async (
  payload: McpHubApprovalDecisionCreateInput
): Promise<McpHubApprovalDecisionResponse> => {
  return await bgRequestClient<McpHubApprovalDecisionResponse>({
    path: "/api/v1/mcp/hub/approval-decisions",
    method: "POST",
    body: payload
  })
}

export const getEffectivePolicy = async (params: {
  persona_id?: string | null
  group_id?: string | null
  org_id?: number | null
  team_id?: number | null
} = {}): Promise<McpHubEffectivePolicy> => {
  return await bgRequestClient<McpHubEffectivePolicy>({
    path: withQuery("/api/v1/mcp/hub/effective-policy", {
      persona_id: params.persona_id,
      group_id: params.group_id,
      org_id: params.org_id,
      team_id: params.team_id
    }),
    method: "GET"
  })
}
