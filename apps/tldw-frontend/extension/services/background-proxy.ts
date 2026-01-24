import { browser } from "wxt/browser"
import { createSafeStorage } from "@/utils/safe-storage"
import { formatErrorMessage } from "@/utils/format-error-message"
import { isPlaceholderApiKey } from "@/utils/api-key"
import { tldwRequest } from "@/services/tldw/request-core"
import type {
  AllowedMethodFor,
  AllowedPath,
  ClientPathOrUrlWithQuery,
  ClientPathRuntimeWithQuery,
  PathOrUrl,
  UpperLower
} from "@/services/tldw/openapi-guard"

type UnknownRecord = Record<string, unknown>
type RequestErrorLogEntry = {
  method: string
  path: string
  status?: number
  error?: string
  source: "background" | "direct"
  at?: string
}

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null

const ERROR_LOG_THROTTLE_MS = 15_000
const RATE_LIMIT_LOG_THROTTLE_MS = 60_000
const ERROR_LOG_MAX_ENTRIES = 200
const errorLogHistory = new Map<string, number>()

const isRateLimitEntry = (entry: { status?: number; error?: string }): boolean => {
  if (entry.status === 429) return true
  const msg = String(entry.error || "").toLowerCase()
  return msg.includes("rate limit") || msg.includes("429")
}

const shouldRecordRequestError = (entry: {
  method: string
  path: string
  status?: number
  error?: string
  source: "background" | "direct"
}): boolean => {
  const now = Date.now()
  const key = `${entry.source}:${entry.method}:${entry.path}:${entry.status ?? "na"}:${entry.error ?? ""}`
  const lastAt = errorLogHistory.get(key)
  const throttleMs = isRateLimitEntry(entry)
    ? RATE_LIMIT_LOG_THROTTLE_MS
    : ERROR_LOG_THROTTLE_MS
  if (lastAt && now - lastAt < throttleMs) return false
  errorLogHistory.set(key, now)
  if (errorLogHistory.size > ERROR_LOG_MAX_ENTRIES) {
    const sorted = Array.from(errorLogHistory.entries()).sort((a, b) => a[1] - b[1])
    const overflow = sorted.length - ERROR_LOG_MAX_ENTRIES
    for (let i = 0; i < overflow; i++) {
      errorLogHistory.delete(sorted[i][0])
    }
  }
  return true
}

const REDACTED_VALUE = "[REDACTED]"
const SENSITIVE_KEY_FRAGMENTS = [
  "stack",
  "trace",
  "sql",
  "query",
  "password",
  "passwd",
  "token",
  "secret",
  "path",
  "headers",
  "internalid",
  "authorization",
  "cookie",
  "api_key",
  "apikey",
  "access_key",
  "accesskey",
  "private",
  "credential",
  "session",
  "bearer"
]

const hasExtensionRuntime = () => Boolean(browser?.runtime?.id)

const isSensitiveKey = (key: string): boolean => {
  const normalized = key.toLowerCase().replace(/[\s-]/g, "_")
  return SENSITIVE_KEY_FRAGMENTS.some((fragment) => normalized.includes(fragment))
}

// Redact known sensitive fields (stack/trace/sql/query/secret/headers/etc.) recursively.
const sanitizeResponseData = (
  value: unknown,
  seen: WeakSet<object> = new WeakSet()
): unknown => {
  if (value == null || typeof value !== "object") return value
  if (seen.has(value as object)) return REDACTED_VALUE
  seen.add(value as object)

  if (Array.isArray(value)) {
    return value.map((entry) => sanitizeResponseData(entry, seen))
  }

  const result: Record<string, unknown> = {}
  Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => {
    if (isSensitiveKey(key)) {
      result[key] = REDACTED_VALUE
      return
    }
    result[key] = sanitizeResponseData(entry, seen)
  })
  return result
}

const resolveWebRequestUrl = async (path: PathOrUrl): Promise<{
  url: string
  config: UnknownRecord | null
}> => {
  const storage = createSafeStorage()
  const config = await storage
    .get<UnknownRecord>("tldwConfig")
    .catch(() => null)
  const isAbsoluteUrl = typeof path === "string" && /^https?:/i.test(path)
  if (!config?.serverUrl && !isAbsoluteUrl) {
    throw new Error("tldw server not configured")
  }
  const baseUrl = config?.serverUrl ? String(config.serverUrl).replace(/\/$/, "") : ""
  const url = isAbsoluteUrl
    ? String(path)
    : `${baseUrl}${String(path).startsWith("/") ? "" : "/"}${String(path)}`
  return { url, config: config || null }
}

const applyAuthHeaders = (
  headers: Record<string, string>,
  config: UnknownRecord | null
): void => {
  if (!config) return
  for (const key of Object.keys(headers)) {
    const lower = key.toLowerCase()
    if (lower === "x-api-key" || lower === "authorization") {
      delete headers[key]
    }
  }
  if (config.authMode === "multi-user") {
    const token = String(config.accessToken || "").trim()
    if (!token) {
      throw new Error("Not authenticated. Please login under Settings > tldw.")
    }
    headers["Authorization"] = `Bearer ${token}`
    return
  }
  const key = String(config.apiKey || "").trim()
  if (!key) {
    throw new Error(
      "Add or update your API key in Settings -> tldw server, then try again."
    )
  }
  if (isPlaceholderApiKey(key)) {
    throw new Error(
      "tldw server API key is still set to the default demo value. Replace it with your real API key in Settings -> tldw server before continuing."
    )
  }
  headers["X-API-KEY"] = key
}

const isBinaryBody = (value: unknown): boolean => {
  if (!value || typeof value !== "object") return false
  if (typeof FormData !== "undefined" && value instanceof FormData) return true
  if (typeof Blob !== "undefined" && value instanceof Blob) return true
  if (typeof URLSearchParams !== "undefined" && value instanceof URLSearchParams)
    return true
  if (typeof ArrayBuffer !== "undefined") {
    if (value instanceof ArrayBuffer) return true
    if (ArrayBuffer.isView?.(value)) return true
  }
  return false
}

export interface BgRequestInit<
  P extends PathOrUrl = AllowedPath,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
> {
  path: P
  method?: UpperLower<M>
  headers?: Record<string, string>
  body?: unknown
  noAuth?: boolean
  timeoutMs?: number
  abortSignal?: AbortSignal
  responseType?: "json" | "text" | "arrayBuffer"
  returnResponse?: boolean
}

export async function bgRequest<
  T = unknown,
  P extends PathOrUrl = AllowedPath,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
>(init: BgRequestInit<P, M>): Promise<T> {
  const {
    path,
    method = 'GET' as UpperLower<M>,
    headers = {},
    body,
    noAuth = false,
    timeoutMs,
    abortSignal,
    responseType,
    returnResponse
  } = init
  const isAbsoluteUrl = typeof path === "string" && /^https?:/i.test(path)
  const noAuthExplicit = Object.prototype.hasOwnProperty.call(init, "noAuth")
  const resolvedNoAuth = noAuthExplicit ? noAuth : (noAuth || isAbsoluteUrl)
  const resolvedHeaders = headers
  const recordRequestError = async (entry: {
    method: string
    path: string
    status?: number
    error?: string
    source: "background" | "direct"
  }) => {
    try {
      if (!shouldRecordRequestError(entry)) return
      const storage = createSafeStorage({ area: "local" })
      const at = new Date().toISOString()
      const payload = { ...entry, at }
      const existing =
        (await storage.get<RequestErrorLogEntry[]>("__tldwRequestErrors").catch(() => [])) ||
        []
      const next = Array.isArray(existing) ? existing : []
      next.unshift(payload)
      if (next.length > 20) next.length = 20
      await storage.set("__tldwRequestErrors", next)
      await storage.set("__tldwLastRequestError", payload)
    } catch {
      // best-effort logging only
    }
  }
  const isAbortErrorMessage = (value?: string) =>
    typeof value === "string" && value.toLowerCase().includes("abort")

  // If extension messaging is available, use it (extension context)
  try {
    if (browser?.runtime?.sendMessage && hasExtensionRuntime()) {
      const payload = {
        type: 'tldw:request',
        payload: {
          path,
          method,
          headers: resolvedHeaders,
          body,
          noAuth: resolvedNoAuth,
          timeoutMs,
          responseType
        }
      }

      if (!abortSignal) {
        const resp = await browser.runtime.sendMessage(payload) as { ok: boolean; error?: string; status?: number; data: T } | undefined
        if (!resp) {
          throw new Error(`Request failed (${method} ${path})`)
        }
        if (!resp.ok) {
          const msg = formatErrorMessage(
            resp?.error,
            `Request failed: ${resp?.status}`
          )
          if (!isAbortErrorMessage(msg)) {
            console.warn("[tldw:request]", method, path, resp?.status, msg)
            await recordRequestError({
              method: String(method),
              path: String(path),
              status: resp?.status,
              error: msg,
              source: "background"
            })
          }
          const error = new Error(`${msg} (${method} ${path})`) as Error & {
            status?: number
          }
          error.status = resp?.status
          if (!returnResponse) {
            throw error
          }
        }
        return (returnResponse ? resp : resp.data) as T
      }

      if (abortSignal.aborted) {
        throw new Error('Aborted')
      }

      const messagePromise = browser.runtime.sendMessage(payload) as Promise<
        { ok: boolean; error?: string; status?: number; data: T } | undefined
      >

      const resp = await new Promise<
        { ok: boolean; error?: string; status?: number; data: T } | undefined
      >((resolve, reject) => {
        const onAbort = () => {
          reject(new Error('Aborted'))
        }
        abortSignal.addEventListener('abort', onAbort, { once: true })
        messagePromise
          .then((r) => {
            abortSignal.removeEventListener('abort', onAbort)
            resolve(r)
          })
          .catch((e) => {
            abortSignal.removeEventListener('abort', onAbort)
            reject(e)
          })
      })

      if (!resp) {
        throw new Error(`Request failed (${method} ${path})`)
      }
      if (!resp.ok) {
        const msg = formatErrorMessage(
          resp?.error,
          `Request failed: ${resp?.status}`
        )
        if (!isAbortErrorMessage(msg)) {
          console.warn("[tldw:request]", method, path, resp?.status, msg)
          await recordRequestError({
            method: String(method),
            path: String(path),
            status: resp?.status,
            error: msg,
            source: "background"
          })
        }
        const error = new Error(`${msg} (${method} ${path})`) as Error & {
          status?: number
        }
        error.status = resp?.status
        if (!returnResponse) {
          throw error
        }
      }
      return (returnResponse ? resp : resp.data) as T
    }
  } catch {
    // fallthrough to direct fetch
  }

  // Fallback: direct fetch (web/dev context)
  const storage = createSafeStorage()
  const resp = await tldwRequest(
    {
      path,
      method,
      headers: resolvedHeaders,
      body,
      noAuth: resolvedNoAuth,
      timeoutMs,
      abortSignal,
      responseType
    },
    {
      getConfig: () =>
        storage.get<UnknownRecord>("tldwConfig").catch(() => null)
    }
  )
  if (!resp?.ok) {
    const msg = formatErrorMessage(
      resp?.error,
      `Request failed: ${resp?.status}`
    )
    if (!isAbortErrorMessage(msg)) {
      console.warn("[tldw:request]", method, path, resp?.status, msg)
      await recordRequestError({
        method: String(method),
        path: String(path),
        status: resp?.status,
        error: msg,
        source: "direct"
      })
    }
    const error = new Error(`${msg} (${method} ${path})`) as Error & {
      status?: number
    }
    error.status = resp?.status
    if (!returnResponse) {
      throw error
    }
  }
  return (returnResponse ? resp : resp.data) as T
}

export interface BgStreamInit<
  P extends AllowedPath = AllowedPath,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
> {
  path: P
  method?: UpperLower<M>
  headers?: Record<string, string>
  body?: unknown
  streamIdleTimeoutMs?: number
  abortSignal?: AbortSignal
}

export async function* bgStream<
  P extends AllowedPath = AllowedPath,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
>(
  { path, method = 'POST' as UpperLower<M>, headers = {}, body, streamIdleTimeoutMs, abortSignal }: BgStreamInit<P, M>
): AsyncGenerator<string> {
  if (!hasExtensionRuntime()) {
    const { url, config } = await resolveWebRequestUrl(path)
    const resolvedHeaders: Record<string, string> = { ...(headers || {}) }
    applyAuthHeaders(resolvedHeaders, config)
    const hasContentType = Object.keys(resolvedHeaders).some(
      (key) => key.toLowerCase() === "content-type"
    )
    const resolvedBody: BodyInit | undefined =
      body == null
        ? undefined
        : typeof body === "string" || isBinaryBody(body)
          ? (body as BodyInit)
          : JSON.stringify(body)
    if (body != null && !hasContentType && !isBinaryBody(body)) {
      resolvedHeaders["Content-Type"] = "application/json"
    }

    const controller = new AbortController()
    const onAbort = () => {
      try {
        controller.abort()
      } catch {}
    }
    if (abortSignal) {
      if (abortSignal.aborted) onAbort()
      else abortSignal.addEventListener("abort", onAbort, { once: true })
    }

    let idleTimeoutId: ReturnType<typeof setTimeout> | null = null
    const resetIdleTimeout = () => {
      if (!streamIdleTimeoutMs || streamIdleTimeoutMs <= 0) return
      if (idleTimeoutId) clearTimeout(idleTimeoutId)
      idleTimeoutId = setTimeout(() => {
        try {
          controller.abort()
        } catch {}
      }, streamIdleTimeoutMs)
    }

    try {
      const resp = await fetch(url, {
        method,
        headers: resolvedHeaders,
        body: resolvedBody,
        signal: controller.signal
      })

      if (!resp.ok) {
        let errorBody: unknown = null
        try {
          const raw = await resp.text()
          try {
            errorBody = JSON.parse(raw)
          } catch {
            errorBody = raw
          }
        } catch {
          errorBody = null
        }
        const detail =
          typeof errorBody === "object" &&
          errorBody &&
          (errorBody.detail || errorBody.error || errorBody.message)
        const msg = formatErrorMessage(
          typeof detail !== "undefined" ? detail : errorBody,
          `Request failed: ${resp.status}`
        )
        const error = new Error(`${msg} (${method} ${path})`) as Error & {
          status?: number
        }
        error.status = resp.status
        throw error
      }

      const reader = resp.body?.getReader()
      if (!reader) {
        throw new Error("Stream response has no body.")
      }
      const decoder = new TextDecoder()
      let buffer = ""
      resetIdleTimeout()

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        if (value) {
          resetIdleTimeout()
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split(/\r?\n/)
          buffer = lines.pop() ?? ""
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue
            if (trimmed.startsWith("event:")) continue
            const normalized = trimmed.startsWith("data:")
              ? trimmed.slice(5).trim()
              : trimmed
            if (!normalized || normalized === "[DONE]") continue
            yield normalized
          }
        }
      }

      if (buffer.trim()) {
        const normalized = buffer.trim().startsWith("data:")
          ? buffer.trim().slice(5).trim()
          : buffer.trim()
        if (normalized && normalized !== "[DONE]") {
          yield normalized
        }
      }
    } finally {
      if (idleTimeoutId) clearTimeout(idleTimeoutId)
      if (abortSignal) {
        try {
          abortSignal.removeEventListener("abort", onAbort)
        } catch {}
      }
    }

    return
  }

  const port = browser.runtime.connect({ name: 'tldw:stream' })
  const queue: string[] = []
  let done = false
  let error: unknown = null

  const onMessage = (msg: unknown) => {
    if (!isRecord(msg)) return
    if (msg.event === 'data') {
      if (typeof msg.data === "string") {
        queue.push(msg.data)
      }
    } else if (msg.event === 'done') {
      done = true
    } else if (msg.event === 'error') {
      const message = typeof msg.message === "string" ? msg.message : 'Stream error'
      error = new Error(message)
      done = true
    }
  }
  port.onMessage.addListener(onMessage)
  const onDisconnect = () => {
    if (!done) {
      if (!error) error = new Error('Stream disconnected')
      done = true
    }
  }
  port.onDisconnect.addListener(onDisconnect)
  const onAbort = () => {
    if (!error) error = new Error('Aborted')
    done = true
    try { port.disconnect() } catch {}
  }
  if (abortSignal) {
    if (abortSignal.aborted) onAbort()
    else abortSignal.addEventListener('abort', onAbort, { once: true })
  }
  if (!done) {
    try {
      port.postMessage({ path, method, headers, body, streamIdleTimeoutMs })
    } catch (e) {
      if (!error) error = e
      done = true
    }
  }

  try {
    while (!done || queue.length > 0) {
      if (queue.length > 0) {
        yield queue.shift() as string
      } else {
        await new Promise((r) => setTimeout(r, 10))
      }
    }
    if (error) throw error
  } finally {
    try { port.onMessage.removeListener(onMessage); } catch {}
    try { port.onDisconnect.removeListener(onDisconnect); } catch {}
    try { port.disconnect(); } catch {}
    if (abortSignal) {
      try { abortSignal.removeEventListener('abort', onAbort) } catch {}
    }
  }
}

export interface BgUploadInit<P extends AllowedPath = AllowedPath, M extends AllowedMethodFor<P> = AllowedMethodFor<P>> {
  path: P
  method?: UpperLower<M>
  // key/value fields to include alongside file in FormData
  fields?: Record<string, unknown>
  // File payload as raw bytes with metadata (structured-cloneable)
  file?: { name?: string; type?: string; data: ArrayBuffer | Uint8Array | number[] }
  // Optional override for the multipart file field name
  fileFieldName?: string
}

export async function bgUpload<T = unknown, P extends AllowedPath = AllowedPath, M extends AllowedMethodFor<P> = AllowedMethodFor<P>>(
  { path, method = 'POST' as UpperLower<M>, fields = {}, file, fileFieldName }: BgUploadInit<P, M>
): Promise<T> {
  if (browser?.runtime?.sendMessage && hasExtensionRuntime()) {
    const resp = await browser.runtime.sendMessage({
      type: 'tldw:upload',
      payload: { path, method, fields, file, fileFieldName }
    }) as { ok: boolean; error?: string; status?: number; data: T } | undefined
    if (!resp?.ok) {
      const msg = formatErrorMessage(
        resp?.error,
        `Upload failed: ${resp?.status}`
      )
      const error = new Error(msg) as Error & { status?: number; details?: unknown }
      error.status = resp?.status
      if (typeof resp?.data !== "undefined") {
        error.details = sanitizeResponseData(resp.data)
      }
      throw error
    }
    return resp.data as T
  }

  const { url, config } = await resolveWebRequestUrl(path)
  const resolvedHeaders: Record<string, string> = {}
  applyAuthHeaders(resolvedHeaders, config)

  const form = new FormData()
  Object.entries(fields || {}).forEach(([key, value]) => {
    if (typeof value === "undefined" || value === null) return
    form.append(key, String(value))
  })
  if (file) {
    const buffer = file.data instanceof ArrayBuffer
      ? file.data
      : (new Uint8Array(file.data as ArrayBuffer | ArrayLike<number>).buffer as ArrayBuffer)
    const blob = new Blob([buffer], {
      type: file.type || "application/octet-stream"
    })
    form.append(fileFieldName || "file", blob, file.name || "upload")
  }

  const resp = await fetch(url, {
    method,
    headers: resolvedHeaders,
    body: form
  })

  const contentType = resp.headers.get("content-type") || ""
  const data = contentType.includes("application/json")
    ? await resp.json().catch(() => null)
    : await resp.text().catch(() => null)

  if (!resp.ok) {
    const msg = formatErrorMessage(
      data,
      `Upload failed: ${resp.status}`
    )
    const error = new Error(msg) as Error & { status?: number; details?: unknown }
    error.status = resp.status
    if (typeof data !== "undefined") {
      error.details = sanitizeResponseData(data)
    }
    throw error
  }

  return data as T
}

export async function bgRequestValidated<
  T = unknown,
  P extends PathOrUrl = AllowedPath,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
>(
  init: BgRequestInit<P, M>,
  validate?: (data: unknown) => T
): Promise<T> {
  const data = await bgRequest<unknown, P, M>(init)
  return validate ? validate(data) : (data as T)
}

// Strict variants: enforce that call sites use ClientPath-derived strings by default.
export async function bgRequestClient<
  T = unknown,
  P extends ClientPathOrUrlWithQuery = ClientPathOrUrlWithQuery,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
>(init: BgRequestInit<P, M>): Promise<T> {
  return bgRequest<T, P, M>(init)
}

export async function* bgStreamClient<
  P extends ClientPathRuntimeWithQuery = ClientPathRuntimeWithQuery,
  M extends AllowedMethodFor<P> = AllowedMethodFor<P>
>(init: BgStreamInit<P, M>): AsyncGenerator<string> {
  for await (const chunk of bgStream<P, M>(init)) {
    yield chunk
  }
}
