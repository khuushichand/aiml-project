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
export type McpHubPathScopeMode = "none" | "workspace_root" | "cwd_descendants"
export type McpHubPathScopeEnforcement = "approval_required_when_unenforceable"
export type McpHubExternalServerSource = "managed" | "legacy"
export type McpHubCredentialBindingMode = "grant" | "disable"
export type McpHubWorkspaceSourceMode = "inline" | "named"
export type McpHubWorkspaceTrustSource = "user_local" | "shared_registry"
export type McpHubCredentialSlotPrivilegeClass = "read" | "write" | "admin" | "custom" | string

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
  path_scope_mode?: McpHubPathScopeMode | null
  path_scope_enforcement?: McpHubPathScopeEnforcement | null
  path_allowlist_prefixes?: string[]
}

export type McpHubPermissionProfile = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  mode: McpHubProfileMode
  path_scope_object_id?: number | null
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
  path_scope_object_id?: number | null
  policy_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubPermissionProfileUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  mode?: McpHubProfileMode
  path_scope_object_id?: number | null
  policy_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubPathScopeObject = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  path_scope_document: McpHubPermissionPolicyDocument
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubPathScopeObjectCreateInput = {
  name: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  path_scope_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubPathScopeObjectUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  path_scope_document?: McpHubPermissionPolicyDocument
  is_active?: boolean
}

export type McpHubWorkspaceSetObject = {
  id: number
  name: string
  description?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubWorkspaceSetObjectCreateInput = {
  name: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  is_active?: boolean
}

export type McpHubWorkspaceSetObjectUpdateInput = {
  name?: string
  description?: string | null
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
  is_active?: boolean
}

export type McpHubWorkspaceSetObjectMember = {
  workspace_set_object_id: number
  workspace_id: string
  created_by?: number | null
  created_at?: string | null
}

export type McpHubSharedWorkspace = {
  id: number
  workspace_id: string
  display_name: string
  absolute_root: string
  owner_scope_type: "global" | "org" | "team"
  owner_scope_id?: number | null
  is_active: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubSharedWorkspaceCreateInput = {
  workspace_id: string
  display_name: string
  absolute_root: string
  owner_scope_type?: "global" | "org" | "team"
  owner_scope_id?: number | null
  is_active?: boolean
}

export type McpHubSharedWorkspaceUpdateInput = {
  workspace_id?: string
  display_name?: string
  absolute_root?: string
  owner_scope_type?: "global" | "org" | "team"
  owner_scope_id?: number | null
  is_active?: boolean
}

export type McpHubPolicyAssignment = {
  id: number
  target_type: McpHubAssignmentTargetType
  target_id?: string | null
  owner_scope_type: McpHubScopeType
  owner_scope_id?: number | null
  profile_id?: number | null
  path_scope_object_id?: number | null
  workspace_source_mode?: McpHubWorkspaceSourceMode | null
  workspace_set_object_id?: number | null
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
  path_scope_object_id?: number | null
  workspace_source_mode?: McpHubWorkspaceSourceMode | null
  workspace_set_object_id?: number | null
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
  path_scope_object_id?: number | null
  workspace_source_mode?: McpHubWorkspaceSourceMode | null
  workspace_set_object_id?: number | null
  inline_policy_document?: McpHubPermissionPolicyDocument
  approval_policy_id?: number | null
  is_active?: boolean
}

export type McpHubPolicyAssignmentWorkspace = {
  assignment_id: number
  workspace_id: string
  created_by?: number | null
  created_at?: string | null
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
  path_scope_object_id?: number | null
}

export type McpHubEffectivePolicyProvenance = {
  field: string
  value: unknown
  source_kind:
    | "profile"
    | "profile_path_scope_object"
    | "assignment_path_scope_object"
    | "assignment_inline"
    | "assignment_override"
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
  selected_assignment_id?: number | null
  selected_workspace_source_mode?: McpHubWorkspaceSourceMode | null
  selected_workspace_set_object_id?: number | null
  selected_workspace_set_object_name?: string | null
  selected_workspace_trust_source?: McpHubWorkspaceTrustSource | null
  selected_workspace_scope_type?: McpHubScopeType | null
  selected_workspace_scope_id?: number | null
  selected_assignment_workspace_ids?: string[]
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
  path_argument_hints: string[]
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
  server_source?: McpHubExternalServerSource
  legacy_source_ref?: string | null
  superseded_by_server_id?: string | null
  binding_count?: number
  runtime_executable?: boolean
  auth_template_present?: boolean
  auth_template_valid?: boolean
  auth_template_blocked_reason?: string | null
  credential_slots?: McpHubExternalServerCredentialSlot[]
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubExternalServerAuthTemplateTargetType = "header" | "env"

export type McpHubExternalServerAuthTemplateMapping = {
  slot_name: string
  target_type: McpHubExternalServerAuthTemplateTargetType
  target_name: string
  prefix?: string
  suffix?: string
  required?: boolean
}

export type McpHubExternalServerAuthTemplate = {
  mode: "template"
  mappings: McpHubExternalServerAuthTemplateMapping[]
}

export type McpHubExternalServerCredentialSlot = {
  server_id: string
  slot_name: string
  display_name: string
  secret_kind: string
  privilege_class: McpHubCredentialSlotPrivilegeClass
  is_required: boolean
  secret_configured: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubExternalServerCredentialSlotCreateInput = {
  slot_name: string
  display_name: string
  secret_kind: string
  privilege_class: McpHubCredentialSlotPrivilegeClass
  is_required?: boolean
}

export type McpHubExternalServerCredentialSlotUpdateInput = {
  display_name?: string
  secret_kind?: string
  privilege_class?: McpHubCredentialSlotPrivilegeClass
  is_required?: boolean
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

export type McpHubSlotSecretSetResponse = {
  server_id: string
  slot_name: string
  secret_configured: boolean
  key_hint?: string | null
  updated_at?: string | null
}

export type McpHubCredentialBinding = {
  id: number
  binding_target_type: string
  binding_target_id: string
  external_server_id: string
  slot_name?: string | null
  credential_ref: string
  binding_mode: McpHubCredentialBindingMode
  usage_rules: Record<string, unknown>
  created_by?: number | null
  updated_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type McpHubEffectiveExternalAccessEntry = {
  server_id: string
  server_name?: string | null
  granted_by?: string | null
  disabled_by_assignment: boolean
  server_source: McpHubExternalServerSource
  superseded_by_server_id?: string | null
  secret_available: boolean
  runtime_executable: boolean
  blocked_reason?: string | null
  slots: McpHubEffectiveExternalAccessSlot[]
}

export type McpHubEffectiveExternalAccessSlot = {
  slot_name: string
  display_name?: string | null
  granted_by?: string | null
  disabled_by_assignment: boolean
  secret_available: boolean
  runtime_usable: boolean
  blocked_reason?: string | null
}

export type McpHubEffectiveExternalAccess = {
  servers: McpHubEffectiveExternalAccessEntry[]
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

export const importExternalServer = async (
  serverId: string
): Promise<McpHubExternalServer> => {
  return await bgRequestClient<McpHubExternalServer>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/import`,
    method: "POST"
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

export const listExternalServerCredentialSlots = async (
  serverId: string
): Promise<McpHubExternalServerCredentialSlot[]> => {
  return await bgRequestClient<McpHubExternalServerCredentialSlot[]>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots`,
    method: "GET"
  })
}

export const createExternalServerCredentialSlot = async (
  serverId: string,
  payload: McpHubExternalServerCredentialSlotCreateInput
): Promise<McpHubExternalServerCredentialSlot> => {
  return await bgRequestClient<McpHubExternalServerCredentialSlot>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots`,
    method: "POST",
    body: payload
  })
}

export const updateExternalServerCredentialSlot = async (
  serverId: string,
  slotName: string,
  payload: McpHubExternalServerCredentialSlotUpdateInput
): Promise<McpHubExternalServerCredentialSlot> => {
  return await bgRequestClient<McpHubExternalServerCredentialSlot>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots/${encodeURIComponent(slotName)}`,
    method: "PUT",
    body: payload
  })
}

export const deleteExternalServerCredentialSlot = async (
  serverId: string,
  slotName: string
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots/${encodeURIComponent(slotName)}`,
    method: "DELETE"
  })
}

export const setExternalServerSlotSecret = async (
  serverId: string,
  slotName: string,
  secret: string
): Promise<McpHubSlotSecretSetResponse> => {
  return await bgRequestClient<McpHubSlotSecretSetResponse>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots/${encodeURIComponent(slotName)}/secret`,
    method: "POST",
    body: { secret }
  })
}

export const clearExternalServerSlotSecret = async (
  serverId: string,
  slotName: string
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/credential-slots/${encodeURIComponent(slotName)}/secret`,
    method: "DELETE"
  })
}

export const getExternalServerAuthTemplate = async (
  serverId: string
): Promise<McpHubExternalServerAuthTemplate> => {
  return await bgRequestClient<McpHubExternalServerAuthTemplate>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/auth-template`,
    method: "GET"
  })
}

export const updateExternalServerAuthTemplate = async (
  serverId: string,
  payload: McpHubExternalServerAuthTemplate
): Promise<McpHubExternalServerAuthTemplate> => {
  return await bgRequestClient<McpHubExternalServerAuthTemplate>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/auth-template`,
    method: "PUT",
    body: payload
  })
}

export const listProfileCredentialBindings = async (
  profileId: number
): Promise<McpHubCredentialBinding[]> => {
  return await bgRequestClient<McpHubCredentialBinding[]>({
    path: `/api/v1/mcp/hub/permission-profiles/${profileId}/credential-bindings`,
    method: "GET"
  })
}

export const upsertProfileCredentialBinding = async (
  profileId: number,
  serverId: string,
  slotName?: string | null
): Promise<McpHubCredentialBinding> => {
  const suffix = slotName ? `/${encodeURIComponent(slotName)}` : ""
  return await bgRequestClient<McpHubCredentialBinding>({
    path: `/api/v1/mcp/hub/permission-profiles/${profileId}/credential-bindings/${encodeURIComponent(serverId)}${suffix}`,
    method: "PUT"
  })
}

export const deleteProfileCredentialBinding = async (
  profileId: number,
  serverId: string,
  slotName?: string | null
): Promise<{ ok: boolean }> => {
  const suffix = slotName ? `/${encodeURIComponent(slotName)}` : ""
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/permission-profiles/${profileId}/credential-bindings/${encodeURIComponent(serverId)}${suffix}`,
    method: "DELETE"
  })
}

export const listAssignmentCredentialBindings = async (
  assignmentId: number
): Promise<McpHubCredentialBinding[]> => {
  return await bgRequestClient<McpHubCredentialBinding[]>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/credential-bindings`,
    method: "GET"
  })
}

export const upsertAssignmentCredentialBinding = async (
  assignmentId: number,
  serverId: string,
  payload: { binding_mode: McpHubCredentialBindingMode },
  slotName?: string | null
): Promise<McpHubCredentialBinding> => {
  const suffix = slotName ? `/${encodeURIComponent(slotName)}` : ""
  return await bgRequestClient<McpHubCredentialBinding>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/credential-bindings/${encodeURIComponent(serverId)}${suffix}`,
    method: "PUT",
    body: payload
  })
}

export const deleteAssignmentCredentialBinding = async (
  assignmentId: number,
  serverId: string,
  slotName?: string | null
): Promise<{ ok: boolean }> => {
  const suffix = slotName ? `/${encodeURIComponent(slotName)}` : ""
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/credential-bindings/${encodeURIComponent(serverId)}${suffix}`,
    method: "DELETE"
  })
}

export const getAssignmentExternalAccess = async (
  assignmentId: number
): Promise<McpHubEffectiveExternalAccess> => {
  return await bgRequestClient<McpHubEffectiveExternalAccess>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/external-access`,
    method: "GET"
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

export const listPathScopeObjects = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubPathScopeObject[]> => {
  return await bgRequestClient<McpHubPathScopeObject[]>({
    path: withQuery("/api/v1/mcp/hub/path-scope-objects", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const listWorkspaceSetObjects = async (params: {
  owner_scope_type?: McpHubScopeType
  owner_scope_id?: number | null
} = {}): Promise<McpHubWorkspaceSetObject[]> => {
  return await bgRequestClient<McpHubWorkspaceSetObject[]>({
    path: withQuery("/api/v1/mcp/hub/workspace-set-objects", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const listSharedWorkspaces = async (params: {
  owner_scope_type?: "global" | "org" | "team"
  owner_scope_id?: number | null
} = {}): Promise<McpHubSharedWorkspace[]> => {
  return await bgRequestClient<McpHubSharedWorkspace[]>({
    path: withQuery("/api/v1/mcp/hub/shared-workspaces", {
      owner_scope_type: params.owner_scope_type,
      owner_scope_id: params.owner_scope_id
    }),
    method: "GET"
  })
}

export const createSharedWorkspace = async (
  payload: McpHubSharedWorkspaceCreateInput
): Promise<McpHubSharedWorkspace> => {
  return await bgRequestClient<McpHubSharedWorkspace>({
    path: "/api/v1/mcp/hub/shared-workspaces",
    method: "POST",
    body: payload
  })
}

export const updateSharedWorkspace = async (
  sharedWorkspaceId: number,
  payload: McpHubSharedWorkspaceUpdateInput
): Promise<McpHubSharedWorkspace> => {
  return await bgRequestClient<McpHubSharedWorkspace>({
    path: `/api/v1/mcp/hub/shared-workspaces/${sharedWorkspaceId}`,
    method: "PUT",
    body: payload
  })
}

export const deleteSharedWorkspace = async (
  sharedWorkspaceId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/shared-workspaces/${sharedWorkspaceId}`,
    method: "DELETE"
  })
}

export const createWorkspaceSetObject = async (
  payload: McpHubWorkspaceSetObjectCreateInput
): Promise<McpHubWorkspaceSetObject> => {
  return await bgRequestClient<McpHubWorkspaceSetObject>({
    path: "/api/v1/mcp/hub/workspace-set-objects",
    method: "POST",
    body: payload
  })
}

export const updateWorkspaceSetObject = async (
  workspaceSetObjectId: number,
  payload: McpHubWorkspaceSetObjectUpdateInput
): Promise<McpHubWorkspaceSetObject> => {
  return await bgRequestClient<McpHubWorkspaceSetObject>({
    path: `/api/v1/mcp/hub/workspace-set-objects/${workspaceSetObjectId}`,
    method: "PUT",
    body: payload
  })
}

export const deleteWorkspaceSetObject = async (
  workspaceSetObjectId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/workspace-set-objects/${workspaceSetObjectId}`,
    method: "DELETE"
  })
}

export const listWorkspaceSetMembers = async (
  workspaceSetObjectId: number
): Promise<McpHubWorkspaceSetObjectMember[]> => {
  return await bgRequestClient<McpHubWorkspaceSetObjectMember[]>({
    path: `/api/v1/mcp/hub/workspace-set-objects/${workspaceSetObjectId}/members`,
    method: "GET"
  })
}

export const addWorkspaceSetMember = async (
  workspaceSetObjectId: number,
  workspaceId: string
): Promise<McpHubWorkspaceSetObjectMember> => {
  return await bgRequestClient<McpHubWorkspaceSetObjectMember>({
    path: `/api/v1/mcp/hub/workspace-set-objects/${workspaceSetObjectId}/members`,
    method: "POST",
    body: { workspace_id: workspaceId }
  })
}

export const deleteWorkspaceSetMember = async (
  workspaceSetObjectId: number,
  workspaceId: string
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/workspace-set-objects/${workspaceSetObjectId}/members/${encodeURIComponent(workspaceId)}`,
    method: "DELETE"
  })
}

export const createPathScopeObject = async (
  payload: McpHubPathScopeObjectCreateInput
): Promise<McpHubPathScopeObject> => {
  return await bgRequestClient<McpHubPathScopeObject>({
    path: "/api/v1/mcp/hub/path-scope-objects",
    method: "POST",
    body: payload
  })
}

export const updatePathScopeObject = async (
  pathScopeObjectId: number,
  payload: McpHubPathScopeObjectUpdateInput
): Promise<McpHubPathScopeObject> => {
  return await bgRequestClient<McpHubPathScopeObject>({
    path: `/api/v1/mcp/hub/path-scope-objects/${pathScopeObjectId}`,
    method: "PUT",
    body: payload
  })
}

export const deletePathScopeObject = async (
  pathScopeObjectId: number
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/path-scope-objects/${pathScopeObjectId}`,
    method: "DELETE"
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

export const listPolicyAssignmentWorkspaces = async (
  assignmentId: number
): Promise<McpHubPolicyAssignmentWorkspace[]> => {
  return await bgRequestClient<McpHubPolicyAssignmentWorkspace[]>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/workspaces`,
    method: "GET"
  })
}

export const addPolicyAssignmentWorkspace = async (
  assignmentId: number,
  workspaceId: string
): Promise<McpHubPolicyAssignmentWorkspace> => {
  return await bgRequestClient<McpHubPolicyAssignmentWorkspace>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/workspaces`,
    method: "POST",
    body: { workspace_id: workspaceId }
  })
}

export const deletePolicyAssignmentWorkspace = async (
  assignmentId: number,
  workspaceId: string
): Promise<{ ok: boolean }> => {
  return await bgRequestClient<{ ok: boolean }>({
    path: `/api/v1/mcp/hub/policy-assignments/${assignmentId}/workspaces/${encodeURIComponent(workspaceId)}`,
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
