import { bgRequest } from "@/services/background-proxy"

export type WritingVersionResponse = {
  version: number
}

export type WritingSessionListItem = {
  id: string
  name: string
  last_modified: string
  version: number
}

export type WritingSessionListResponse = {
  sessions: WritingSessionListItem[]
  total: number
}

export type WritingSessionResponse = {
  id: string
  name: string
  payload: Record<string, unknown>
  schema_version: number
  version_parent_id?: string | null
  created_at: string
  last_modified: string
  deleted: boolean
  client_id: string
  version: number
}

export type WritingTemplateResponse = {
  id: number
  name: string
  payload: Record<string, unknown>
  schema_version: number
  version_parent_id?: string | null
  is_default: boolean
  created_at: string
  last_modified: string
  deleted: boolean
  client_id: string
  version: number
}

export type WritingTemplateListResponse = {
  templates: WritingTemplateResponse[]
  total: number
}

export type WritingThemeResponse = {
  id: number
  name: string
  class_name?: string | null
  className?: string | null
  css?: string | null
  schema_version: number
  version_parent_id?: string | null
  is_default: boolean
  order: number
  created_at: string
  last_modified: string
  deleted: boolean
  client_id: string
  version: number
}

export type WritingThemeListResponse = {
  themes: WritingThemeResponse[]
  total: number
}

export type WritingTokenizerSupport = {
  available: boolean
  tokenizer?: string | null
  error?: string | null
}

export type WritingProviderCapabilities = {
  name: string
  models: string[]
  capabilities: Record<string, unknown>
  supported_fields: string[]
  features: Record<string, boolean>
  tokenizers?: Record<string, WritingTokenizerSupport>
}

export type WritingServerCapabilities = {
  sessions: boolean
  templates: boolean
  themes: boolean
  tokenize: boolean
  token_count: boolean
}

export type WritingRequestedCapabilities = {
  provider: string
  model?: string | null
  supported_fields: string[]
  features: Record<string, boolean>
  tokenizer_available: boolean
  tokenizer?: string | null
  tokenization_error?: string | null
}

export type WritingCapabilitiesResponse = {
  version: number
  server: WritingServerCapabilities
  default_provider?: string | null
  providers?: WritingProviderCapabilities[] | null
  requested?: WritingRequestedCapabilities | null
}

export type WritingTokenizeResponse = {
  ids: number[]
  strings?: string[] | null
  meta: {
    provider: string
    model: string
    tokenizer: string
    input_chars: number
    token_count: number
    warnings?: string[]
  }
}

export type WritingTokenCountResponse = {
  count: number
  meta: {
    provider: string
    model: string
    tokenizer: string
    input_chars: number
    token_count: number
    warnings?: string[]
  }
}

const buildQuery = (params: Record<string, string | number | boolean | undefined>) => {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined)
  if (entries.length === 0) return ""
  const query = entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join("&")
  return `?${query}`
}

export async function getWritingVersion(): Promise<WritingVersionResponse> {
  return await bgRequest<WritingVersionResponse>({
    path: "/api/v1/writing/version",
    method: "GET"
  })
}

export async function getWritingCapabilities(params?: {
  provider?: string
  model?: string
  include_providers?: boolean
  include_deprecated?: boolean
}): Promise<WritingCapabilitiesResponse> {
  const query = buildQuery({
    provider: params?.provider,
    model: params?.model,
    include_providers: params?.include_providers ?? true,
    include_deprecated: params?.include_deprecated
  })
  return await bgRequest<WritingCapabilitiesResponse>({
    path: `/api/v1/writing/capabilities${query}`,
    method: "GET"
  })
}

export async function listWritingSessions(params?: {
  limit?: number
  offset?: number
}): Promise<WritingSessionListResponse> {
  const query = buildQuery({
    limit: params?.limit,
    offset: params?.offset
  })
  return await bgRequest<WritingSessionListResponse>({
    path: `/api/v1/writing/sessions${query}`,
    method: "GET"
  })
}

export async function createWritingSession(payload: {
  name: string
  payload: Record<string, unknown>
  schema_version?: number
  id?: string
  version_parent_id?: string | null
}): Promise<WritingSessionResponse> {
  return await bgRequest<WritingSessionResponse>({
    path: "/api/v1/writing/sessions",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export async function getWritingSession(sessionId: string): Promise<WritingSessionResponse> {
  return await bgRequest<WritingSessionResponse>({
    path: `/api/v1/writing/sessions/${encodeURIComponent(sessionId)}`,
    method: "GET"
  })
}

export async function updateWritingSession(
  sessionId: string,
  payload: {
    name?: string
    payload?: Record<string, unknown>
    schema_version?: number
    version_parent_id?: string | null
  },
  expectedVersion: number
): Promise<WritingSessionResponse> {
  return await bgRequest<WritingSessionResponse>({
    path: `/api/v1/writing/sessions/${encodeURIComponent(sessionId)}`,
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "expected-version": String(expectedVersion)
    },
    body: payload
  })
}

export async function deleteWritingSession(
  sessionId: string,
  expectedVersion: number
): Promise<void> {
  await bgRequest<void>({
    path: `/api/v1/writing/sessions/${encodeURIComponent(sessionId)}`,
    method: "DELETE",
    headers: {
      "expected-version": String(expectedVersion)
    }
  })
}

export async function cloneWritingSession(
  sessionId: string,
  payload?: { name?: string }
): Promise<WritingSessionResponse> {
  return await bgRequest<WritingSessionResponse>({
    path: `/api/v1/writing/sessions/${encodeURIComponent(sessionId)}/clone`,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ?? {}
  })
}

export async function listWritingTemplates(params?: {
  limit?: number
  offset?: number
}): Promise<WritingTemplateListResponse> {
  const query = buildQuery({
    limit: params?.limit,
    offset: params?.offset
  })
  return await bgRequest<WritingTemplateListResponse>({
    path: `/api/v1/writing/templates${query}`,
    method: "GET"
  })
}

export async function createWritingTemplate(payload: {
  name: string
  payload: Record<string, unknown>
  schema_version?: number
  version_parent_id?: string | null
  is_default?: boolean
}): Promise<WritingTemplateResponse> {
  return await bgRequest<WritingTemplateResponse>({
    path: "/api/v1/writing/templates",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export async function updateWritingTemplate(
  name: string,
  payload: {
    name?: string
    payload?: Record<string, unknown>
    schema_version?: number
    version_parent_id?: string | null
    is_default?: boolean
  },
  expectedVersion: number
): Promise<WritingTemplateResponse> {
  return await bgRequest<WritingTemplateResponse>({
    path: `/api/v1/writing/templates/${encodeURIComponent(name)}`,
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "expected-version": String(expectedVersion)
    },
    body: payload
  })
}

export async function deleteWritingTemplate(name: string, expectedVersion: number): Promise<void> {
  await bgRequest<void>({
    path: `/api/v1/writing/templates/${encodeURIComponent(name)}`,
    method: "DELETE",
    headers: {
      "expected-version": String(expectedVersion)
    }
  })
}

export async function listWritingThemes(params?: {
  limit?: number
  offset?: number
}): Promise<WritingThemeListResponse> {
  const query = buildQuery({
    limit: params?.limit,
    offset: params?.offset
  })
  return await bgRequest<WritingThemeListResponse>({
    path: `/api/v1/writing/themes${query}`,
    method: "GET"
  })
}

export async function createWritingTheme(payload: {
  name: string
  class_name?: string | null
  css?: string | null
  schema_version?: number
  version_parent_id?: string | null
  is_default?: boolean
  order?: number
}): Promise<WritingThemeResponse> {
  return await bgRequest<WritingThemeResponse>({
    path: "/api/v1/writing/themes",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export async function updateWritingTheme(
  name: string,
  payload: {
    name?: string
    class_name?: string | null
    css?: string | null
    schema_version?: number
    version_parent_id?: string | null
    is_default?: boolean
    order?: number
  },
  expectedVersion: number
): Promise<WritingThemeResponse> {
  return await bgRequest<WritingThemeResponse>({
    path: `/api/v1/writing/themes/${encodeURIComponent(name)}`,
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "expected-version": String(expectedVersion)
    },
    body: payload
  })
}

export async function deleteWritingTheme(name: string, expectedVersion: number): Promise<void> {
  await bgRequest<void>({
    path: `/api/v1/writing/themes/${encodeURIComponent(name)}`,
    method: "DELETE",
    headers: {
      "expected-version": String(expectedVersion)
    }
  })
}

export async function tokenizeWriting(payload: {
  provider: string
  model: string
  text: string
  options?: { include_strings?: boolean }
}): Promise<WritingTokenizeResponse> {
  return await bgRequest<WritingTokenizeResponse>({
    path: "/api/v1/writing/tokenize",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export async function countWritingTokens(payload: {
  provider: string
  model: string
  text: string
}): Promise<WritingTokenCountResponse> {
  return await bgRequest<WritingTokenCountResponse>({
    path: "/api/v1/writing/token-count",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}
