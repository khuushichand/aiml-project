import type { ChatScope } from "@/types/chat-scope"
import { toChatScopeParams } from "@/types/chat-scope"
import { Storage } from "@plasmohq/storage"
import { createSafeStorage, safeStorageSerde } from "@/utils/safe-storage"
import { bgRequest, bgStream, bgUpload } from "@/services/background-proxy"
import { isPlaceholderApiKey } from "@/utils/api-key"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import type { AllowedPath, PathOrUrl } from "@/services/tldw/openapi-guard"
import { tldwRequest } from "@/services/tldw/request-core"
import { appendPathQuery } from "@/services/tldw/path-utils"
import { inferUploadMediaTypeFromUrl } from "@/services/tldw/media-routing"
import { captureChatRequestDebugSnapshot } from "@/services/tldw/chat-request-debug"
import { isHostedTldwDeployment } from "@/services/tldw/deployment-mode"
import {
  DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY,
  normalizeDefaultCharacterPreferenceId
} from "@/utils/default-character-preference"
import {
  buildContentPayload,
  mapApiDetailToUi,
  mapApiListToUi,
  mapUiSourceToApi,
  type ApiDataTableGenerateResponse,
  type ApiDataTableJobStatus
} from "@/services/tldw/data-tables"
import type { DataTableColumn } from "@/types/data-tables"
import type {
  CreateReadingSavedSearchRequest,
  CreateReadingDigestScheduleRequest,
  ImportSource,
  ReadingNoteLink,
  ReadingSavedSearch,
  ReadingSavedSearchListResponse,
  ReadingDigestSchedule,
  ReadingImportJobResponse,
  ReadingImportJobStatus,
  ReadingImportJobsListResponse,
  UpdateReadingSavedSearchRequest,
  UpdateReadingDigestScheduleRequest
} from "@/types/collections"
import type {
  CreateIngestionSourceRequest,
  IngestionSourceItem,
  IngestionSourceItemFilters,
  IngestionSourceItemsListResponse,
  IngestionSourceListResponse,
  IngestionSourceSummary,
  IngestionSourceSyncSummary,
  IngestionSourceSyncTriggerResponse,
  UpdateIngestionSourceRequest
} from "@/types/ingestion-sources"

const DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
const CHARACTER_CACHE_TTL_MS = 5 * 60 * 1000
const CHAT_MESSAGES_CACHE_TTL_MS = 60 * 1000
const RAG_QUERY_MAX_LENGTH = 20000

export export const normalizeReadingDigestSchedule = (schedule: any): ReadingDigestSchedule => ({
  ...schedule,
  id: String(schedule?.id ?? ""),
  name: schedule?.name ?? null,
  cron: String(schedule?.cron ?? ""),
  timezone: schedule?.timezone ?? null,
  enabled: Boolean(schedule?.enabled),
  require_online: Boolean(schedule?.require_online),
  format: schedule?.format === "html" ? "html" : "md",
  template_id:
    typeof schedule?.template_id === "number" && Number.isFinite(schedule.template_id)
      ? schedule.template_id
      : null,
  template_name: schedule?.template_name ?? null,
  retention_days:
    typeof schedule?.retention_days === "number" && Number.isFinite(schedule.retention_days)
      ? schedule.retention_days
      : null,
  filters:
    schedule?.filters && typeof schedule.filters === "object" && !Array.isArray(schedule.filters)
      ? schedule.filters
      : null,
  last_run_at: schedule?.last_run_at ?? null,
  next_run_at: schedule?.next_run_at ?? null,
  last_status: schedule?.last_status ?? null,
  created_at: schedule?.created_at ?? null,
  updated_at: schedule?.updated_at ?? null
})

export export const toFiniteNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

export export const toOptionalString = (value: unknown): string | null => {
  if (value === null || typeof value === "undefined") {
    return null
  }
  return String(value)
}

export export const toRecord = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {}
  }
  return { ...(value as Record<string, unknown>) }
}

const toOptionalNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0)
    .map((entry) => entry.trim())
}

export export const normalizeIngestionSourceSyncSummary = (
  summary: unknown
): IngestionSourceSyncSummary | null => {
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) {
    return null
  }
  const record = summary as Record<string, unknown>
  return {
    changed_count: toFiniteNumber(record.changed_count),
    degraded_count: toFiniteNumber(record.degraded_count),
    conflict_count: toFiniteNumber(record.conflict_count),
    sink_failure_count: toFiniteNumber(record.sink_failure_count),
    ingestion_failure_count: toFiniteNumber(record.ingestion_failure_count),
    created_count: toFiniteNumber(record.created_count),
    updated_count: toFiniteNumber(record.updated_count),
    deleted_count: toFiniteNumber(record.deleted_count),
    unchanged_count: toFiniteNumber(record.unchanged_count)
  }
}

export export const normalizeIngestionSourceType = (value: unknown): IngestionSourceSummary["source_type"] => {
  if (value === "archive_snapshot" || value === "git_repository") {
    return value
  }
  return "local_directory"
}

export export const normalizeIngestionSource = (source: any): IngestionSourceSummary => ({
  id: String(source?.id ?? ""),
  user_id: toFiniteNumber(source?.user_id),
  source_type: normalizeIngestionSourceType(source?.source_type),
  sink_type: source?.sink_type === "notes" ? "notes" : "media",
  policy: source?.policy === "import_only" ? "import_only" : "canonical",
  enabled: Boolean(source?.enabled),
  schedule_enabled: Boolean(source?.schedule_enabled),
  schedule_config: toRecord(source?.schedule_config),
  config: toRecord(source?.config),
  active_job_id: toOptionalString(source?.active_job_id),
  last_successful_snapshot_id: toOptionalString(source?.last_successful_snapshot_id),
  last_sync_started_at: toOptionalString(source?.last_sync_started_at),
  last_sync_completed_at: toOptionalString(source?.last_sync_completed_at),
  last_sync_status: toOptionalString(source?.last_sync_status),
  last_error: toOptionalString(source?.last_error),
  last_successful_sync_summary: normalizeIngestionSourceSyncSummary(
    source?.last_successful_sync_summary
  ),
  created_at: toOptionalString(source?.created_at),
  updated_at: toOptionalString(source?.updated_at)
})

export export const normalizeIngestionSourceListResponse = (payload: any): IngestionSourceListResponse => {
  const rawSources = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.sources)
      ? payload.sources
      : []
  const sources = rawSources.map((source: any) => normalizeIngestionSource(source))
  return {
    sources,
    total: toFiniteNumber(payload?.total, sources.length)
  }
}

export export const normalizeIngestionSourceItem = (item: any): IngestionSourceItem => ({
  id: String(item?.id ?? ""),
  source_id: String(item?.source_id ?? ""),
  normalized_relative_path: String(item?.normalized_relative_path ?? ""),
  content_hash: item?.content_hash == null ? null : String(item.content_hash),
  sync_status: String(item?.sync_status ?? "unknown"),
  binding: toRecord(item?.binding),
  present_in_source: Boolean(item?.present_in_source),
  created_at: toOptionalString(item?.created_at),
  updated_at: toOptionalString(item?.updated_at)
})

export export const normalizeIngestionSourceItemsListResponse = (
  payload: any
): IngestionSourceItemsListResponse => {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : []
  const items = rawItems.map((item: any) => normalizeIngestionSourceItem(item))
  return {
    items,
    total: toFiniteNumber(payload?.total, items.length)
  }
}

export export const normalizeIngestionSourceSyncTrigger = (
  payload: any
): IngestionSourceSyncTriggerResponse => ({
  status: String(payload?.status ?? ""),
  source_id: String(payload?.source_id ?? ""),
  job_id: toOptionalString(payload?.job_id),
  snapshot_status: toOptionalString(payload?.snapshot_status)
})

export interface TldwConfig {
  serverUrl: string
  apiKey?: string
  accessToken?: string
  refreshToken?: string
  orgId?: number
  authMode: 'single-user' | 'multi-user'
}

export interface CurrentUserStorageQuotaResponse {
  user_id: number
  storage_used_mb: number
  storage_quota_mb: number
  available_mb: number
  usage_percentage: number
}

export interface OpenAIOAuthAuthorizeRequest {
  credential_fields?: Record<string, unknown>
  return_path?: string
}

export interface OpenAIOAuthAuthorizeResponse {
  provider: "openai"
  auth_url: string
  auth_session_id: string
  expires_at: string
}

export interface OpenAIOAuthStatusResponse {
  provider: "openai"
  connected: boolean
  auth_source: "api_key" | "oauth" | "none"
  updated_at?: string | null
  last_used_at?: string | null
  expires_at?: string | null
  scope?: string | null
}

export interface OpenAIOAuthRefreshResponse {
  provider: "openai"
  status: string
  updated_at?: string | null
  expires_at?: string | null
}

export interface OpenAICredentialSourceSwitchResponse {
  provider: "openai"
  auth_source: "api_key" | "oauth"
  updated_at?: string | null
}

export type PresentationStudioSlide = {
  order: number
  layout: string
  title?: string | null
  content: string
  speaker_notes?: string | null
  metadata: Record<string, any>
}

export type PresentationVisualStyleSnapshot = {
  id: string
  scope: string
  name: string
  description?: string | null
  generation_rules?: Record<string, any>
  artifact_preferences?: string[]
  appearance_defaults?: Record<string, any>
  fallback_policy?: Record<string, any>
  version?: number | null
}

export type VisualStyleRecord = {
  id: string
  name: string
  scope: string
  description?: string | null
  generation_rules: Record<string, any>
  artifact_preferences: string[]
  appearance_defaults: Record<string, any>
  fallback_policy: Record<string, any>
  version?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export type VisualStyleCreateInput = {
  name: string
  description?: string | null
  generation_rules?: Record<string, any>
  artifact_preferences?: string[]
  appearance_defaults?: Record<string, any>
  fallback_policy?: Record<string, any>
}

export type VisualStylePatchInput = {
  name?: string | null
  description?: string | null
  generation_rules?: Record<string, any> | null
  artifact_preferences?: string[] | null
  appearance_defaults?: Record<string, any> | null
  fallback_policy?: Record<string, any> | null
}

const cloneVisualStyleValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => cloneVisualStyleValue(item))
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, entryValue]) => [
        key,
        cloneVisualStyleValue(entryValue)
      ])
    )
  }
  return value
}

const cloneVisualStyleObject = (value: Record<string, any> | null | undefined): Record<string, any> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (cloneVisualStyleValue(value) as Record<string, any>)
    : {}

export const clonePresentationVisualStyleSnapshot = (
  snapshot: PresentationVisualStyleSnapshot | null | undefined
): PresentationVisualStyleSnapshot | null => {
  if (!snapshot) {
    return null
  }
  return {
    id: snapshot.id,
    scope: snapshot.scope,
    name: snapshot.name,
    description: snapshot.description ?? null,
    generation_rules: cloneVisualStyleObject(snapshot.generation_rules),
    artifact_preferences: [...(snapshot.artifact_preferences || [])],
    appearance_defaults: cloneVisualStyleObject(snapshot.appearance_defaults),
    fallback_policy: cloneVisualStyleObject(snapshot.fallback_policy),
    version: snapshot.version ?? null
  }
}

export const buildPresentationVisualStyleSnapshot = (
  style: Pick<
    VisualStyleRecord,
    | "id"
    | "scope"
    | "name"
    | "description"
    | "generation_rules"
    | "artifact_preferences"
    | "appearance_defaults"
    | "fallback_policy"
    | "version"
  >
): PresentationVisualStyleSnapshot =>
  clonePresentationVisualStyleSnapshot({
    id: style.id,
    scope: style.scope,
    name: style.name,
    description: style.description ?? null,
    generation_rules: cloneVisualStyleObject(style.generation_rules),
    artifact_preferences: [...(style.artifact_preferences || [])],
    appearance_defaults: cloneVisualStyleObject(style.appearance_defaults),
    fallback_policy: cloneVisualStyleObject(style.fallback_policy),
    version: style.version ?? null
  })!

export type PresentationStudioRecord = {
  id: string
  title: string
  description?: string | null
  theme: string
  marp_theme?: string | null
  template_id?: string | null
  visual_style_id?: string | null
  visual_style_scope?: string | null
  visual_style_name?: string | null
  visual_style_version?: number | null
  visual_style_snapshot?: PresentationVisualStyleSnapshot | null
  settings?: Record<string, any> | null
  studio_data?: Record<string, any> | null
  slides: PresentationStudioSlide[]
  custom_css?: string | null
  source_type?: string | null
  source_ref?: unknown
  source_query?: string | null
  created_at: string
  last_modified: string
  deleted?: boolean
  client_id?: string
  version: number
}

export type PresentationRenderFormat = "mp4" | "webm"

export type PresentationRenderJob = {
  job_id: number
  status: string
  job_type: string
  presentation_id?: string | null
  presentation_version?: number | null
  format?: PresentationRenderFormat | null
  output_id?: number | null
  download_url?: string | null
  error?: string | null
}

export type PresentationRenderArtifact = {
  output_id: number
  format: PresentationRenderFormat
  title?: string | null
  download_url: string
  presentation_version?: number | null
  created_at?: string | null
}

export type PresentationRenderArtifactList = {
  presentation_id: string
  artifacts: PresentationRenderArtifact[]
}

const normalizeVisualStyleSnapshot = (
  value: unknown
): PresentationVisualStyleSnapshot | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null
  }
  const snapshot = value as Record<string, unknown>
  const id = String(snapshot.id ?? "").trim()
  const scope = String(snapshot.scope ?? "").trim()
  const name = String(snapshot.name ?? "").trim()
  if (!id || !scope || !name) {
    return null
  }
  return clonePresentationVisualStyleSnapshot({
    id,
    scope,
    name,
    description: toOptionalString(snapshot.description),
    generation_rules: toRecord(snapshot.generation_rules),
    artifact_preferences: toStringArray(snapshot.artifact_preferences),
    appearance_defaults: toRecord(snapshot.appearance_defaults),
    fallback_policy: toRecord(snapshot.fallback_policy),
    version: toOptionalNumber(snapshot.version)
  })
}

const normalizeVisualStyleRecord = (style: unknown): VisualStyleRecord => {
  const record = style && typeof style === "object" && !Array.isArray(style)
    ? (style as Record<string, unknown>)
    : {}
  return {
    id: String(record.id ?? ""),
    name: String(record.name ?? ""),
    scope: String(record.scope ?? ""),
    description: toOptionalString(record.description),
    generation_rules: toRecord(record.generation_rules),
    artifact_preferences: toStringArray(record.artifact_preferences),
    appearance_defaults: toRecord(record.appearance_defaults),
    fallback_policy: toRecord(record.fallback_policy),
    version: toOptionalNumber(record.version),
    created_at: toOptionalString(record.created_at),
    updated_at: toOptionalString(record.updated_at)
  }
}

const normalizePresentationStudioRecord = (presentation: unknown): PresentationStudioRecord => {
  const record =
    presentation && typeof presentation === "object" && !Array.isArray(presentation)
      ? (presentation as Record<string, unknown>)
      : {}
  const slides = Array.isArray(record.slides)
    ? (record.slides as PresentationStudioSlide[])
    : []
  return {
    id: String(record.id ?? ""),
    title: String(record.title ?? ""),
    description: toOptionalString(record.description),
    theme: String(record.theme ?? "black"),
    marp_theme: toOptionalString(record.marp_theme),
    template_id: toOptionalString(record.template_id),
    visual_style_id: toOptionalString(record.visual_style_id),
    visual_style_scope: toOptionalString(record.visual_style_scope),
    visual_style_name: toOptionalString(record.visual_style_name),
    visual_style_version: toOptionalNumber(record.visual_style_version),
    visual_style_snapshot: normalizeVisualStyleSnapshot(record.visual_style_snapshot),
    settings: Object.keys(toRecord(record.settings)).length > 0 ? toRecord(record.settings) : null,
    studio_data:
      Object.keys(toRecord(record.studio_data)).length > 0 ? toRecord(record.studio_data) : null,
    slides,
    custom_css: toOptionalString(record.custom_css),
    source_type: toOptionalString(record.source_type),
    source_ref: record.source_ref ?? null,
    source_query: toOptionalString(record.source_query),
    created_at: String(record.created_at ?? ""),
    last_modified: String(record.last_modified ?? ""),
    deleted: Boolean(record.deleted),
    client_id: toOptionalString(record.client_id) ?? undefined,
    version: toFiniteNumber(record.version, 0)
  }
}

export type UserProfileUpdateEntry = {
  key: string
  value: unknown | null
}

export type UserProfileUpdateResponse = {
  profile_version?: string
  applied: string[]
  skipped: Array<{ key: string; message: string }>
}

export interface TldwModel {
  id: string
  name: string
  provider: string
  description?: string
  capabilities?: string[] | Record<string, unknown>
  context_length?: number
  vision?: boolean
  function_calling?: boolean
  json_output?: boolean
  type?: string
  modalities?: {
    input?: string[]
    output?: string[]
  }
}

export type ChatCompletionContentPartText = {
  type: "text"
  text: string
}

export type ChatCompletionContentPartImage = {
  type: "image_url"
  image_url: {
    url: string
    detail?: "auto" | "low" | "high" | null
  }
}

export type ChatCompletionContentPart =
  | ChatCompletionContentPartText
  | ChatCompletionContentPartImage

export type ChatCompletionUserContent = string | ChatCompletionContentPart[]

export type ChatCompletionAssistantContent = string | null

export type ChatCompletionToolCall = {
  id: string
  type: "function"
  function: {
    name: string
    arguments?: string | null
    parameters?: Record<string, unknown> | null
    description?: string | null
  }
}

export type FunctionCall = {
  name: string
  arguments: string
}

export type ChatMessage =
  | {
      role: "system"
      content: string
      name?: string | null
    }
  | {
      role: "user"
      content: ChatCompletionUserContent
      name?: string | null
    }
  | {
      role: "assistant"
      content: ChatCompletionAssistantContent
      name?: string | null
      tool_calls?: ChatCompletionToolCall[] | null
      function_call?: FunctionCall | null
    }
  | {
      role: "tool"
      content: string
      tool_call_id: string
      name?: string | null
    }

export interface ChatCompletionRequest {
  messages: ChatMessage[]
  model: string
  routing?: {
    strategy?: "llm_router" | "rules_router"
    objective?: "highest_quality" | "lowest_cost" | "lowest_latency" | "balanced"
    mode?: "per_turn" | "sticky_session"
    cross_provider?: boolean
    failure_mode?: "fallback_then_error" | "error"
  }
  stream?: boolean
  temperature?: number
  logprobs?: boolean
  top_logprobs?: number
  max_tokens?: number
  top_p?: number
  frequency_penalty?: number
  presence_penalty?: number
  reasoning_effort?: "low" | "medium" | "high"
  tool_choice?: "auto" | "none" | "required"
  tools?: Record<string, unknown>[]
  save_to_db?: boolean
  conversation_id?: string
  history_message_limit?: number
  history_message_order?: string
  slash_command_injection_mode?: string
  api_provider?: string
  extra_headers?: Record<string, unknown>
  extra_body?: Record<string, unknown>
  thinking_budget_tokens?: number
  grammar_mode?: "none" | "library" | "inline"
  grammar_id?: string
  grammar_inline?: string
  grammar_override?: string
  response_format?: { type: "json_object" | "text" }
}

export interface ServerChatSummary {
  id: string
  title: string
  created_at: string
  updated_at?: string | null
  last_active?: string | null
  message_count?: number | null
  source?: string | null
  state?: ConversationState | string | null
  topic_label?: string | null
  cluster_id?: string | null
  external_ref?: string | null
  bm25_norm?: number | null
  character_id?: string | number | null
  assistant_kind?: "character" | "persona" | null
  assistant_id?: string | null
  persona_memory_mode?: "read_only" | "read_write" | null
  parent_conversation_id?: string | null
  root_id?: string | null
  forked_from_message_id?: string | null
  version?: number | null
  scope_type?: "global" | "workspace" | null
  workspace_id?: string | null
}

export interface PersonaProfileSummary {
  id: string
  name?: string | null
  character_card_id?: number | null
  origin_character_id?: number | null
  [key: string]: unknown
}

export interface PersonaProfile extends PersonaProfileSummary {
  mode?: string | null
  system_prompt?: string | null
  use_persona_state_context_default?: boolean
}

export interface PersonaExemplar {
  id: string
  persona_id: string
  kind: string
  content: string
  tone?: string | null
  scenario_tags: string[]
  capability_tags: string[]
  priority: number
  enabled: boolean
  source_type?: string | null
  source_ref?: string | null
  notes?: string | null
  created_at?: string | null
  last_modified?: string | null
}

export type PersonaExemplarInput = {
  kind: string
  content: string
  tone?: string | null
  scenario_tags?: string[]
  capability_tags?: string[]
  priority?: number
  enabled?: boolean
  source_type?: string | null
  source_ref?: string | null
  notes?: string | null
}

export type PersonaExemplarListOptions = {
  includeDisabled?: boolean
  includeDeleted?: boolean
  includeDeletedPersonas?: boolean
}

export type PersonaExemplarImportInput = {
  transcript: string
  source_ref?: string | null
  notes?: string | null
  max_candidates?: number
}

export type PersonaExemplarReviewInput = {
  action: "approve" | "reject"
  notes?: string | null
}

export type ConversationSharePermission = "view"

export interface ConversationShareLinkSummary {
  id: string
  permission: ConversationSharePermission
  created_at: string
  expires_at: string
  revoked_at?: string | null
  share_path?: string | null
  token?: string | null
}

export interface ConversationShareLinkCreateResponse {
  share_id: string
  permission: ConversationSharePermission
  created_at: string
  expires_at: string
  token: string
  share_path: string
}

export interface ConversationShareLinksListResponse {
  conversation_id: string
  links: ConversationShareLinkSummary[]
}

export interface ConversationShareLinkResolveResponse {
  conversation_id: string
  title?: string | null
  source?: string | null
  permission: ConversationSharePermission
  shared_by_user_id: string
  expires_at: string
  messages: any[]
}

export type ConversationState =
  | "in-progress"
  | "resolved"
  | "backlog"
  | "non-viable"

export interface ServerChatMessage {
  id: string
  role: "system" | "user" | "assistant"
  sender?: string
  content: string
  created_at: string
  version?: number
  metadata_extra?: Record<string, unknown>
  pinned?: boolean
}

export type ChatSettingsResponse = {
  conversation_id: string
  settings: Record<string, unknown>
  last_modified: string
}

export const normalizePersonaProfile = <T extends Record<string, unknown>>(
  input: T | null | undefined
): PersonaProfile => {
  const candidate = input && typeof input === "object" ? input : ({} as T)
  return {
    ...candidate,
    id: String(candidate?.id ?? candidate?.persona_id ?? "")
  }
}

export const normalizeStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => String(item ?? "").trim())
    .filter((item) => item.length > 0)
}

export const normalizePersonaExemplar = (
  input: Record<string, unknown> | null | undefined
): PersonaExemplar => {
  const candidate = input && typeof input === "object" ? input : {}
  const priorityValue = Number(candidate?.priority)
  return {
    id: String(candidate?.id ?? ""),
    persona_id: String(candidate?.persona_id ?? candidate?.personaId ?? ""),
    kind: String(candidate?.kind ?? "style"),
    content: String(candidate?.content ?? ""),
    tone:
      candidate?.tone == null || String(candidate.tone).trim() === ""
        ? null
        : String(candidate.tone),
    scenario_tags: normalizeStringArray(
      candidate?.scenario_tags ?? candidate?.scenarioTags
    ),
    capability_tags: normalizeStringArray(
      candidate?.capability_tags ?? candidate?.capabilityTags
    ),
    priority: Number.isFinite(priorityValue) ? priorityValue : 0,
    enabled: candidate?.enabled !== false,
    source_type:
      candidate?.source_type == null || String(candidate.source_type).trim() === ""
        ? null
        : String(candidate.source_type),
    source_ref:
      candidate?.source_ref == null || String(candidate.source_ref).trim() === ""
        ? null
        : String(candidate.source_ref),
    notes:
      candidate?.notes == null || String(candidate.notes).trim() === ""
        ? null
        : String(candidate.notes),
    created_at:
      candidate?.created_at == null ? null : String(candidate.created_at),
    last_modified:
      candidate?.last_modified == null ? null : String(candidate.last_modified)
  }
}

export type WorldBookProcessDiagnostic = {
  entry_id: number | null
  world_book_id: number | null
  activation_reason: "keyword_match" | "regex_match" | "depth" | string
  keyword?: string | null
  token_cost: number
  priority: number
  regex_match: boolean
  content_preview: string
  depth_level?: number | null
}

export type WorldBookProcessResponse = {
  injected_content: string
  entries_matched: number
  tokens_used: number
  books_used: number
  entry_ids: number[]
  token_budget?: number | null
  budget_exhausted?: boolean | null
  skipped_entries_due_to_budget?: number | null
  diagnostics: WorldBookProcessDiagnostic[]
}

export type LorebookDiagnosticTurn = {
  message_id: string
  timestamp?: string | null
  turn_number: number
  message_preview: string
  diagnostics: Record<string, unknown>[]
}

export type LorebookDiagnosticExportResponse = {
  chat_id: string
  character_id?: string | null
  total_turns_with_diagnostics: number
  turns: LorebookDiagnosticTurn[]
  page: number
  size: number
}

export type PromptPayload = {
  name?: string
  title?: string
  author?: string
  details?: string
  system_prompt?: string | null
  user_prompt?: string | null
  keywords?: string[]
  content?: string
  is_system?: boolean
}

export type FileArtifactExport = {
  status?: "none" | "ready" | "pending"
  format?: "ics" | "md" | "html" | "xlsx" | "csv" | "json" | "png" | "jpg" | "webp"
  url?: string | null
  content_type?: string | null
  bytes?: number | null
  job_id?: string | null
  content_b64?: string | null
  expires_at?: string | null
}

export type FileArtifact = {
  file_id: number
  file_type: string
  title: string
  structured?: Record<string, unknown>
  export?: FileArtifactExport
  created_at?: string
  updated_at?: string
}

export type FileCreateResponse = {
  artifact: FileArtifact
}

export type ImageArtifactRequest = {
  backend: string
  prompt: string
  negativePrompt?: string
  width?: number
  height?: number
  steps?: number
  cfgScale?: number
  seed?: number
  sampler?: string
  model?: string
  extraParams?: Record<string, unknown>
  format?: "png" | "jpg" | "webp"
  title?: string
  persist?: boolean
  timeoutMs?: number
}

export interface ImageBackend {
  id: string
  name: string
  is_configured: boolean
  supported_formats?: string[]
}

export interface TldwEmbeddingModel {
  provider: string
  model: string
  allowed?: boolean
  default?: boolean
}

export interface TldwEmbeddingModelsResponse {
  data?: TldwEmbeddingModel[]
  allowed_providers?: string[] | null
  allowed_models?: string[] | null
}

export interface TldwEmbeddingProvidersConfig {
  default_provider: string
  default_model: string
  providers: {
    name: string
    models: string[]
  }[]
}

export type CharacterListSortBy =
  | "name"
  | "creator"
  | "created_at"
  | "updated_at"
  | "last_used_at"
  | "conversation_count"

export type CharacterListSortOrder = "asc" | "desc"

export interface CharacterListQueryParams {
  page?: number
  page_size?: number
  query?: string
  tags?: string[]
  match_all_tags?: boolean
  creator?: string
  has_conversations?: boolean
  favorite_only?: boolean
  created_from?: string
  created_to?: string
  updated_from?: string
  updated_to?: string
  sort_by?: CharacterListSortBy
  sort_order?: CharacterListSortOrder
  include_image_base64?: boolean
  include_deleted?: boolean
  deleted_only?: boolean
}

export interface CharacterListQueryResponse {
  items: any[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface CharacterVersionEntry {
  change_id: number
  version: number
  operation: string
  timestamp?: string | null
  client_id?: string | null
  payload: Record<string, unknown>
}

export interface CharacterVersionListResponse {
  items: CharacterVersionEntry[]
  total: number
}

export interface CharacterVersionDiffField {
  field: string
  old_value: unknown
  new_value: unknown
}

export interface CharacterVersionDiffResponse {
  character_id: number
  from_entry: CharacterVersionEntry
  to_entry: CharacterVersionEntry
  changed_fields: CharacterVersionDiffField[]
  changed_count: number
}

// Admin / RBAC types
export interface AdminUserSummary {
  id: number
  uuid: string
  username: string
  email: string
  role: string
  is_active: boolean
  is_verified: boolean
  created_at: string
  last_login?: string | null
  storage_quota_mb: number
  storage_used_mb: number
}

export interface AdminUserListResponse {
  users: AdminUserSummary[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface AdminUserUpdateRequest {
  email?: string
  role?: string
  is_active?: boolean
  is_verified?: boolean
  is_locked?: boolean
  storage_quota_mb?: number
}

export interface AdminRole {
  id: number
  name: string
  description?: string | null
  is_system?: boolean
}

// MLX admin types
export interface MlxStatusConfig {
  device?: string | null
  dtype?: string | null
  compile?: boolean
  warmup?: boolean
  max_seq_len?: number | null
  max_batch_size?: number | null
}

export interface MlxStatus {
  active: boolean
  model: string | null
  loaded_at: number | string | null
  supports_embeddings: boolean
  warmup_completed: boolean
  max_concurrent: number
  config?: MlxStatusConfig
}

export interface MlxLoadRequest {
  model_path?: string
  max_seq_len?: number
  max_batch_size?: number
  device?: string
  dtype?: string
  quantization?: string
  compile?: boolean
  warmup?: boolean
  prompt_template?: string
  revision?: string
  trust_remote_code?: boolean
  tokenizer?: string
  adapter?: string
  adapter_weights?: string
  max_kv_cache_size?: number
  max_concurrent?: number
}

export interface MlxUnloadRequest {
  reason?: string
}

export interface MediaIngestionBudgetDiagnostics {
  status: string
  entity?: string | null
  policy_id?: string | null
  limits?: {
    jobs_max_concurrent?: number | null
    ingestion_bytes_daily_cap?: number | null
  } | null
  usage?: {
    jobs_active?: number | null
    jobs_remaining?: number | null
    ingestion_bytes_daily_used?: number | null
    ingestion_bytes_daily_remaining?: number | null
  } | null
  retry_after?: number | null
  reason?: string | null
  error?: string | null
}

export class TldwApiClient {
  private storage: Storage
  private config: TldwConfig | null = null
  private baseUrl: string = ''
  private headers: HeadersInit = {}
  characterCache = new Map<string, { value: any; expiresAt: number }>()
  characterInFlight = new Map<string, Promise<any>>()
  chatMessagesCache = new Map<
    string,
    { value: ServerChatMessage[]; expiresAt: number }
  >()
  chatMessagesInFlight = new Map<string, Promise<ServerChatMessage[]>>()
  private openApiPathSet: Set<string> | null = null
  private openApiPathSetPromise: Promise<Set<string> | null> | null = null
  private resolvedPathCache = new Map<string, string>()

  constructor() {
    this.storage = createSafeStorage({
      serde: safeStorageSerde
    })
  }

  private getEnvApiKey(): string | null {
    try {
      const env: any = (import.meta as any)?.env || {}
      const raw =
        (env?.VITE_TLDW_API_KEY as string | undefined) ??
        (env?.VITE_TLDW_DEFAULT_API_KEY as string | undefined)
      const key = (raw || "").trim()
      return key || null
    } catch {
      return null
    }
  }

  private isDevMode(): boolean {
    try {
      const env: any = (import.meta as any)?.env || {}
      return Boolean(env?.DEV) || env?.MODE === "development"
    } catch {
      return false
    }
  }

  private getMissingApiKeyMessage(): string {
    return "tldw server API key is missing. Open Settings → tldw server and configure an API key before continuing."
  }

  normalizeRagQuery(rawQuery: string): string {
    const normalized =
      typeof rawQuery === "string" ? rawQuery : String(rawQuery ?? "")
    if (normalized.length <= RAG_QUERY_MAX_LENGTH) {
      return normalized
    }

    // Keep client behavior resilient to backend schema limits.
    const truncated = normalized.slice(0, RAG_QUERY_MAX_LENGTH).trimEnd()
    console.warn(
      `[tldw:rag] query exceeded ${RAG_QUERY_MAX_LENGTH} characters; truncating before request`,
      { originalLength: normalized.length, truncatedLength: truncated.length }
    )
    return truncated
  }

  getChatMessagesCacheKey(chatId: string, query: string): string {
    return `${chatId}${query || ""}`
  }

  invalidateChatMessagesCache(chatId?: string | number): void {
    const cid = chatId != null ? String(chatId) : null
    if (!cid) {
      this.chatMessagesCache.clear()
      return
    }
    for (const key of this.chatMessagesCache.keys()) {
      if (key.startsWith(cid)) {
        this.chatMessagesCache.delete(key)
      }
    }
  }

  private getPlaceholderApiKeyMessage(): string {
    return "tldw server API key is still set to the default demo value. Replace it with your real API key in Settings → tldw server before continuing."
  }

  async ensureConfigForRequest(requireAuth: boolean): Promise<TldwConfig> {
    const cfg = (await this.getConfig()) || null
    const hostedMode = isHostedTldwDeployment()
    if ((!cfg || !cfg.serverUrl) && !hostedMode) {
      const msg =
        "tldw server is not configured. Open Settings → tldw server in the extension and set the server URL and API key."
      // eslint-disable-next-line no-console
      console.warn(msg)
      throw new Error(msg)
    }

    if (hostedMode) {
      return {
        serverUrl: String(cfg?.serverUrl || ""),
        apiKey: cfg?.apiKey,
        accessToken: cfg?.accessToken,
        refreshToken: cfg?.refreshToken,
        orgId: cfg?.orgId,
        authMode: cfg?.authMode || "multi-user"
      }
    }

    if (!requireAuth) {
      return cfg
    }

    if (cfg.authMode === "multi-user") {
      const token = (cfg.accessToken || "").trim()
      if (!token) {
        const msg =
          "Not authenticated. Please log in under Settings → tldw server before continuing."
        // eslint-disable-next-line no-console
        console.warn(msg)
        throw new Error(msg)
      }
      return cfg
    }

    // single-user auth
    const key = (cfg.apiKey || "").trim()
    if (!key) {
      const msg = this.getMissingApiKeyMessage()
      // eslint-disable-next-line no-console
      console.warn(msg)
      throw new Error(msg)
    }
    if (isPlaceholderApiKey(key)) {
      const msg = this.getPlaceholderApiKeyMessage()
      // eslint-disable-next-line no-console
      console.warn(msg)
      throw new Error(msg)
    }
    return cfg
  }

  async request<T>(init: any, requireAuth = true): Promise<T> {
    await this.ensureConfigForRequest(requireAuth && !init?.noAuth)
    return await bgRequest<T>(init)
  }

  async fetchWithAuth(
    path: PathOrUrl,
    init?: {
      method?: string
      headers?: Record<string, string>
      body?: any
      timeoutMs?: number
      signal?: AbortSignal
      responseType?: "json" | "text" | "arrayBuffer"
    }
  ): Promise<{
    ok: boolean
    status?: number
    error?: string
    data?: any
    json: () => Promise<any>
    text: () => Promise<string>
  }> {
    await this.ensureConfigForRequest(true)
    const response = await bgRequest<any, PathOrUrl>({
      path,
      method: (init?.method || "GET") as any,
      headers: init?.headers,
      body: init?.body,
      timeoutMs: init?.timeoutMs,
      abortSignal: init?.signal,
      responseType: init?.responseType,
      returnResponse: true
    })
    const data = response?.data
    const text = () => {
      if (typeof data === "string") return Promise.resolve(data)
      if (data == null) return Promise.resolve("")
      try {
        return Promise.resolve(JSON.stringify(data))
      } catch {
        return Promise.resolve(String(data))
      }
    }
    return {
      ok: Boolean(response?.ok),
      status: response?.status,
      error: response?.error,
      data,
      json: () => Promise.resolve(data),
      text
    }
  }

  async upload<T>(init: any, requireAuth = true): Promise<T> {
    await this.ensureConfigForRequest(requireAuth)
    return await bgUpload<T>(init)
  }

  async *stream(init: any, requireAuth = true): AsyncGenerator<string> {
    await this.ensureConfigForRequest(requireAuth)
    for await (const line of bgStream(init)) {
      yield line as string
    }
  }

  async initialize(): Promise<void> {
    let stored = await this.storage.get<TldwConfig>("tldwConfig")
    if (!stored) {
      try {
        const localStore = createSafeStorage({
          area: "local",
          serde: safeStorageSerde
        })
        const localConfig = await localStore.get<TldwConfig>("tldwConfig")
        if (localConfig) {
          stored = localConfig
          await this.storage.set("tldwConfig", localConfig)
        }
      } catch {
        // ignore migration failures
      }
    }
    const envApiKey = this.getEnvApiKey()

    if (!stored) {
      // True first-run: leave config null so callers (like the connection
      // store) can distinguish an unconfigured state from a misconfigured
      // or unreachable server.
      this.config = null
    } else {
      const hydrated: TldwConfig = {
        ...stored,
        // Default authMode but do not silently inject a server URL if none
        // has been configured yet.
        authMode: stored.authMode || "single-user",
        serverUrl: stored.serverUrl || ""
      }
      if (!hydrated.apiKey && envApiKey) {
        hydrated.apiKey = envApiKey
      }
      this.config = hydrated
      await this.storage.set("tldwConfig", hydrated)
    }

    const config = this.config
    const hostedMode = isHostedTldwDeployment()
    const nextBaseUrl = hostedMode
      ? String(config?.serverUrl || "").replace(/\/$/, "")
      : (config?.serverUrl || DEFAULT_SERVER_URL).replace(/\/$/, "")
    if (this.baseUrl && this.baseUrl !== nextBaseUrl) {
      this.openApiPathSet = null
      this.openApiPathSetPromise = null
      this.resolvedPathCache.clear()
    }
    this.baseUrl = nextBaseUrl

    // Set up headers based on auth mode
    this.headers = {
      "Content-Type": "application/json"
    }

    if (!hostedMode && config?.authMode === "single-user" && config.apiKey) {
      const key = String(config.apiKey || "").trim()
      if (key) {
        this.headers["X-API-KEY"] = key
      }
    } else if (!hostedMode && config?.authMode === "multi-user" && config.accessToken) {
      this.headers["Authorization"] = `Bearer ${config.accessToken}`
    }
    if (config?.orgId) {
      this.headers["X-TLDW-Org-Id"] = String(config.orgId)
    }
  }

  async getConfig(): Promise<TldwConfig | null> {
    if (this.config === null) {
      await this.initialize().catch(() => null)
    }
    return this.config
  }

  async updateConfig(config: Partial<TldwConfig>): Promise<void> {
    const currentConfig = (await this.getConfig()) || {}
    const newConfig = { ...(currentConfig as any), ...config } as TldwConfig
    await this.storage.set('tldwConfig', newConfig)
    this.config = newConfig
    await this.initialize().catch(() => null)
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("tldw:config-updated"))
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      await bgRequest<{ status?: string; [k: string]: any }>({
        path: '/api/v1/health',
        method: 'GET'
      })
      return true
    } catch {
      // Swallow errors to avoid noisy console during first-run
      return false
    }
  }

  async getServerInfo(): Promise<any> {
    return await bgRequest<any>({ path: '/', method: 'GET' })
  }

  async getCurrentUserProfile(params?: {
    sections?: string | string[]
    includeSources?: boolean
    includeRaw?: boolean
    maskSecrets?: boolean
  }): Promise<any> {
    const sections = Array.isArray(params?.sections)
      ? params?.sections.join(",")
      : params?.sections
    const query = this.buildQuery({
      sections,
      include_sources: params?.includeSources,
      include_raw: params?.includeRaw,
      mask_secrets: params?.maskSecrets
    })
    return await this.request<any>({
      path: `/api/v1/users/me/profile${query}`,
      method: "GET"
    })
  }

  async updateCurrentUserProfile(payload: {
    updates: UserProfileUpdateEntry[]
    profile_version?: string
    dry_run?: boolean
  }): Promise<UserProfileUpdateResponse> {
    return await this.request<UserProfileUpdateResponse>({
      path: "/api/v1/users/me/profile",
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async getCurrentUserStorageQuota(): Promise<CurrentUserStorageQuotaResponse> {
    return await this.request<CurrentUserStorageQuotaResponse>({
      path: "/api/v1/users/storage",
      method: "GET"
    })
  }

  async startOpenAIOAuthAuthorize(
    payload: OpenAIOAuthAuthorizeRequest = {}
  ): Promise<OpenAIOAuthAuthorizeResponse> {
    return await this.request<OpenAIOAuthAuthorizeResponse>({
      path: "/api/v1/users/keys/openai/oauth/authorize",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async getOpenAIOAuthStatus(): Promise<OpenAIOAuthStatusResponse> {
    return await this.request<OpenAIOAuthStatusResponse>({
      path: "/api/v1/users/keys/openai/oauth/status",
      method: "GET"
    })
  }

  async refreshOpenAIOAuth(): Promise<OpenAIOAuthRefreshResponse> {
    return await this.request<OpenAIOAuthRefreshResponse>({
      path: "/api/v1/users/keys/openai/oauth/refresh",
      method: "POST"
    })
  }

  async disconnectOpenAIOAuth(): Promise<void> {
    await this.request<void>({
      path: "/api/v1/users/keys/openai/oauth",
      method: "DELETE"
    })
  }

  async switchOpenAICredentialSource(
    authSource: "api_key" | "oauth"
  ): Promise<OpenAICredentialSourceSwitchResponse> {
    return await this.request<OpenAICredentialSourceSwitchResponse>({
      path: "/api/v1/users/keys/openai/source",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { auth_source: authSource }
    })
  }

  async getDefaultCharacterPreference(): Promise<string | null> {
    const profile = await this.getCurrentUserProfile({
      sections: "preferences"
    })
    const raw = profile?.preferences?.[DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY]
    if (
      raw &&
      typeof raw === "object" &&
      !Array.isArray(raw) &&
      "value" in raw
    ) {
      return normalizeDefaultCharacterPreferenceId(
        (raw as { value?: unknown }).value
      )
    }
    return normalizeDefaultCharacterPreferenceId(raw)
  }

  async setDefaultCharacterPreference(
    characterId: string | null
  ): Promise<UserProfileUpdateResponse> {
    const normalizedCharacterId = normalizeDefaultCharacterPreferenceId(characterId)
    return await this.updateCurrentUserProfile({
      updates: [
        {
          key: DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY,
          value: normalizedCharacterId
        }
      ]
    })
  }

  buildQuery(params?: Record<string, any>): string {
    if (!params || Object.keys(params).length === 0) {
      return ''
    }
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue
      if (Array.isArray(value)) {
        value.forEach((entry) => search.append(key, String(entry)))
        continue
      }
      search.append(key, String(value))
    }
    const query = search.toString()
    return query ? `?${query}` : ''
  }

  async getOpenAPISpec(): Promise<any | null> {
    try {
      if (!this.baseUrl) await this.initialize()
      if (!this.baseUrl) return null
      return await bgRequest<any>({
        path: `${this.baseUrl.replace(/\/$/, '')}/openapi.json` as any,
        method: 'GET' as any
      })
    } catch {
      return null
    }
  }

  normalizePathShape(path: string): string {
    return path.replace(/\{[^}]+\}/g, "{}")
  }

  async getOpenApiPathSet(): Promise<Set<string> | null> {
    if (this.openApiPathSet) return this.openApiPathSet
    if (!this.openApiPathSetPromise) {
      this.openApiPathSetPromise = (async () => {
        const spec = await this.getOpenAPISpec()
        if (!spec?.paths || typeof spec.paths !== "object") {
          this.openApiPathSet = null
          this.openApiPathSetPromise = null
          return null
        }
        const paths = new Set(Object.keys(spec.paths))
        this.openApiPathSet = paths
        this.resolvedPathCache.clear()
        return paths
      })()
    }
    return this.openApiPathSetPromise
  }

  async resolveApiPath(
    key: string,
    candidates: string[]
  ): Promise<AllowedPath> {
    const cached = this.resolvedPathCache.get(key)
    if (cached) return cached as AllowedPath
    const fallback = candidates[0] as AllowedPath
    if (!fallback) {
      throw new Error(`No path candidates provided for ${key}`)
    }
    const specPaths = await this.getOpenApiPathSet().catch(() => null)
    if (!specPaths || specPaths.size === 0) {
      this.resolvedPathCache.set(key, fallback)
      return fallback
    }

    const specShapes = new Set(
      Array.from(specPaths, (path) => this.normalizePathShape(String(path)))
    )

    const resolved =
      candidates.find((candidate) => {
        if (specPaths.has(candidate)) return true
        return specShapes.has(this.normalizePathShape(candidate))
      }) || fallback

    this.resolvedPathCache.set(key, resolved)
    return resolved as AllowedPath
  }

  fillPathParams(
    template: AllowedPath,
    values: string | string[]
  ): AllowedPath {
    if (!template.includes("{")) return template
    if (Array.isArray(values)) {
      let index = 0
      return template.replace(/\{[^}]+\}/g, () => {
        const value = values[index] ?? ""
        index += 1
        return encodeURIComponent(value)
      }) as AllowedPath
    }
    const encoded = encodeURIComponent(values)
    return template.replace(/\{[^}]+\}/g, encoded) as AllowedPath
  }

  async postChatMetric(payload: Record<string, unknown>): Promise<any> {
    return await this.request<any>({
      path: "/api/v1/metrics/chat",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

}

// ─────────────────────────────────────────────────────────────────────────────
// Domain Method Mixins
// ─────────────────────────────────────────────────────────────────────────────

import { adminMethods } from "./domains/admin"
import { mediaMethods } from "./domains/media"
import { characterMethods } from "./domains/characters"
import { chatRagMethods } from "./domains/chat-rag"
import { collectionsMethods } from "./domains/collections"
import { modelsAudioMethods } from "./domains/models-audio"
import { presentationsMethods } from "./domains/presentations"
import { workspaceApiMethods } from "./domains/workspace-api"

// Declaration merging: extend the class type with all domain methods
export interface TldwApiClient
  extends
    Omit<typeof adminMethods, never>,
    Omit<typeof mediaMethods, never>,
    Omit<typeof characterMethods, never>,
    Omit<typeof chatRagMethods, never>,
    Omit<typeof collectionsMethods, never>,
    Omit<typeof modelsAudioMethods, never>,
    Omit<typeof presentationsMethods, never>,
    Omit<typeof workspaceApiMethods, never> {}

// Apply domain methods to the prototype
Object.assign(
  TldwApiClient.prototype,
  adminMethods,
  mediaMethods,
  characterMethods,
  chatRagMethods,
  collectionsMethods,
  modelsAudioMethods,
  presentationsMethods,
  workspaceApiMethods
)

// Also expose core helpers that domain files reference via `this`
export type TldwApiClientCore = TldwApiClient

// Singleton instance
export const tldwClient = new TldwApiClient()
