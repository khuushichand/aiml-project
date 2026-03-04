import { bgRequestClient } from "@/services/background-proxy"
import type { ClientPathOrUrlWithQuery } from "@/services/tldw/openapi-guard"

export type McpHubScopeType = "global" | "org" | "team" | "user"

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
