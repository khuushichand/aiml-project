import { Storage } from "@plasmohq/storage"
import { createSafeStorage, safeStorageSerde } from "@/utils/safe-storage"
import {
  bgRequest,
  bgStream,
  bgUpload,
  type BgRequestInit,
  type BgStreamInit,
  type BgUploadInit
} from "@/services/background-proxy"
import { isPlaceholderApiKey } from "@/utils/api-key"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import { env } from "@/config/env"
import type { AllowedPath, PathOrUrl } from "@/services/tldw/openapi-guard"
import { appendPathQuery } from "@/services/tldw/path-utils"
import {
  buildContentPayload,
  mapApiDetailToUi,
  mapApiListToUi,
  mapUiSourceToApi,
  type ApiDataTableDetailResponse,
  type ApiDataTableGenerateResponse,
  type ApiDataTableJobStatus
} from "@/services/tldw/data-tables"
import type { ReadingImportJobDetail, ReadingImportJobResponse } from "@/types/collections"
import type { DataTableColumn, DataTableSource } from "@/types/data-tables"

const DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
const CHARACTER_CACHE_TTL_MS = 5 * 60 * 1000
const CHAT_MESSAGES_CACHE_TTL_MS = 60 * 1000

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null

export interface TldwConfig {
  serverUrl: string
  apiKey?: string
  accessToken?: string
  refreshToken?: string
  authMode: 'single-user' | 'multi-user'
}

export interface TldwModel {
  id: string
  name: string
  provider: string
  description?: string
  capabilities?: string[]
  context_length?: number
  type?: string
  modalities?: {
    input?: string[]
    output?: string[]
  }
  vision?: boolean
  function_calling?: boolean
  json_output?: boolean
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
  stream?: boolean
  temperature?: number
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
  response_format?: { type: "json_object" | "text" }
}

export interface ServerChatSummary {
  id: string
  title: string
  created_at: string
  updated_at?: string | null
  source?: string | null
  state?: ConversationState | string | null
  topic_label?: string | null
  cluster_id?: string | null
  external_ref?: string | null
  bm25_norm?: number | null
  character_id?: string | number | null
  parent_conversation_id?: string | null
  root_id?: string | null
  version?: number | null
}

export type ConversationState =
  | "in-progress"
  | "resolved"
  | "backlog"
  | "non-viable"

export interface ServerChatMessage {
  id: string
  role: "system" | "user" | "assistant"
  content: string
  created_at: string
  version?: number
}

type PromptPayload = {
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

export class TldwApiClient {
  private storage: Storage
  private config: TldwConfig | null = null
  private baseUrl: string = ''
  private headers: HeadersInit = {}
  private characterCache = new Map<string, { value: unknown; expiresAt: number }>()
  private characterInFlight = new Map<string, Promise<unknown>>()
  private chatMessagesCache = new Map<
    string,
    { value: ServerChatMessage[]; expiresAt: number }
  >()
  private chatMessagesInFlight = new Map<string, Promise<ServerChatMessage[]>>()
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
      return Boolean(env?.DEV) || process.env.NODE_ENV === "development"
    } catch {
      return false
    }
  }

  private getMissingApiKeyMessage(): string {
    return "tldw server API key is missing. Open Settings → tldw server and configure an API key before continuing."
  }

  private getChatMessagesCacheKey(chatId: string, query: string): string {
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

  private async ensureConfigForRequest(requireAuth: boolean): Promise<TldwConfig> {
    const cfg = (await this.getConfig()) || null
    if (!cfg || !cfg.serverUrl) {
      const msg =
        "tldw server is not configured. Open Settings → tldw server in the extension and set the server URL and API key."
      console.warn(msg)
      throw new Error(msg)
    }

    if (!requireAuth) {
      return cfg
    }

    if (cfg.authMode === "multi-user") {
      const token = (cfg.accessToken || "").trim()
      if (!token) {
        const msg =
          "Not authenticated. Please log in under Settings → tldw server before continuing."
        console.warn(msg)
        throw new Error(msg)
      }
      return cfg
    }

    // single-user auth
    const key = (cfg.apiKey || "").trim()
    if (!key) {
      const msg = this.getMissingApiKeyMessage()
      console.warn(msg)
      throw new Error(msg)
    }
    if (isPlaceholderApiKey(key)) {
      const msg = this.getPlaceholderApiKeyMessage()
      console.warn(msg)
      throw new Error(msg)
    }
    return cfg
  }

  private async request<T>(init: BgRequestInit<PathOrUrl>, requireAuth = true): Promise<T> {
    await this.ensureConfigForRequest(requireAuth && !init?.noAuth)
    return await bgRequest<T>(init)
  }

  private async upload<T>(init: BgUploadInit, requireAuth = true): Promise<T> {
    await this.ensureConfigForRequest(requireAuth)
    return await bgUpload<T>(init)
  }

  private async *stream(init: BgStreamInit, requireAuth = true): AsyncGenerator<string> {
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
    const nextBaseUrl = (config?.serverUrl || DEFAULT_SERVER_URL).replace(/\/$/, "")
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

    if (config?.authMode === "single-user" && config.apiKey) {
      const key = String(config.apiKey || "").trim()
      if (key) {
        this.headers["X-API-KEY"] = key
      }
    } else if (config?.authMode === "multi-user" && config.accessToken) {
      this.headers["Authorization"] = `Bearer ${config.accessToken}`
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
    const newConfig = { ...currentConfig, ...config } as TldwConfig
    await this.storage.set('tldwConfig', newConfig)
    this.config = newConfig
    await this.initialize().catch(() => null)
  }

  async healthCheck(): Promise<boolean> {
    try {
      await bgRequest<{ status?: string; [k: string]: unknown }>({
        path: '/api/v1/health',
        method: 'GET'
      })
      return true
    } catch {
      // Swallow errors to avoid noisy console during first-run
      return false
    }
  }

  async getServerInfo(): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/', method: 'GET' })
  }

  private buildQuery(params?: Record<string, unknown>): string {
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

  async getOpenAPISpec(): Promise<unknown | null> {
    try {
      if (!this.baseUrl) await this.initialize()
      if (!this.baseUrl) return null
      return await bgRequest<unknown, PathOrUrl, "GET">({
        path: `${this.baseUrl.replace(/\/$/, '')}/openapi.json`,
        method: 'GET'
      })
    } catch {
      return null
    }
  }

  private normalizePathShape(path: string): string {
    return path.replace(/\{[^}]+\}/g, "{}")
  }

  private async getOpenApiPathSet(): Promise<Set<string> | null> {
    if (this.openApiPathSet) return this.openApiPathSet
    if (!this.openApiPathSetPromise) {
      this.openApiPathSetPromise = (async () => {
        const spec = await this.getOpenAPISpec()
        if (!isRecord(spec) || !isRecord(spec.paths)) {
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

  private async resolveApiPath(
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

  private fillPathParams(
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

  async postChatMetric(payload: Record<string, unknown>): Promise<unknown> {
    return await this.request<unknown>({
      path: "/api/v1/metrics/chat",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async getModels(): Promise<TldwModel[]> {
    const meta = await this.getModelsMetadata()
    const toStringArray = (value: unknown): string[] | undefined =>
      Array.isArray(value) ? value.map((item) => String(item)) : undefined
    const list =
      Array.isArray(meta) && meta.length > 0
        ? meta
        : isRecord(meta) && Array.isArray(meta.models)
          ? meta.models
          : []

    return list.map((item) => {
      const record = isRecord(item) ? item : {}
      const capabilitiesArray =
        toStringArray(record.capabilities) ?? toStringArray(record.features)
      const capabilitiesObject = isRecord(record.capabilities)
        ? record.capabilities
        : null
      const modalities = isRecord(record.modalities)
        ? {
            input: toStringArray(record.modalities.input),
            output: toStringArray(record.modalities.output)
          }
        : undefined
      return {
        id: String(record.id || record.model || record.name || ""),
        name: String(record.name || record.id || record.model || ""),
        provider: String(record.provider || "default"),
        description:
          typeof record.description === "string" ? record.description : undefined,
        capabilities: capabilitiesArray,
        context_length:
          typeof record.context_length === "number"
            ? record.context_length
            : typeof record.context_window === "number"
              ? record.context_window
              : typeof record.contextLength === "number"
              ? record.contextLength
              : undefined,
        type: typeof record.type === "string" ? record.type : undefined,
        modalities,
        vision: Boolean((capabilitiesObject?.vision ?? record.vision)),
        function_calling: Boolean(
          (capabilitiesObject &&
            (capabilitiesObject.function_calling ||
              capabilitiesObject.tool_use)) ??
            record.function_calling
        ),
        json_output: Boolean(
          (capabilitiesObject?.json_mode ?? record.json_output)
        )
      }
    })
  }

  async getProviders(): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/api/v1/llm/providers', method: 'GET' })
  }

  async getModelsMetadata(): Promise<unknown> {
    // tldw_server returns either an array or an object
    // of the form { models: [...], total: N }.
    return await bgRequest<unknown>({ path: '/api/v1/llm/models/metadata', method: 'GET' })
  }

  // Embeddings - Models & Providers
  async getEmbeddingModelsList(): Promise<TldwEmbeddingModel[]> {
    try {
      const data = await bgRequest<TldwEmbeddingModelsResponse | TldwEmbeddingModel[]>({
        path: "/api/v1/embeddings/models",
        method: "GET"
      })

      const list: unknown[] = Array.isArray(data)
        ? data
        : isRecord(data) && Array.isArray(data.data)
          ? data.data
          : []

      return list
        .map((item) => {
          const record = isRecord(item) ? item : {}
          return {
            provider: String(record.provider || "unknown"),
            model: String(record.model || ""),
          allowed:
            typeof record.allowed === "boolean"
              ? Boolean(record.allowed)
              : true,
            default: Boolean(record.default)
          }
        })
        .filter((m) => m.model.length > 0)
    } catch (e) {
      if (env.DEV) {
        console.warn("tldw_server: GET /api/v1/embeddings/models failed", e)
      }
      return []
    }
  }

  async getEmbeddingProvidersConfig(): Promise<TldwEmbeddingProvidersConfig | null> {
    try {
      const cfg = await bgRequest<TldwEmbeddingProvidersConfig>({
        path: "/api/v1/embeddings/providers-config",
        method: "GET"
      })
      return cfg
    } catch (e) {
      if (env.DEV) {
        console.warn(
          "tldw_server: GET /api/v1/embeddings/providers-config failed",
          e
        )
      }
      return null
    }
  }

  // Admin / diagnostics helpers
  async getSystemStats(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/admin/stats",
      method: "GET"
    })
  }

  async getLlamacppStatus(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/llamacpp/status",
      method: "GET"
    })
  }

  async listLlamacppModels(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/llamacpp/models",
      method: "GET"
    })
  }

  async startLlamacppServer(
    modelFilename: string,
    serverArgs?: Record<string, unknown>
  ): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/llamacpp/start_server",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        model_filename: modelFilename,
        server_args: serverArgs || {}
      }
    })
  }

  async stopLlamacppServer(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/llamacpp/stop_server",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {}
    })
  }

  async getLlmProviders(
    includeDeprecated = false
  ): Promise<unknown> {
    const query = this.buildQuery(includeDeprecated ? { include_deprecated: true } : {})
    return await bgRequest<unknown>({
      path: `/api/v1/llm/providers${query}`,
      method: "GET"
    })
  }

  // MLX admin helpers
  async getMlxStatus(): Promise<MlxStatus> {
    return await bgRequest<MlxStatus>({
      path: "/api/v1/llm/providers/mlx/status",
      method: "GET"
    })
  }

  async loadMlxModel(payload: MlxLoadRequest): Promise<MlxStatus> {
    return await bgRequest<MlxStatus>({
      path: "/api/v1/llm/providers/mlx/load",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async unloadMlxModel(payload?: MlxUnloadRequest): Promise<{ message?: string }> {
    return await bgRequest<{ message?: string }>({
      path: "/api/v1/llm/providers/mlx/unload",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload || {}
    })
  }

  async listAdminUsers(params?: {
    page?: number
    limit?: number
    role?: string
    is_active?: boolean
    search?: string
  }): Promise<AdminUserListResponse> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<AdminUserListResponse>({
      path: `/api/v1/admin/users${query}`,
      method: "GET"
    })
  }

  async updateAdminUser(
    userId: number,
    payload: AdminUserUpdateRequest
  ): Promise<{ message: string }> {
    return await bgRequest<{ message: string }>({
      path: `/api/v1/admin/users/${userId}`,
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async listAdminRoles(): Promise<AdminRole[]> {
    return await bgRequest<AdminRole[]>({
      path: "/api/v1/admin/roles",
      method: "GET"
    })
  }

  async createAdminRole(
    name: string,
    description?: string
  ): Promise<AdminRole> {
    return await bgRequest<AdminRole>({
      path: "/api/v1/admin/roles",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { name, description }
    })
  }

  async deleteAdminRole(roleId: number): Promise<{ message: string }> {
    return await bgRequest<{ message: string }>({
      path: `/api/v1/admin/roles/${roleId}`,
      method: "DELETE"
    })
  }

  async createChatCompletion(request: ChatCompletionRequest): Promise<Response> {
    // Non-stream request via background
    const res = await bgRequest<Response>({ path: '/api/v1/chat/completions', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: request })
    // bgRequest returns parsed data; for non-streaming chat we expect a JSON structure or text. To keep existing consumers happy, wrap as Response-like
    // For simplicity, return a minimal object with json() and text()
    const data = res as unknown
    return new Response(typeof data === 'string' ? data : JSON.stringify(data), { status: 200, headers: { 'content-type': typeof data === 'string' ? 'text/plain' : 'application/json' } })
  }

  async *streamChatCompletion(request: ChatCompletionRequest, options?: { signal?: AbortSignal; streamIdleTimeoutMs?: number }): AsyncGenerator<unknown, void, unknown> {
    request.stream = true
    for await (const line of bgStream({ path: '/api/v1/chat/completions', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: request, abortSignal: options?.signal, streamIdleTimeoutMs: options?.streamIdleTimeoutMs })) {
      try {
        const parsed = JSON.parse(line)
        yield parsed
      } catch {
        // Ignore non-JSON lines
      }
    }
  }

  // RAG Methods
  async ragHealth(): Promise<unknown> {
    return await this.request<unknown>({ path: '/api/v1/rag/health', method: 'GET' })
  }

  async ragSearch(query: string, options?: Record<string, unknown>): Promise<unknown> {
    const opts = isRecord(options) ? options : {}
    const timeoutMs = typeof opts.timeoutMs === "number" ? opts.timeoutMs : undefined
    const { timeoutMs: _discard, ...rest } = opts
    return await bgRequest<unknown>({
      path: '/api/v1/rag/search',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { query, ...rest },
      timeoutMs
    })
  }

  async ragSimple(query: string, options?: Record<string, unknown>): Promise<unknown> {
    const opts = isRecord(options) ? options : {}
    const timeoutMs = typeof opts.timeoutMs === "number" ? opts.timeoutMs : undefined
    const { timeoutMs: _discard, ...rest } = opts
    return await bgRequest<unknown>({
      path: '/api/v1/rag/simple',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { query, ...rest },
      timeoutMs
    })
  }

  // Research / Web search
  async webSearch(options: Record<string, unknown>): Promise<unknown> {
    const opts = isRecord(options) ? options : {}
    const timeoutMs = typeof opts.timeoutMs === "number" ? opts.timeoutMs : undefined
    const signal = opts.signal as AbortSignal | undefined
    const { timeoutMs: _timeout, signal: _signal, ...rest } = opts
    return await bgRequest<unknown>({
      path: "/api/v1/research/websearch",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: rest,
      timeoutMs,
      abortSignal: signal
    })
  }

  // Media Methods
  async addMedia(url: string, metadata?: Record<string, unknown>): Promise<unknown> {
    const opts = isRecord(metadata) ? metadata : {}
    const timeoutMs = typeof opts.timeoutMs === "number" ? opts.timeoutMs : undefined
    const { timeoutMs: _discard, ...rest } = opts
    return await bgRequest<unknown>({
      path: '/api/v1/media/add',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { url, ...rest },
      timeoutMs
    })
  }

  async addMediaForm(fields: Record<string, unknown>): Promise<unknown> {
    // Multipart form for rich ingest parameters
    // Accepts a flat fields map; callers may pass booleans/strings and they will be converted
    const normalized: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(fields || {})) {
      if (typeof v === 'undefined' || v === null) continue
      if (typeof v === 'boolean') normalized[k] = v ? 'true' : 'false'
      else normalized[k] = v
    }
    return await bgUpload<unknown>({ path: '/api/v1/media/add', method: 'POST', fields: normalized })
  }

  async uploadMedia(file: File, fields?: Record<string, unknown>): Promise<unknown> {
    const data = await file.arrayBuffer()
    const name = file.name || 'upload'
    const type = file.type || 'application/octet-stream'
    const normalized: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(fields || {})) {
      if (typeof v === 'undefined' || v === null) continue
      if (typeof v === 'boolean') normalized[k] = v ? 'true' : 'false'
      else normalized[k] = v
    }
    return await bgUpload<unknown>({ path: '/api/v1/media/add', method: 'POST', fields: normalized, file: { name, type, data } })
  }

  async listMedia(params?: {
    page?: number
    results_per_page?: number
    include_keywords?: boolean
  }): Promise<unknown> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<unknown>({
      path: `/api/v1/media${query}`,
      method: "GET"
    })
  }

  async searchMedia(
    payload: {
      query?: string
      fields?: string[]
      exact_phrase?: string
      media_types?: string[]
      date_range?: Record<string, unknown>
      must_have?: string[]
      must_not_have?: string[]
      sort_by?: string
      boost_fields?: Record<string, number>
    },
    params?: { page?: number; results_per_page?: number }
  ): Promise<unknown> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<unknown>({
      path: `/api/v1/media/search${query}`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  // Notes Methods
  async createNote(content: string, metadata?: Record<string, unknown>): Promise<unknown> {
    const meta = isRecord(metadata) ? metadata : {}
    return await bgRequest<unknown>({
      path: '/api/v1/notes/',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { content, ...meta }
    })
  }

  async searchNotes(query: string): Promise<unknown> {
    // OpenAPI uses trailing slash for this path
    return await bgRequest<unknown>({
      path: '/api/v1/notes/search/',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { query }
    })
  }
  // Prompts Methods
  async getPrompts(): Promise<unknown> {
    const path = await this.resolveApiPath("prompts.list", [
      "/api/v1/prompts",
      "/api/v1/prompts/"
    ])
    return await bgRequest<unknown>({ path, method: 'GET' })
  }

  async searchPrompts(query: string): Promise<unknown> {
    // TODO: confirm trailing slash per OpenAPI (`/api/v1/prompts/search` exists without slash)
    return await bgRequest<unknown>({
      path: '/api/v1/prompts/search',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { query }
    })
  }

  async createPrompt(payload: PromptPayload): Promise<unknown> {
    const name = payload.name || payload.title || 'Untitled'
    const system_prompt = payload.system_prompt ?? (payload.is_system ? payload.content : undefined)
    const user_prompt = payload.user_prompt ?? (!payload.is_system ? payload.content : undefined)
    const keywords = payload.keywords
    const normalized: Record<string, unknown> = {
      name,
      author: payload.author,
      details: payload.details,
      system_prompt,
      user_prompt,
      keywords
    }

    Object.keys(normalized).forEach((key) => {
      if (typeof normalized[key] === 'undefined') delete normalized[key]
    })

    const path = await this.resolveApiPath("prompts.create", [
      "/api/v1/prompts",
      "/api/v1/prompts/"
    ])
    return await bgRequest<unknown>({
      path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: normalized
    })
  }

  async updatePrompt(id: string | number, payload: PromptPayload): Promise<unknown> {
    const pid = String(id)
    const name = payload.name || payload.title || 'Untitled'
    const system_prompt = payload.system_prompt ?? (payload.is_system ? payload.content : undefined)
    const user_prompt = payload.user_prompt ?? (!payload.is_system ? payload.content : undefined)
    const keywords = payload.keywords

    const normalized: Record<string, unknown> = {
      name,
      author: payload.author,
      details: payload.details,
      system_prompt,
      user_prompt,
      keywords
    }

    Object.keys(normalized).forEach((key) => {
      if (typeof normalized[key] === 'undefined') delete normalized[key]
    })

    // Path per OpenAPI: /api/v1/prompts/{prompt_identifier}
    return await bgRequest<unknown>({
      path: `/api/v1/prompts/${pid}`,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: normalized
    })
  }

  // Characters API
  async listCharacters(params?: Record<string, unknown>): Promise<unknown[]> {
    const query = this.buildQuery(params as Record<string, unknown>)
    const base = await this.resolveApiPath("characters.list", [
      "/api/v1/characters",
      "/api/v1/characters/"
    ])
    return await bgRequest<unknown[]>({
      path: appendPathQuery(base, query),
      method: 'GET'
    })
  }

   async searchCharacters(query: string, params?: Record<string, unknown>): Promise<unknown[]> {
    const qp = this.buildQuery({ query, ...(params || {}) } as Record<string, unknown>)
    const base = await this.resolveApiPath("characters.search", [
      "/api/v1/characters/search",
      "/api/v1/characters/search/"
    ])
    return await bgRequest<unknown[]>({
      path: appendPathQuery(base, qp),
      method: 'GET'
    })
  }

  async filterCharactersByTags(
    tags: string[],
    options?: { match_all?: boolean; limit?: number; offset?: number }
  ): Promise<unknown[]> {
    const qp = this.buildQuery({
      tags,
      ...(options || {})
    } as Record<string, unknown>)
    const base = await this.resolveApiPath("characters.filter", [
      "/api/v1/characters/filter",
      "/api/v1/characters/filter/"
    ])
    return await bgRequest<unknown[]>({
      path: appendPathQuery(base, qp),
      method: 'GET'
    })
  }

  async getCharacter(id: string | number): Promise<unknown> {
    const cid = String(id)
    const cached = this.characterCache.get(cid)
    if (cached && cached.expiresAt > Date.now()) {
      return cached.value
    }
    const inFlight = this.characterInFlight.get(cid)
    if (inFlight) return inFlight

    const request = (async () => {
      try {
        const template = await this.resolveApiPath("characters.get", [
          "/api/v1/characters/{id}",
          "/api/v1/characters/{id}/"
        ])
        const path = this.fillPathParams(template, cid)
        const value = await bgRequest<unknown>({
          path,
          method: 'GET'
        })
        this.characterCache.set(cid, {
          value,
          expiresAt: Date.now() + CHARACTER_CACHE_TTL_MS
        })
        return value
      } finally {
        this.characterInFlight.delete(cid)
      }
    })()

    this.characterInFlight.set(cid, request)
    return request
  }

  async createCharacter(payload: Record<string, unknown>): Promise<unknown> {
    const path = await this.resolveApiPath("characters.create", [
      "/api/v1/characters",
      "/api/v1/characters/"
    ])
    return await bgRequest<unknown>({
      path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload
    })
  }

  async importCharacterFile(
    file: File,
    options?: { allowImageOnly?: boolean }
  ): Promise<unknown> {
    const buffer = await file.arrayBuffer()
    const data = Array.from(new Uint8Array(buffer))
    const name = file.name || "character-card"
    const type = file.type || "application/octet-stream"
    const path = await this.resolveApiPath("characters.import", [
      "/api/v1/characters/import",
      "/api/v1/characters/import/"
    ])
    const fields = options?.allowImageOnly
      ? { allow_image_only: true }
      : undefined
    return await this.upload<unknown>({
      path,
      method: "POST",
      fileFieldName: "character_file",
      file: { name, type, data },
      fields
    })
  }

  async updateCharacter(
    id: string | number,
    payload: Record<string, unknown>,
    expectedVersion?: number
  ): Promise<unknown> {
    const cid = String(id)
    const qp = expectedVersion != null ? `?expected_version=${encodeURIComponent(String(expectedVersion))}` : ''
    const template = await this.resolveApiPath("characters.update", [
      "/api/v1/characters/{id}",
      "/api/v1/characters/{id}/"
    ])
    const path = appendPathQuery(this.fillPathParams(template, cid), qp)
    const res = await bgRequest<unknown>({
      path,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: payload
    })
    this.characterCache.delete(cid)
    return res
  }

  async deleteCharacter(id: string | number): Promise<void> {
    const cid = String(id)
    const template = await this.resolveApiPath("characters.delete", [
      "/api/v1/characters/{id}",
      "/api/v1/characters/{id}/"
    ])
    const path = this.fillPathParams(template, cid)
    await bgRequest<void>({ path, method: 'DELETE' })
    this.characterCache.delete(cid)
  }

  // Character chat sessions
  async listCharacterChatSessions(): Promise<unknown[]> {
    const path = await this.resolveApiPath("characterChatSessions.list", [
      "/api/v1/character-chat/sessions",
      "/api/v1/character_chat_sessions",
      "/api/v1/character_chat_sessions/"
    ])
    return await bgRequest<unknown[]>({ path, method: 'GET' })
  }

  async createCharacterChatSession(character_id: string): Promise<unknown> {
    const body = { character_id }
    const path = await this.resolveApiPath("characterChatSessions.create", [
      "/api/v1/character-chat/sessions",
      "/api/v1/character_chat_sessions",
      "/api/v1/character_chat_sessions/"
    ])
    return await bgRequest<unknown>({
      path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body
    })
  }

  async deleteCharacterChatSession(session_id: string | number): Promise<void> {
    const sid = String(session_id)
    const template = await this.resolveApiPath("characterChatSessions.delete", [
      "/api/v1/character-chat/sessions/{session_id}",
      "/api/v1/character_chat_sessions/{session_id}",
      "/api/v1/character_chat_sessions/{session_id}/"
    ])
    const path = this.fillPathParams(template, sid)
    await bgRequest<void>({ path, method: 'DELETE' })
  }

  // Character messages
  async listCharacterMessages(session_id: string | number): Promise<unknown[]> {
    const sid = String(session_id)
    const query = this.buildQuery({ session_id: sid })
    const template = await this.resolveApiPath("characterChatMessages.list", [
      "/api/v1/character-chat/sessions/{session_id}/messages",
      "/api/v1/character-messages",
      "/api/v1/character_messages"
    ])
    const path = template.includes("{")
      ? this.fillPathParams(template, sid)
      : appendPathQuery(template, query)
    return await bgRequest<unknown[]>({ path, method: 'GET' })
  }

  async sendCharacterMessage(
    session_id: string | number,
    content: string,
    options?: { extra?: Record<string, unknown> }
  ): Promise<unknown> {
    const sid = String(session_id)
    const body = { content, session_id: sid, ...(options?.extra || {}) }
    const template = await this.resolveApiPath("characterChatMessages.send", [
      "/api/v1/character-chat/sessions/{session_id}/messages",
      "/api/v1/character_messages",
      "/api/v1/character-messages"
    ])
    const path = template.includes("{")
      ? this.fillPathParams(template, sid)
      : template
    return await bgRequest<unknown>({
      path,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body
    })
  }

  async * streamCharacterMessage(
    session_id: string | number,
    content: string,
    options?: { extra?: Record<string, unknown> }
  ): AsyncGenerator<unknown> {
    const sid = String(session_id)
    const body = { content, session_id: sid, ...(options?.extra || {}) }
    const template = await this.resolveApiPath("characterChatMessages.stream", [
      "/api/v1/character-chat/sessions/{session_id}/messages/stream",
      "/api/v1/character_messages/stream",
      "/api/v1/character-messages/stream"
    ])
    const path = this.fillPathParams(template, sid)
    for await (const line of bgStream({ path, method: 'POST', headers: { 'Content-Type': 'application/json' }, body })) {
      try { yield JSON.parse(line) } catch {}
    }
  }

  private normalizeChatSummary(input: unknown): ServerChatSummary {
    const record = isRecord(input) ? input : {}
    const created_at = String(record.created_at || record.createdAt || "")
    const updated_at =
      record.updated_at ??
      record.updatedAt ??
      record.last_modified ??
      record.lastModified ??
      null
    const state = record.state ?? record.conversation_state ?? null
    return {
      id: String(record.id ?? ""),
      title: String(record.title || ""),
      created_at,
      updated_at: updated_at ? String(updated_at) : null,
      source: record.source ?? null,
      state: state ? String(state) : null,
      topic_label: record.topic_label ?? record.topicLabel ?? null,
      cluster_id: record.cluster_id ?? record.clusterId ?? null,
      external_ref: record.external_ref ?? record.externalRef ?? null,
      bm25_norm:
        typeof record.bm25_norm === "number"
          ? record.bm25_norm
          : typeof record.relevance === "number"
            ? record.relevance
            : null,
      character_id: record.character_id ?? record.characterId ?? null,
      parent_conversation_id:
        record.parent_conversation_id ?? record.parentConversationId ?? null,
      root_id: record.root_id ?? record.rootId ?? null,
      version:
        typeof record.version === "number"
          ? record.version
          : typeof record.expected_version === "number"
            ? record.expected_version
            : null
    }
  }

  // Chats API (resource-based)
  async listChatCommands(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/commands",
      method: "GET"
    })
  }

  async listChats(params?: Record<string, unknown>): Promise<ServerChatSummary[]> {
    const query = this.buildQuery(params)
    const data = await bgRequest<unknown>({
      path: `/api/v1/chats/${query}`,
      method: "GET"
    })

    let list: unknown[] = []

    if (Array.isArray(data)) {
      list = data
    } else if (isRecord(data)) {
      const candidates = [data.chats, data.items, data.results, data.data]
      for (const candidate of candidates) {
        if (Array.isArray(candidate)) {
          list = candidate
          break
        }
      }
    }

    return list.map((c) => this.normalizeChatSummary(c))
  }

  async createChat(payload: Record<string, unknown>): Promise<ServerChatSummary> {
    const res = await bgRequest<unknown>({
      path: "/api/v1/chats/",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
    return this.normalizeChatSummary(res)
  }

  async getChat(chat_id: string | number): Promise<ServerChatSummary> {
    const cid = String(chat_id)
    const res = await bgRequest<unknown>({
      path: `/api/v1/chats/${cid}`,
      method: "GET"
    })
    return this.normalizeChatSummary(res)
  }

  async updateChat(
    chat_id: string | number,
    payload: Record<string, unknown>,
    options?: { expectedVersion?: number }
  ): Promise<ServerChatSummary> {
    const cid = String(chat_id)
    let expectedVersion = options?.expectedVersion
    if (expectedVersion == null) {
      try {
        const current = await this.getChat(cid)
        if (typeof current?.version === "number") {
          expectedVersion = current.version
        }
      } catch {
        // ignore and fall back to unversioned update
      }
    }
    const qp =
      typeof expectedVersion === "number"
        ? `?expected_version=${encodeURIComponent(String(expectedVersion))}`
        : ""
    const res = await bgRequest<unknown>({
      path: `/api/v1/chats/${cid}${qp}`,
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
    return this.normalizeChatSummary(res)
  }

  async deleteChat(chat_id: string | number): Promise<void> {
    const cid = String(chat_id)
    await bgRequest<void>({ path: `/api/v1/chats/${cid}`, method: 'DELETE' })
  }

  async listChatMessages(
    chat_id: string | number,
    params?: Record<string, unknown>,
    options?: { signal?: AbortSignal }
  ): Promise<ServerChatMessage[]> {
    const cid = String(chat_id)
    const query = this.buildQuery(params)
    const cacheKey = this.getChatMessagesCacheKey(cid, query)
    const cached = this.chatMessagesCache.get(cacheKey)
    if (cached && cached.expiresAt > Date.now()) {
      return cached.value
    }
    if (cached) {
      this.chatMessagesCache.delete(cacheKey)
    }

    const inFlight = this.chatMessagesInFlight.get(cacheKey)
    if (inFlight) {
      return inFlight
    }

    const request = (async () => {
      const data = await bgRequest<unknown>({
        path: `/api/v1/chats/${cid}/messages${query}`,
        method: "GET",
        abortSignal: options?.signal
      })

      let list: unknown[] = []

      if (Array.isArray(data)) {
        list = data
      } else if (isRecord(data)) {
        const candidates = [data.messages, data.items, data.results, data.data]
        for (const candidate of candidates) {
          if (Array.isArray(candidate)) {
            list = candidate
            break
          }
        }
      }

      const normalized = list.map((item) => {
        const record = isRecord(item) ? item : {}
        const nested = isRecord(record.message) ? record.message : {}
        const roleCandidate =
          typeof record.role === "string"
            ? record.role
            : typeof record.sender === "string"
              ? record.sender
              : typeof record.author === "string"
                ? record.author
                : typeof nested.role === "string"
                  ? nested.role
                  : typeof nested.sender === "string"
                    ? nested.sender
                    : typeof nested.author === "string"
                      ? nested.author
                      : undefined
        const isBotFlag =
          typeof record.is_bot === "boolean"
            ? record.is_bot
            : typeof record.isBot === "boolean"
              ? record.isBot
              : null
        const role =
          isBotFlag !== null
            ? isBotFlag
              ? "assistant"
              : "user"
            : normalizeChatRole(roleCandidate)
        const created_at = String(
          record.created_at || record.createdAt || record.timestamp || ""
        )
        return {
          id: String(record.id ?? ""),
          role,
          content: String(record.content ?? ""),
          created_at,
          version:
            typeof record.version === "number"
              ? record.version
              : typeof record.expected_version === "number"
                ? record.expected_version
                : undefined
        } as ServerChatMessage
      })
      this.chatMessagesCache.set(cacheKey, {
        value: normalized,
        expiresAt: Date.now() + CHAT_MESSAGES_CACHE_TTL_MS
      })
      return normalized
    })()

    this.chatMessagesInFlight.set(cacheKey, request)
    try {
      return await request
    } finally {
      this.chatMessagesInFlight.delete(cacheKey)
    }
  }

  async addChatMessage(
    chat_id: string | number,
    payload: Record<string, unknown>
  ): Promise<ServerChatMessage> {
    const cid = String(chat_id)
    const res = await bgRequest<ServerChatMessage>({
      path: `/api/v1/chats/${cid}/messages`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
    this.invalidateChatMessagesCache(cid)
    return res
  }

  async prepareCharacterCompletion(
    chat_id: string | number,
    payload?: Record<string, unknown>
  ): Promise<unknown> {
    const cid = String(chat_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chats/${cid}/completions`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload || {}
    })
  }

  async persistCharacterCompletion(
    chat_id: string | number,
    payload: Record<string, unknown>
  ): Promise<unknown> {
    const cid = String(chat_id)
    const res = await bgRequest<unknown>({
      path: `/api/v1/chats/${cid}/completions/persist`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
    this.invalidateChatMessagesCache(cid)
    return res
  }

  async *streamCharacterChatCompletion(
    chat_id: string | number,
    payload?: Record<string, unknown>,
    options?: { signal?: AbortSignal; streamIdleTimeoutMs?: number }
  ): AsyncGenerator<unknown> {
    const cid = String(chat_id)
    const body = { ...(payload || {}), stream: true }
    for await (const line of bgStream({
      path: `/api/v1/chats/${cid}/complete-v2`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      abortSignal: options?.signal,
      streamIdleTimeoutMs: options?.streamIdleTimeoutMs
    })) {
      if (!line) continue
      try {
        const parsed = JSON.parse(line)
        yield parsed
      } catch {
        yield line
      }
    }
  }

  async searchChatMessages(
    chat_id: string | number,
    query: string,
    limit?: number
  ): Promise<unknown> {
    const cid = String(chat_id)
    const qp = `?query=${encodeURIComponent(query)}${typeof limit === 'number' ? `&limit=${encodeURIComponent(String(limit))}` : ''}`
    return await bgRequest<unknown>({ path: `/api/v1/chats/${cid}/messages/search${qp}`, method: 'GET' })
  }

  async completeChat(chat_id: string | number, payload?: Record<string, unknown>): Promise<unknown> {
    const cid = String(chat_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chats/${cid}/complete`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload || {}
    })
  }

  async * streamCompleteChat(
    chat_id: string | number,
    payload?: Record<string, unknown>
  ): AsyncGenerator<unknown> {
    const cid = String(chat_id)
    for await (const line of bgStream({ path: `/api/v1/chats/${cid}/complete`, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload || {} })) {
      try { yield JSON.parse(line) } catch {}
    }
  }

  // Message (single) APIs
  async getMessage(message_id: string | number): Promise<unknown> {
    const mid = String(message_id)
    return await bgRequest<unknown>({ path: `/api/v1/messages/${mid}`, method: 'GET' })
  }

  async editMessage(
    message_id: string | number,
    content: string,
    expectedVersion: number,
    chatId?: string | number
  ): Promise<unknown> {
    const mid = String(message_id)
    const qp = `?expected_version=${encodeURIComponent(String(expectedVersion))}`
    const res = await bgRequest<unknown>({
      path: `/api/v1/messages/${mid}${qp}`,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: { content }
    })
    if (chatId != null) {
      this.invalidateChatMessagesCache(chatId)
    }
    return res
  }

  async deleteMessage(
    message_id: string | number,
    expectedVersion: number,
    chatId?: string | number
  ): Promise<void> {
    const mid = String(message_id)
    const qp = `?expected_version=${encodeURIComponent(String(expectedVersion))}`
    await bgRequest<void>({
      path: `/api/v1/messages/${mid}${qp}`,
      method: 'DELETE'
    })
    if (chatId != null) {
      this.invalidateChatMessagesCache(chatId)
    }
  }

  async saveChatKnowledge(payload: {
    conversation_id: string | number
    message_id: string | number
    snippet: string
    tags?: string[]
    make_flashcard?: boolean
  }): Promise<unknown> {
    const body = {
      ...payload,
      conversation_id: String(payload.conversation_id),
      message_id: String(payload.message_id)
    }
    return await bgRequest<unknown>({
      path: "/api/v1/chat/knowledge/save",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body
    })
  }

  // World Books
  async listWorldBooks(include_disabled?: boolean): Promise<unknown> {
    const qp = include_disabled ? `?include_disabled=true` : ''
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books${qp}`, method: 'GET' })
  }

  async createWorldBook(payload: Record<string, unknown>): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/api/v1/characters/world-books', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async updateWorldBook(world_book_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}`, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async deleteWorldBook(world_book_id: number | string): Promise<unknown> {
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}`, method: 'DELETE' })
  }

  async listWorldBookEntries(world_book_id: number | string, enabled_only?: boolean): Promise<unknown> {
    const wid = String(world_book_id)
    const qp = enabled_only ? `?enabled_only=true` : ''
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}/entries${qp}`, method: 'GET' })
  }

  async addWorldBookEntry(world_book_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}/entries`, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async updateWorldBookEntry(entry_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const eid = String(entry_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/entries/${eid}`, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async deleteWorldBookEntry(entry_id: number | string): Promise<unknown> {
    const eid = String(entry_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/entries/${eid}`, method: 'DELETE' })
  }

  async attachWorldBookToCharacter(character_id: number | string, world_book_id: number | string): Promise<unknown> {
    const cid = String(character_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/${cid}/world-books`, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: { world_book_id: Number(world_book_id) } })
  }

  async detachWorldBookFromCharacter(character_id: number | string, world_book_id: number | string): Promise<unknown> {
    const cid = String(character_id)
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/${cid}/world-books/${wid}`, method: 'DELETE' })
  }

  async listCharacterWorldBooks(character_id: number | string): Promise<unknown> {
    const cid = String(character_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/${cid}/world-books`, method: 'GET' })
  }

  async exportWorldBook(world_book_id: number | string): Promise<unknown> {
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}/export`, method: 'GET' })
  }

  async importWorldBook(request: { world_book: Record<string, unknown>; entries?: unknown[]; merge_on_conflict?: boolean }): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/api/v1/characters/world-books/import', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: request })
  }

  async worldBookStatistics(world_book_id: number | string): Promise<unknown> {
    const wid = String(world_book_id)
    return await bgRequest<unknown>({ path: `/api/v1/characters/world-books/${wid}/statistics`, method: 'GET' })
  }

  // Chat Dictionaries
  async createDictionary(payload: Record<string, unknown>): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/api/v1/chat/dictionaries', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async listDictionaries(include_inactive?: boolean): Promise<unknown> {
    const qp = include_inactive ? `?include_inactive=true` : ''
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries${qp}`, method: 'GET' })
  }

  async getDictionary(dictionary_id: number | string): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}`, method: 'GET' })
  }

  async updateDictionary(dictionary_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}`, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async deleteDictionary(dictionary_id: number | string, hard_delete?: boolean): Promise<unknown> {
    const id = String(dictionary_id)
    const qp = hard_delete ? `?hard_delete=true` : ''
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}${qp}`, method: 'DELETE' })
  }

  async listDictionaryEntries(dictionary_id: number | string, group?: string): Promise<unknown> {
    const id = String(dictionary_id)
    const qp = group ? `?group=${encodeURIComponent(group)}` : ''
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}/entries${qp}`, method: 'GET' })
    }

  async addDictionaryEntry(dictionary_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}/entries`, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async updateDictionaryEntry(entry_id: number | string, payload: Record<string, unknown>): Promise<unknown> {
    const eid = String(entry_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/entries/${eid}`, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: payload })
  }

  async deleteDictionaryEntry(entry_id: number | string): Promise<unknown> {
    const eid = String(entry_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/entries/${eid}`, method: 'DELETE' })
  }

  async exportDictionaryMarkdown(dictionary_id: number | string): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}/export/markdown`, method: 'GET' })
  }

  async exportDictionaryJSON(dictionary_id: number | string): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}/export/json`, method: 'GET' })
  }

  async importDictionaryJSON(data: unknown, activate?: boolean): Promise<unknown> {
    return await bgRequest<unknown>({ path: '/api/v1/chat/dictionaries/import/json', method: 'POST', headers: { 'Content-Type': 'application/json' }, body: { data, activate: !!activate } })
  }

  async validateDictionary(payload: {
    data: Record<string, unknown>
    schema_version?: number
    strict?: boolean
  }): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/dictionaries/validate",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async processDictionary(payload: {
    text: string
    token_budget?: number
    dictionary_id?: number | string
    max_iterations?: number
  }): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/dictionaries/process",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async dictionaryStatistics(dictionary_id: number | string): Promise<unknown> {
    const id = String(dictionary_id)
    return await bgRequest<unknown>({ path: `/api/v1/chat/dictionaries/${id}/statistics`, method: 'GET' })
  }

  // Chat Documents
  async generateChatDocument(payload: {
    conversation_id: string | number
    document_type: string
    provider: string
    model: string
    specific_message?: string | null
    custom_prompt?: string | null
    stream?: boolean
    async_generation?: boolean
  }): Promise<unknown> {
    const body = {
      ...payload,
      conversation_id: String(payload.conversation_id)
    }
    return await bgRequest<unknown>({
      path: "/api/v1/chat/documents/generate",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body
    })
  }

  async listChatDocuments(params?: {
    conversation_id?: string | number
    document_type?: string
    limit?: number
  }): Promise<unknown> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents${query}`,
      method: "GET"
    })
  }

  async getChatDocument(document_id: number | string): Promise<unknown> {
    const id = String(document_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents/${id}`,
      method: "GET"
    })
  }

  async deleteChatDocument(document_id: number | string): Promise<unknown> {
    const id = String(document_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents/${id}`,
      method: "DELETE"
    })
  }

  async getChatDocumentJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents/jobs/${id}`,
      method: "GET"
    })
  }

  async cancelChatDocumentJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents/jobs/${id}`,
      method: "DELETE"
    })
  }

  async saveChatDocumentPrompt(payload: {
    document_type: string
    system_prompt: string
    user_prompt: string
    temperature?: number
    max_tokens?: number
  }): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/documents/prompts",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async getChatDocumentPrompt(document_type: string): Promise<unknown> {
    return await bgRequest<unknown>({
      path: `/api/v1/chat/documents/prompts/${encodeURIComponent(document_type)}`,
      method: "GET"
    })
  }

  async chatDocumentStatistics(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/documents/statistics",
      method: "GET"
    })
  }

  // Chatbooks
  async exportChatbook(payload: {
    name: string
    description: string
    content_selections: Record<string, string[]>
    author?: string
    include_media?: boolean
    media_quality?: string
    include_embeddings?: boolean
    include_generated_content?: boolean
    tags?: string[]
    categories?: string[]
    async_mode?: boolean
  }): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chatbooks/export",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async previewChatbook(file: File): Promise<unknown> {
    const data = await file.arrayBuffer()
    const name = file.name || "chatbook.zip"
    const type = file.type || "application/zip"
    return await bgUpload<unknown>({
      path: "/api/v1/chatbooks/preview",
      method: "POST",
      file: { name, type, data }
    })
  }

  async importChatbook(
    file: File,
    options?: {
      conflict_resolution?: string
      prefix_imported?: boolean
      import_media?: boolean
      import_embeddings?: boolean
      async_mode?: boolean
      content_selections?: Record<string, string[]>
    }
  ): Promise<unknown> {
    const data = await file.arrayBuffer()
    const name = file.name || "chatbook.zip"
    const type = file.type || "application/zip"
    const normalized: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(options || {})) {
      if (typeof v === "undefined" || v === null) continue
      normalized[k] = typeof v === "boolean" ? (v ? "true" : "false") : v
    }
    return await bgUpload<unknown>({
      path: "/api/v1/chatbooks/import",
      method: "POST",
      fields: normalized,
      file: { name, type, data }
    })
  }

  async listChatbookExportJobs(params?: { limit?: number; offset?: number }): Promise<unknown> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/export/jobs${query}`,
      method: "GET"
    })
  }

  async listChatbookImportJobs(params?: { limit?: number; offset?: number }): Promise<unknown> {
    const query = this.buildQuery(params as Record<string, unknown>)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/import/jobs${query}`,
      method: "GET"
    })
  }

  async getChatbookExportJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/export/jobs/${id}`,
      method: "GET"
    })
  }

  async getChatbookImportJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/import/jobs/${id}`,
      method: "GET"
    })
  }

  async cancelChatbookExportJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/export/jobs/${id}`,
      method: "DELETE"
    })
  }

  async cancelChatbookImportJob(job_id: string): Promise<unknown> {
    const id = String(job_id)
    return await bgRequest<unknown>({
      path: `/api/v1/chatbooks/import/jobs/${id}`,
      method: "DELETE"
    })
  }

  async cleanupChatbooks(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chatbooks/cleanup",
      method: "POST"
    })
  }

  async chatbooksHealth(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chatbooks/health",
      method: "GET"
    })
  }

  async downloadChatbookExport(job_id: string): Promise<{ blob: Blob; filename: string }> {
    await this.ensureConfigForRequest(true)
    const response = await this.request<{
      ok: boolean
      status: number
      data?: ArrayBuffer
      error?: string
      headers?: Record<string, string>
    }>({
      path: `/api/v1/chatbooks/download/${encodeURIComponent(job_id)}`,
      method: "GET",
      headers: { Accept: "application/octet-stream" },
      responseType: "arrayBuffer",
      returnResponse: true
    })
    if (!response) {
      throw new Error("Download failed")
    }
    if (!response.ok) {
      throw new Error(response.error || `Download failed: ${response.status}`)
    }
    const headers = new Headers(response.headers || {})
    const blob = new Blob([response.data ?? new Uint8Array()], {
      type: headers.get("content-type") || "application/octet-stream"
    })
    const disposition = headers.get("content-disposition")
    let filename = `chatbook-${job_id}.zip`
    if (disposition) {
      const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
      const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
      const raw = utfMatch?.[1] || plainMatch?.[1]
      if (raw) {
        try {
          filename = decodeURIComponent(raw)
        } catch {
          filename = raw
        }
      }
    }
    return { blob, filename }
  }

  async chatQueueStatus(): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/chat/queue/status",
      method: "GET"
    })
  }

  async chatQueueActivity(limit?: number): Promise<unknown> {
    const query = this.buildQuery(
      typeof limit === "number" ? { limit } : undefined
    )
    return await bgRequest<unknown>({
      path: `/api/v1/chat/queue/activity${query}`,
      method: "GET"
    })
  }

  // STT Methods
  async getTranscriptionModels(): Promise<unknown> {
    await this.ensureConfigForRequest(true)
    return await bgRequest<unknown>({
      path: "/api/v1/media/transcription-models",
      method: "GET"
    })
  }

  async getTranscriptionModelHealth(model: string): Promise<unknown> {
    await this.ensureConfigForRequest(true)
    const query = this.buildQuery({ model })
    return await bgRequest<unknown>({
      path: `/api/v1/audio/transcriptions/health${query}`,
      method: "GET"
    })
  }

  async transcribeAudio(audioFile: File | Blob, options?: Record<string, unknown>): Promise<unknown> {
    await this.ensureConfigForRequest(true)
    const fields: Record<string, unknown> = {}
    const opts = isRecord(options) ? options : {}
    if (opts.model != null) fields.model = opts.model
    if (opts.language != null) fields.language = opts.language
    if (opts.prompt != null) fields.prompt = opts.prompt
    if (opts.response_format != null) fields.response_format = opts.response_format
    if (opts.temperature != null) fields.temperature = opts.temperature
    if (opts.task != null) fields.task = opts.task
    if (opts.timestamp_granularities != null) {
      fields.timestamp_granularities = opts.timestamp_granularities
    }
    if (opts.segment != null) fields.segment = opts.segment
    if (opts.seg_K != null) fields.seg_K = opts.seg_K
    if (opts.seg_min_segment_size != null) {
      fields.seg_min_segment_size = opts.seg_min_segment_size
    }
    if (opts.seg_lambda_balance != null) {
      fields.seg_lambda_balance = opts.seg_lambda_balance
    }
    if (opts.seg_utterance_expansion_width != null) {
      fields.seg_utterance_expansion_width = opts.seg_utterance_expansion_width
    }
    if (opts.seg_embeddings_provider != null) {
      fields.seg_embeddings_provider = opts.seg_embeddings_provider
    }
    if (opts.seg_embeddings_model != null) {
      fields.seg_embeddings_model = opts.seg_embeddings_model
    }
    const data = await audioFile.arrayBuffer()
    const name = (typeof File !== 'undefined' && audioFile instanceof File && (audioFile as File).name) ? (audioFile as File).name : 'audio'
    const type =
      typeof (audioFile as Blob).type === "string" && (audioFile as Blob).type
        ? (audioFile as Blob).type
        : 'application/octet-stream'
    return await this.upload<unknown>({ path: '/api/v1/audio/transcriptions', method: 'POST', fields, file: { name, type, data } })
  }

  async synthesizeSpeech(
    text: string,
    options?: { voice?: string; model?: string; responseFormat?: string; speed?: number }
  ): Promise<ArrayBuffer> {
    await this.ensureConfigForRequest(true)
    const body: Record<string, unknown> = { input: text, text }
    if (options?.voice) body.voice = options.voice
    if (options?.model) body.model = options.model
    if (options?.responseFormat) body.response_format = options.responseFormat
    if (options?.speed != null) body.speed = options.speed
    const response = await this.request<{
      ok: boolean
      status: number
      data?: ArrayBuffer
      error?: string
    }>({
      path: "/api/v1/audio/speech",
      method: "POST",
      headers: { Accept: "audio/mpeg" },
      body,
      responseType: "arrayBuffer",
      returnResponse: true
    })
    if (!response) {
      throw new Error("TTS failed")
    }
    if (!response.ok) {
      throw new Error(response.error || `TTS failed (HTTP ${response.status})`)
    }
    return response.data ?? new ArrayBuffer(0)
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Data Tables API
  // ─────────────────────────────────────────────────────────────────────────

  async listDataTables(params?: {
    page?: number
    page_size?: number
    limit?: number
    offset?: number
    search?: string
    status?: string
  }): Promise<{ tables: unknown[]; total: number }> {
    const limit = params?.limit ?? params?.page_size ?? 20
    const page = params?.page ?? 1
    const offset = params?.offset ?? Math.max(0, (page - 1) * limit)
    const query = this.buildQuery({
      limit,
      offset,
      search: params?.search,
      status_filter: params?.status
    } as Record<string, unknown>)
    const response = await bgRequest<unknown>({
      path: `/api/v1/data-tables${query}`,
      method: "GET"
    })
    return mapApiListToUi(response)
  }

  async getDataTable(
    tableId: string,
    params?: {
      rows_limit?: number
      rows_offset?: number
      include_rows?: boolean
      include_sources?: boolean
    }
  ): Promise<unknown> {
    const id = encodeURIComponent(tableId)
    const query = this.buildQuery({
      rows_limit: params?.rows_limit,
      rows_offset: params?.rows_offset,
      include_rows: params?.include_rows,
      include_sources: params?.include_sources
    } as Record<string, unknown>)
    const response = await bgRequest<unknown>({
      path: `/api/v1/data-tables/${id}${query}`,
      method: "GET"
    })
    return isRecord(response) && response.table
      ? mapApiDetailToUi(response as ApiDataTableDetailResponse)
      : response
  }

  async generateDataTable(payload: {
    name: string
    prompt: string
    sources: DataTableSource[]
    column_hints?: Array<{ name?: string; type?: string; description?: string; format?: string }>
    model?: string
    max_rows?: number
  }): Promise<ApiDataTableGenerateResponse> {
    const body = {
      name: payload.name,
      prompt: payload.prompt,
      sources: payload.sources.map(mapUiSourceToApi),
      column_hints: payload.column_hints,
      model: payload.model,
      max_rows: payload.max_rows
    }
    return await bgRequest<ApiDataTableGenerateResponse>({
      path: "/api/v1/data-tables/generate",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body
    })
  }

  async updateDataTable(
    tableId: string,
    payload: { name?: string; description?: string }
  ): Promise<unknown> {
    const id = encodeURIComponent(tableId)
    return await bgRequest<unknown>({
      path: `/api/v1/data-tables/${id}`,
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
  }

  async saveDataTableContent(
    tableId: string,
    payload: {
      columns: DataTableColumn[]
      rows: Record<string, unknown>[]
    }
  ): Promise<unknown> {
    const id = encodeURIComponent(tableId)
    const body = buildContentPayload(payload.columns, payload.rows)
    const response = await bgRequest<unknown>({
      path: `/api/v1/data-tables/${id}/content`,
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body
    })
    return isRecord(response) && response.table
      ? mapApiDetailToUi(response as ApiDataTableDetailResponse)
      : response
  }

  async deleteDataTable(tableId: string): Promise<void> {
    const id = encodeURIComponent(tableId)
    await bgRequest<void>({
      path: `/api/v1/data-tables/${id}`,
      method: "DELETE"
    })
  }

  async getDataTableJob(jobId: number): Promise<ApiDataTableJobStatus> {
    return await bgRequest<ApiDataTableJobStatus>({
      path: `/api/v1/data-tables/jobs/${encodeURIComponent(String(jobId))}`,
      method: "GET"
    })
  }

  async regenerateDataTable(
    tableId: string,
    payload?: { prompt?: string; model?: string; max_rows?: number }
  ): Promise<ApiDataTableGenerateResponse> {
    const id = encodeURIComponent(tableId)
    return await bgRequest<ApiDataTableGenerateResponse>({
      path: `/api/v1/data-tables/${id}/regenerate`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload || {}
    })
  }

  async exportDataTable(
    tableId: string,
    format: "csv" | "xlsx" | "json"
  ): Promise<{ blob: Blob; filename: string }> {
    await this.ensureConfigForRequest(true)

    const fallbackFilename = `data-table-${tableId}.${format}`
    const resolveFilename = (res: Response) => {
      const disposition = res.headers.get("content-disposition")
      if (!disposition) return fallbackFilename
      const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
      const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
      const raw = utfMatch?.[1] || plainMatch?.[1]
      if (!raw) return fallbackFilename
      try {
        return decodeURIComponent(raw)
      } catch {
        return raw
      }
    }
    const readErrorDetail = async (res: Response) => {
      try {
        const data = await res.json()
        return data?.detail || data?.error || data?.message
      } catch {
        return undefined
      }
    }
    const requestWithAuth = async (
      path: PathOrUrl,
      options?: {
        method?: "GET" | "POST" | "PUT" | "DELETE"
        body?: unknown
        signal?: AbortSignal
      }
    ) => {
      const response = await bgRequest<{
        ok: boolean
        status: number
        data?: unknown
        error?: string
        headers?: Record<string, string>
      }, PathOrUrl>({
        path,
        method: options?.method ?? "GET",
        body: options?.body,
        abortSignal: options?.signal,
        responseType: "arrayBuffer",
        returnResponse: true
      })
      if (!response) {
        throw new Error(`Request failed (${options?.method ?? "GET"} ${path})`)
      }
      if (!response.ok && response.status === 0) {
        throw new Error(response.error || "Network error")
      }
      const headers = new Headers(response.headers || {})
      let body: BodyInit | null = null
      if (response.data instanceof ArrayBuffer) {
        body = response.data
      } else if (response.data instanceof Uint8Array) {
        body = response.data.buffer as BodyInit
      } else if (response.data instanceof Blob) {
        body = response.data
      } else if (typeof response.data === "string") {
        body = response.data
      } else if (response.data != null) {
        body = JSON.stringify(response.data)
        if (!headers.has("content-type")) {
          headers.set("content-type", "application/json")
        }
      }
      return new Response(body, { status: response.status, headers })
    }
    const readBlobResponse = async (res: Response) => {
      const blob = await res.blob()
      return { blob, filename: resolveFilename(res) }
    }
    const decodeBase64Blob = (data: string, contentType?: string | null) => {
      const binary = atob(data)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i)
      }
      return new Blob([bytes], {
        type: contentType || "application/octet-stream"
      })
    }
    const waitForExportReady = async (fileId: number) => {
      const timeoutMs = 5 * 60 * 1000
      const intervalMs = 1500
      const start = Date.now()
      while (Date.now() - start < timeoutMs) {
        const statusRes = await requestWithAuth(`/api/v1/files/${fileId}`)
        if (!statusRes.ok) {
          const detail = await readErrorDetail(statusRes)
          throw new Error(detail || `Export status failed: ${statusRes.status}`)
        }
        const payload = await statusRes.json()
        const exportInfo = payload?.artifact?.export || payload?.export
        if (exportInfo?.status === "ready") {
          return exportInfo
        }
        if (exportInfo?.status && exportInfo.status !== "pending") {
          throw new Error("Export failed")
        }
        await new Promise((resolve) => setTimeout(resolve, intervalMs))
      }
      throw new Error("Export timed out")
    }
    const downloadFromUrl = async (url: string) => {
      const resolved = url.startsWith("http")
        ? (url as PathOrUrl)
        : ((url.startsWith("/") ? url : `/${url}`) as PathOrUrl)
      const fileRes = await requestWithAuth(resolved)
      if (!fileRes.ok) {
        const detail = await readErrorDetail(fileRes)
        throw new Error(detail || `Export download failed: ${fileRes.status}`)
      }
      return await readBlobResponse(fileRes)
    }
    const exportViaArtifact = async () => {
      const exportUrl =
        `/api/v1/data-tables/${encodeURIComponent(tableId)}/export?format=${encodeURIComponent(
          format
        )}&async_mode=auto&mode=url` as AllowedPath
      const exportRes = await requestWithAuth(exportUrl)
      if (!exportRes.ok) {
        const detail = await readErrorDetail(exportRes)
        throw new Error(detail || `Export failed: ${exportRes.status}`)
      }
      const contentType = exportRes.headers.get("content-type") || ""
      if (!contentType.includes("application/json")) {
        return await readBlobResponse(exportRes)
      }
      const payload = await exportRes.json()
      const exportInfo = payload?.export || payload?.artifact?.export
      const fileId = payload?.file_id || payload?.artifact?.file_id
      if (exportInfo?.content_b64) {
        const blob = decodeBase64Blob(
          exportInfo.content_b64,
          exportInfo.content_type
        )
        return { blob, filename: resolveFilename(exportRes) }
      }
      if (!fileId) {
        throw new Error("Export response missing file id")
      }
      const resolvedExport =
        exportInfo?.status === "pending" ? await waitForExportReady(fileId) : exportInfo
      if (!resolvedExport?.url) {
        throw new Error("Export URL missing")
      }
      return await downloadFromUrl(resolvedExport.url)
    }

    const url =
      `/api/v1/data-tables/${encodeURIComponent(tableId)}/export?format=${encodeURIComponent(
        format
      )}&download=true` as AllowedPath
    const res = await requestWithAuth(url)

    if (!res.ok) {
      const detail = await readErrorDetail(res)
      if (res.status === 422 && detail === "export_size_exceeded") {
        return await exportViaArtifact()
      }
      throw new Error(detail || `Export failed: ${res.status}`)
    }

    return await readBlobResponse(res)
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Collections / Reading List API
  // ─────────────────────────────────────────────────────────────────────────────

  async getReadingList(params?: {
    page?: number
    size?: number
    q?: string
    status?: string | string[]
    tags?: string[]
    favorite?: boolean
    sort?: string
    domain?: string
    date_from?: string
    date_to?: string
  }): Promise<unknown> {
    const query = new URLSearchParams()
    if (params?.page) query.set("page", String(params.page))
    if (params?.size) query.set("size", String(params.size))
    if (params?.q) query.set("q", params.q)
    if (params?.status) {
      const statuses = Array.isArray(params.status) ? params.status : [params.status]
      statuses.filter(Boolean).forEach((status) => query.append("status", status))
    }
    if (params?.tags?.length) params.tags.forEach((tag) => query.append("tags", tag))
    if (params?.favorite !== undefined) query.set("favorite", String(params.favorite))
    if (params?.sort) query.set("sort", params.sort)
    if (params?.domain) query.set("domain", params.domain)
    if (params?.date_from) query.set("date_from", params.date_from)
    if (params?.date_to) query.set("date_to", params.date_to)
    const qs = query.toString()
    const path = `/api/v1/reading/items${qs ? `?${qs}` : ""}` as const
    const data = await bgRequest<unknown>({ path, method: "GET" })
    const record = isRecord(data) ? data : {}
    const items = Array.isArray(record.items)
      ? record.items.map((item) => {
          const entry = isRecord(item) ? item : {}
          return {
            id: String(entry.id ?? ""),
            title: entry.title || entry.url || "Untitled",
            url: entry.url,
            canonical_url: entry.canonical_url,
            domain: entry.domain,
            summary: entry.summary ?? undefined,
            notes: entry.notes ?? undefined,
            status: entry.status ?? "saved",
            favorite: Boolean(entry.favorite),
            tags: Array.isArray(entry.tags) ? entry.tags : [],
            reading_time_minutes: entry.reading_time_minutes,
            created_at: entry.created_at,
            updated_at: entry.updated_at,
            published_at: entry.published_at
          }
        })
      : []
    return {
      ...record,
      items,
      total: record.total ?? items.length,
      page: record.page ?? params?.page ?? 1,
      size: record.size ?? params?.size ?? items.length
    }
  }

  async getReadingItem(itemId: string): Promise<unknown> {
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}` as const
    const item = await bgRequest<unknown>({ path, method: "GET" })
    const record = isRecord(item) ? item : {}
    return {
      ...record,
      id: String(record.id ?? ""),
      media_id: record.media_id ? String(record.media_id) : undefined,
      favorite: Boolean(record.favorite),
      tags: Array.isArray(record.tags) ? record.tags : []
    }
  }

  async addReadingItem(data: {
    url: string
    title?: string
    tags?: string[]
    notes?: string
    status?: string
    favorite?: boolean
    summary?: string
    content?: string
  }): Promise<unknown> {
    return await bgRequest<unknown>({
      path: "/api/v1/reading/save",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: data
    })
  }

  async updateReadingItem(
    itemId: string,
    data: {
      status?: string
      favorite?: boolean
      tags?: string[]
      notes?: string
      title?: string
    }
  ): Promise<unknown> {
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}` as const
    return await bgRequest<unknown>({
      path,
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: data
    })
  }

  async deleteReadingItem(itemId: string, options?: { hard?: boolean }): Promise<void> {
    const query = new URLSearchParams()
    if (options?.hard !== undefined) query.set("hard", String(options.hard))
    const qs = query.toString()
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}${qs ? `?${qs}` : ""}` as const
    await bgRequest<void>({ path, method: "DELETE" })
  }

  async summarizeReadingItem(
    itemId: string,
    options?: {
      provider?: string
      model?: string
      prompt?: string
      system_prompt?: string
      temperature?: number
      recursive?: boolean
      chunked?: boolean
    }
  ): Promise<{ summary: string; provider: string; model?: string }> {
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}/summarize` as const
    const response = await bgRequest<unknown>({
      path,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: options || {}
    })
    return response as { summary: string; provider: string; model?: string }
  }

  async generateReadingItemTts(
    itemId: string,
    options?: { voice?: string }
  ): Promise<{ audio_url: string }> {
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}/tts` as const
    const data = await bgRequest<ArrayBuffer>({
      path,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        response_format: "mp3",
        stream: false,
        ...(options || {})
      },
      responseType: "arrayBuffer"
    })
    const blob = new Blob([data], { type: "audio/mpeg" })
    return { audio_url: URL.createObjectURL(blob) }
  }

  // Highlights
  async getHighlights(itemId: string): Promise<unknown[]> {
    const path = `/api/v1/reading/items/${encodeURIComponent(itemId)}/highlights` as const
    const data = await bgRequest<unknown>({ path, method: "GET" })
    return Array.isArray(data)
      ? data.map((highlight) => {
          const record = isRecord(highlight) ? highlight : {}
          return {
            ...record,
            id: String(record.id ?? ""),
            item_id: String(record.item_id ?? ""),
            color: record.color || "yellow",
            anchor_strategy: record.anchor_strategy || "fuzzy_quote",
            state: record.state || "active"
          }
        })
      : []
  }

  async createHighlight(data: {
    item_id: string
    quote: string
    note?: string
    color?: string
    start_offset?: number
    end_offset?: number
    anchor_strategy?: string
  }): Promise<unknown> {
    const path = `/api/v1/reading/items/${encodeURIComponent(data.item_id)}/highlight` as const
    const payload = {
      item_id: Number(data.item_id),
      quote: data.quote,
      note: data.note,
      color: data.color,
      start_offset: data.start_offset,
      end_offset: data.end_offset,
      anchor_strategy: data.anchor_strategy
    }
    const highlight = await bgRequest<unknown>({
      path,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload
    })
    const record = isRecord(highlight) ? highlight : {}
    return {
      ...record,
      id: String(record.id ?? ""),
      item_id: String(record.item_id ?? ""),
      color: record.color || "yellow",
      anchor_strategy: record.anchor_strategy || "fuzzy_quote",
      state: record.state || "active"
    }
  }

  async updateHighlight(
    highlightId: string,
    data: { note?: string; color?: string; state?: string }
  ): Promise<unknown> {
    const path = `/api/v1/reading/highlights/${encodeURIComponent(highlightId)}` as const
    const highlight = await bgRequest<unknown>({
      path,
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: data
    })
    const record = isRecord(highlight) ? highlight : {}
    return {
      ...record,
      id: String(record.id ?? ""),
      item_id: String(record.item_id ?? ""),
      color: record.color || "yellow",
      anchor_strategy: record.anchor_strategy || "fuzzy_quote",
      state: record.state || "active"
    }
  }

  async deleteHighlight(highlightId: string): Promise<void> {
    const path = `/api/v1/reading/highlights/${encodeURIComponent(highlightId)}` as const
    await bgRequest<void>({ path, method: "DELETE" })
  }

  // Output Templates
  async getOutputTemplates(params?: {
    q?: string
    limit?: number
    offset?: number
  }): Promise<unknown> {
    const query = new URLSearchParams()
    if (params?.q) query.set("q", params.q)
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset !== undefined) query.set("offset", String(params.offset))
    const qs = query.toString()
    const path = `/api/v1/outputs/templates${qs ? `?${qs}` : ""}` as const
    const data = await bgRequest<unknown>({ path, method: "GET" })
    const record = isRecord(data) ? data : {}
    const items = Array.isArray(record.items)
      ? record.items.map((template) => {
          const entry = isRecord(template) ? template : {}
          return {
            ...entry,
            id: String(entry.id ?? "")
          }
        })
      : []
    return {
      ...record,
      items,
      total: record.total ?? items.length
    }
  }

  async createOutputTemplate(data: {
    name: string
    description?: string
    type: string
    format: string
    body: string
    is_default?: boolean
  }): Promise<unknown> {
    const template = await bgRequest<unknown>({
      path: "/api/v1/outputs/templates",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: data
    })
    const record = isRecord(template) ? template : {}
    return { ...record, id: String(record.id ?? "") }
  }

  async updateOutputTemplate(
    templateId: string,
    data: {
      name?: string
      description?: string
      body?: string
      is_default?: boolean
      type?: string
      format?: string
    }
  ): Promise<unknown> {
    const path = `/api/v1/outputs/templates/${encodeURIComponent(templateId)}` as const
    const template = await bgRequest<unknown>({
      path,
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: data
    })
    const record = isRecord(template) ? template : {}
    return { ...record, id: String(record.id ?? "") }
  }

  async deleteOutputTemplate(templateId: string): Promise<void> {
    const path = `/api/v1/outputs/templates/${encodeURIComponent(templateId)}` as const
    await bgRequest<void>({ path, method: "DELETE" })
  }

  async previewTemplate(data: {
    template_id: string
    item_ids?: string[]
    run_id?: string
    limit?: number
    data?: Record<string, unknown>
  }): Promise<{ rendered: string; format: string }> {
    const path = `/api/v1/outputs/templates/${encodeURIComponent(data.template_id)}/preview` as const
    return await bgRequest<{ rendered: string; format: string }>({
      path,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        template_id: Number(data.template_id),
        item_ids: data.item_ids?.map((id) => Number(id)),
        run_id: data.run_id ? Number(data.run_id) : undefined,
        limit: data.limit,
        data: data.data
      }
    })
  }

  async generateOutput(data: {
    template_id: string
    item_ids?: string[]
    run_id?: string
    title?: string
    data?: Record<string, unknown>
  }): Promise<unknown> {
    const output = await bgRequest<unknown>({
      path: "/api/v1/outputs",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        template_id: Number(data.template_id),
        item_ids: data.item_ids?.map((id) => Number(id)),
        run_id: data.run_id ? Number(data.run_id) : undefined,
        title: data.title,
        data: data.data
      }
    })
    const record = isRecord(output) ? output : {}
    return { ...record, id: String(record.id ?? "") }
  }

  async downloadOutput(outputId: string, format?: string): Promise<Blob> {
    const path = `/api/v1/outputs/${encodeURIComponent(outputId)}/download` as const
    const data = await bgRequest<ArrayBuffer>({
      path,
      method: "GET",
      responseType: "arrayBuffer"
    })
    const mime =
      format === "html"
        ? "text/html"
        : format === "md"
          ? "text/markdown"
          : format === "mp3"
            ? "audio/mpeg"
            : "application/octet-stream"
    return new Blob([data], { type: mime })
  }

  // Import/Export
  async importReadingList(data: {
    source: string
    file: File
    merge_tags?: boolean
  }): Promise<ReadingImportJobResponse> {
    const buffer = await data.file.arrayBuffer()
    const fileData = Array.from(new Uint8Array(buffer))
    return await this.upload<ReadingImportJobResponse>({
      path: "/api/v1/reading/import",
      method: "POST",
      fileFieldName: "file",
      file: {
        name: data.file.name,
        type: data.file.type || "application/octet-stream",
        data: fileData
      },
      fields: {
        source: data.source,
        merge_tags: data.merge_tags ?? true
      }
    })
  }

  async getReadingImportJob(jobId: string | number): Promise<ReadingImportJobDetail> {
    const id = String(jobId)
    const path = `/api/v1/reading/import/jobs/${encodeURIComponent(id)}` as const
    return await this.request<ReadingImportJobDetail>({
      path,
      method: "GET"
    })
  }

  async exportReadingList(params: {
    format: string
    status?: string[]
    tags?: string[]
    favorite?: boolean
    q?: string
    domain?: string
    page?: number
    size?: number
  }): Promise<{ blob: Blob; filename: string }> {
    const query = new URLSearchParams()
    query.set("format", params.format)
    if (params?.status?.length) params.status.forEach((status) => query.append("status", status))
    if (params?.tags?.length) params.tags.forEach((tag) => query.append("tags", tag))
    if (params?.favorite !== undefined) query.set("favorite", String(params.favorite))
    if (params?.q) query.set("q", params.q)
    if (params?.domain) query.set("domain", params.domain)
    if (params?.page) query.set("page", String(params.page))
    if (params?.size) query.set("size", String(params.size))
    const qs = query.toString()
    const path = `/api/v1/reading/export${qs ? `?${qs}` : ""}` as const
    const response = await bgRequest<{
      ok: boolean
      status: number
      data?: ArrayBuffer
      error?: string
      headers?: Record<string, string>
    }>({
      path,
      method: "GET",
      responseType: "arrayBuffer",
      returnResponse: true
    })
    if (!response) {
      throw new Error("Export failed")
    }
    if (!response.ok) {
      const msg = response.error || `Export failed: ${response.status}`
      throw new Error(msg)
    }
    const headers = new Headers(response.headers || {})
    const contentDisposition = headers.get("content-disposition") || ""
    const filenameMatch = /filename="?([^"]+)"?/i.exec(contentDisposition)
    const filename = filenameMatch?.[1] || "reading_export.jsonl"
    const blob = new Blob([response.data], { type: headers.get("content-type") || "application/octet-stream" })
    return { blob, filename }
  }
}

// Singleton instance
export const tldwClient = new TldwApiClient()
