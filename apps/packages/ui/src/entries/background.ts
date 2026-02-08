import { browser } from "wxt/browser"
import { createSafeStorage } from "@/utils/safe-storage"
import { formatErrorMessage } from "@/utils/format-error-message"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { tldwAuth } from "@/services/tldw/TldwAuth"
import { tldwModels } from "@/services/tldw"
import { apiSend } from "@/services/api-send"
import { tldwRequest } from "@/services/tldw/request-core"
import {
  getProcessPathForType,
  getProcessPathForUrl,
  inferMediaTypeFromUrl,
  inferUploadMediaTypeFromFile,
  normalizeMediaType
} from "@/services/tldw/media-routing"
import {
  ensureSidepanelOpen,
  pickFirstString,
  extractTranscriptionPieces,
  clampText,
  notify
} from "@/services/background-helpers"
import { ModelDb } from "@/db/models"
import { generateID } from "@/db"
import {
  initBackground,
  MODEL_WARM_ALARM_NAME
} from "@/entries/shared/background-init"
import {
  buildContextMenuAddPayload,
  buildContextMenuProcessPayload,
  extractYouTubeTimestampSeconds,
  normalizeUrlForDedupe,
  resolveContextMenuTargetUrl
} from "@/entries/shared/ingest-payloads"

type BackgroundDiagnostics = {
  startedAt: number
  modelWarmCount: number
  lastModelWarmAt: number | null
  lastModelWarmError: string | null
  alarmFires: number
  lastAlarmAt: number | null
  ports: {
    stream: number
    stt: number
    copilot: number
  }
  lastStreamAt: number | null
  lastSttAt: number | null
  lastCopilotAt: number | null
}

const backgroundDiagnostics: BackgroundDiagnostics = {
  startedAt: Date.now(),
  modelWarmCount: 0,
  lastModelWarmAt: null,
  lastModelWarmError: null,
  alarmFires: 0,
  lastAlarmAt: null,
  ports: {
    stream: 0,
    stt: 0,
    copilot: 0
  },
  lastStreamAt: null,
  lastSttAt: null,
  lastCopilotAt: null
}

const logBackgroundError = (label: string, error: unknown) => {
  console.debug(`[tldw] background ${label} failed`, error)
}

type IngestLifecycleStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "auth_required"

type IngestFunnelEvent =
  | "context_click"
  | "job_queued"
  | "media_completed"
  | "first_chat_message"

type IngestSession = {
  funnelId: string
  url: string
  normalizedUrl: string
  tabId?: number
  status: IngestLifecycleStatus
  jobIds: number[]
  createdAt: number
  retryCount: number
  awaitingAuth: boolean
  mediaId?: number
  lastError?: string
  timestampSeconds?: number | null
}

const warmModels = async (
  force = false,
  throwOnError = false
): Promise<any[] | null> => {
  backgroundDiagnostics.modelWarmCount += 1
  backgroundDiagnostics.lastModelWarmAt = Date.now()
  backgroundDiagnostics.lastModelWarmError = null
  try {
    const models = await tldwModels.warmCache(Boolean(force))

    // Sync models to local database
    if (models && models.length > 0) {
      const db = new ModelDb()
      const existing = await db.getAll()
      const existingLookups = new Set(
        existing.map((m: any) => m?.lookup).filter(Boolean)
      )

      for (const model of models) {
        try {
          const lookup = `${model.id}_tldw_${model.provider}`
          if (existingLookups.has(lookup)) continue

          // Transform ModelInfo to Model format
          const dbModel = {
            id: `${model.id}_${generateID()}`,
            model_id: model.id,
            name: model.name,
            provider_id: `tldw_${model.provider}`,
            lookup,
            model_type: model.type || 'chat',
            db_type: 'openai_model'
          }

          await db.create(dbModel)
          existingLookups.add(lookup)
        } catch (err) {
          // Log but don't fail the entire sync if one model fails
          console.debug('[tldw] Failed to sync model to DB:', model.id, err)
        }
      }
    }

    return models
  } catch (e) {
    console.debug("[tldw] model warmup failed", e)
    backgroundDiagnostics.lastModelWarmError =
      (e as any)?.message || "model warmup failed"
    if (throwOnError) {
      throw e
    }
    return null
  }
}

export default defineBackground({
  main() {
    console.log('[BG_STARTUP] Background script main() starting', { timestamp: Date.now() })
    const storage = createSafeStorage()
    let isCopilotRunning: boolean = false
    let actionIconClick: string = "webui"
    let contextMenuClick: string = "sidePanel"
    const contextMenuId = {
      webui: "open-web-ui-pa",
      sidePanel: "open-side-panel-pa"
    }
    const transcribeMenuId = {
      transcribe: "transcribe-media-pa",
      transcribeAndSummarize: "transcribe-and-summarize-media-pa"
    }
    const saveToNotesMenuId = "save-to-notes-pa"
    const narrateSelectionMenuId = "narrate-selection-pa"
    const getActionApi = () => {
      const anyBrowser = browser as any
      const anyChrome = (globalThis as any).chrome
      return (
        anyBrowser?.action ||
        anyBrowser?.browserAction ||
        anyChrome?.action ||
        anyChrome?.browserAction
      )
    }

    const initialize = async () => {
      try {
        await initBackground({
          storage,
          contextMenuId,
          saveToNotesMenuId,
          narrateSelectionMenuId,
          transcribeMenuId,
          warmModels,
          capabilities: {
            sendToTldw: true,
            processLocal: true,
            transcribe: true,
            openApiCheck: true
          },
          onActionIconClickChange: (value) => {
            actionIconClick = value
          },
          onContextMenuClickChange: (value) => {
            contextMenuClick = value
          }
        })
      } catch (error) {
        console.error("Error in initLogic:", error)
      }
    }

    const buildBackgroundDiagnostics = () => {
      const memory = (globalThis as any)?.performance?.memory
      return {
        ...backgroundDiagnostics,
        chatQueueDepth: chatQueue.length,
        chatActiveCount,
        chatBackoffMs,
        chatBackoffUntil,
        memory:
          memory && typeof memory.usedJSHeapSize === "number"
            ? {
                usedJSHeapSize: memory.usedJSHeapSize,
                totalJSHeapSize: memory.totalJSHeapSize,
                jsHeapSizeLimit: memory.jsHeapSizeLimit
              }
            : null
      }
    }


    let refreshInFlight: Promise<any> | null = null
    let streamDebugEnabled = false
    const ingestSessions = new Map<string, IngestSession>()
    const pendingAuthReplay = new Set<string>()

    const INGEST_FUNNEL_METRICS_KEY = "tldw:ingestFunnelMetrics"
    const INGEST_FUNNEL_METRICS_LIMIT = 200
    const METADATA_DEDUPE_FIELDS = [
      "url",
      "source_url",
      "source",
      "input_ref",
      "canonical_url",
      "webpage_url"
    ]
    const TERMINAL_INGEST_JOB_STATUSES = new Set([
      "completed",
      "failed",
      "cancelled",
      "quarantined"
    ])

    const createFunnelId = (): string =>
      `ingest-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

    const isLikelyAuthError = (status: number, error?: string): boolean => {
      if (status === 401) return true
      const text = String(error || "").toLowerCase()
      if (!text) return false
      return (
        text.includes("not authenticated") ||
        text.includes("api key") ||
        text.includes("login") ||
        text.includes("unauthorized")
      )
    }

    const hasUsableAuthConfig = (cfg: any): boolean => {
      if (!cfg || typeof cfg !== "object") return false
      const authMode = String(cfg.authMode || "single-user")
      if (authMode === "multi-user") {
        return Boolean(String(cfg.accessToken || "").trim())
      }
      return Boolean(String(cfg.apiKey || "").trim())
    }

    const toPositiveInt = (value: unknown): number | null => {
      const parsed = Number(value)
      if (!Number.isFinite(parsed) || parsed <= 0) return null
      return Math.trunc(parsed)
    }

    const pickMediaIdFromAny = (value: unknown): number | null => {
      if (!value || typeof value !== "object") return null
      const row = value as Record<string, unknown>
      return (
        toPositiveInt(row.media_id) ||
        toPositiveInt(row.db_id) ||
        toPositiveInt(row.id)
      )
    }

    const pickMetadataSearchMediaId = (data: unknown): number | null => {
      if (!data || typeof data !== "object") return null
      const root = data as Record<string, unknown>
      const rows = Array.isArray(root.results) ? root.results : []
      for (const row of rows) {
        const mediaId = pickMediaIdFromAny(row)
        if (mediaId != null) return mediaId
      }
      return null
    }

    const buildMetadataSearchPath = (urlValue: string): string => {
      const filters = METADATA_DEDUPE_FIELDS.map((field) => ({
        field,
        op: "eq",
        value: urlValue
      }))
      const query = new URLSearchParams({
        filters: JSON.stringify(filters),
        match_mode: "any",
        group_by_media: "true",
        page: "1",
        per_page: "1"
      })
      return `/api/v1/media/metadata-search?${query.toString()}`
    }

    const appendIngestFunnelMetric = async (
      event: IngestFunnelEvent,
      funnelId: string,
      metadata?: Record<string, unknown>
    ) => {
      try {
        const current = await storage.get<any>(INGEST_FUNNEL_METRICS_KEY)
        const entries = Array.isArray(current) ? current : []
        entries.push({
          event,
          funnelId,
          timestamp: new Date().toISOString(),
          metadata: metadata || {}
        })
        if (entries.length > INGEST_FUNNEL_METRICS_LIMIT) {
          entries.splice(0, entries.length - INGEST_FUNNEL_METRICS_LIMIT)
        }
        await storage.set(INGEST_FUNNEL_METRICS_KEY, entries)
      } catch (error) {
        logBackgroundError("append ingest funnel metric", error)
      }
    }

    const emitBackgroundMessage = async (
      tabId: number | undefined,
      type: string,
      payload?: Record<string, unknown>
    ) => {
      ensureSidepanelOpen(tabId)
      try {
        await browser.runtime.sendMessage({
          from: "background",
          type,
          payload
        })
      } catch (error) {
        logBackgroundError(`send ${type}`, error)
        setTimeout(() => {
          try {
            browser.runtime.sendMessage({
              from: "background",
              type,
              payload
            })
          } catch (retryError) {
            logBackgroundError(`send ${type} (retry)`, retryError)
          }
        }, 500)
      }
    }

    const emitIngestStatus = async (
      session: IngestSession,
      update: Partial<{
        status: IngestLifecycleStatus
        progressPercent: number
        progressMessage: string
        error: string
        mediaId: number
        canCancel: boolean
        canRetry: boolean
      }>
    ) => {
      if (update.status) {
        session.status = update.status
      }
      if (typeof update.mediaId === "number" && update.mediaId > 0) {
        session.mediaId = Math.trunc(update.mediaId)
      }
      if (update.error) {
        session.lastError = update.error
      }
      const canCancel =
        typeof update.canCancel === "boolean"
          ? update.canCancel
          : session.status === "queued" || session.status === "running"
      const canRetry =
        typeof update.canRetry === "boolean"
          ? update.canRetry
          : session.status === "failed" ||
            session.status === "cancelled" ||
            session.status === "auth_required"
      await emitBackgroundMessage(session.tabId, "media-ingest-status", {
        funnelId: session.funnelId,
        url: session.url,
        status: session.status,
        progressPercent: update.progressPercent,
        progressMessage: update.progressMessage,
        error: update.error,
        mediaId: session.mediaId,
        jobIds: session.jobIds,
        canCancel,
        canRetry,
        timestampSeconds: session.timestampSeconds ?? undefined
      })
    }

    const sendIngestReadyMessage = async (
      tabId: number | undefined,
      payload: {
        funnelId: string
        mediaId: string
        url?: string
        mode: "rag_media"
        timestampSeconds?: number
      }
    ) => {
      await emitBackgroundMessage(tabId, "media-ingest-ready", payload)
    }

    const openAuthSettings = async () => {
      try {
        const settingsUrl = browser.runtime.getURL("options.html#/settings/tldw")
        await browser.tabs.create({ url: settingsUrl })
      } catch (error) {
        logBackgroundError("open auth settings", error)
      }
    }

    const queueAuthRecovery = async (session: IngestSession, errorText: string) => {
      session.awaitingAuth = true
      session.lastError = errorText
      pendingAuthReplay.add(session.funnelId)
      await emitIngestStatus(session, {
        status: "auth_required",
        error: errorText,
        canCancel: false,
        canRetry: true
      })
      notify(
        "tldw_server",
        "Authentication required. Opened settings to update credentials; ingest will retry automatically."
      )
      await openAuthSettings()
    }

    const findExistingMediaForUrl = async (
      rawUrl: string,
      normalizedUrl: string
    ): Promise<number | null> => {
      const candidates = Array.from(
        new Set(
          [String(rawUrl || "").trim(), String(normalizedUrl || "").trim()].filter(
            (value) => value.length > 0
          )
        )
      )
      for (const candidate of candidates) {
        const path = buildMetadataSearchPath(candidate)
        const resp = (await handleTldwRequest({
          path,
          method: "GET",
          timeoutMs: 15000
        })) as { ok: boolean; status?: number; data?: any; error?: string } | undefined
        if (!resp?.ok) {
          if (isLikelyAuthError(Number(resp?.status || 0), resp?.error)) {
            throw new Error(resp?.error || "Authentication required.")
          }
          continue
        }
        const mediaId = pickMetadataSearchMediaId(resp.data)
        if (mediaId != null) return mediaId
      }
      return null
    }

    const handleTranscribeClick = async (
      info: any,
      tab: any,
      mode: 'transcribe' | 'transcribe+summary'
    ) => {
      const pageUrl = info.pageUrl || (tab && tab.url) || ''
      const targetUrl = (info.linkUrl && /^https?:/i.test(info.linkUrl)) ? info.linkUrl : pageUrl
      if (!targetUrl) {
        notify('tldw_server', 'No URL found to transcribe.')
        return
      }
      const path = getProcessPathForUrl(targetUrl)
      if (path !== '/api/v1/media/process-audios' && path !== '/api/v1/media/process-videos') {
        notify('tldw_server', 'Transcription is available for audio or video URLs only.')
        return
      }

      try {
        const resp = await apiSend({
          path,
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: {
            urls: [targetUrl],
            perform_analysis: mode === 'transcribe+summary',
            perform_chunking: false,
            summarize_recursively: mode === 'transcribe+summary',
            timestamp_option: true
          },
          timeoutMs: 180000
        })
        if (!resp?.ok) {
          notify('tldw_server', resp?.error || 'Transcription failed. Check your connection and server config.')
          return
        }
        const { transcript, summary } = extractTranscriptionPieces(resp.data)
        const safeTranscript = clampText(transcript)
        const safeSummary = clampText(summary)
        const label = mode === 'transcribe+summary' ? 'Transcription + summary' : 'Transcription'
        const bodyParts = []
        if (safeTranscript) bodyParts.push(`Transcript:\n${safeTranscript}`)
        if (safeSummary) bodyParts.push(`Summary:\n${safeSummary}`)
        const combinedText = bodyParts.join('\n\n') || 'Request completed. Open Media or the sidebar to view results.'

        ensureSidepanelOpen(tab?.id)
        try {
          await browser.runtime.sendMessage({
            from: 'background',
            type: mode === 'transcribe+summary' ? 'transcription+summary' : 'transcription',
            text: combinedText,
            payload: {
              url: targetUrl,
              transcript: safeTranscript,
              summary: safeSummary,
              mode
            }
          })
        } catch (error) {
          logBackgroundError("send transcription result", error)
          setTimeout(() => {
            try {
              browser.runtime.sendMessage({
                from: 'background',
                type: mode === 'transcribe+summary' ? 'transcription+summary' : 'transcription',
                text: combinedText,
                payload: {
                  url: targetUrl,
                  transcript: safeTranscript,
                  summary: safeSummary,
                  mode
                }
              })
            } catch (fallbackError) {
              logBackgroundError("send transcription result (retry)", fallbackError)
            }
          }, 500)
        }
        notify('tldw_server', `${label} sent to sidebar. You can also review it under Media in the Web UI.`)
      } catch (e: any) {
        notify('tldw_server', e?.message || 'Transcription request failed.')
      }
    }

    const deriveStreamIdleTimeout = (cfg: any, path: string, override?: number) => {
      if (override && override > 0) return override
      const p = String(path || '')
      const defaultIdle = 45000 // bump default idle timeout to 45s to tolerate slow providers
      if (p.includes('/api/v1/chat/completions')) {
        return Number(cfg?.chatStreamIdleTimeoutMs) > 0
          ? Number(cfg.chatStreamIdleTimeoutMs)
          : (Number(cfg?.streamIdleTimeoutMs) > 0 ? Number(cfg.streamIdleTimeoutMs) : defaultIdle)
      }
      return Number(cfg?.streamIdleTimeoutMs) > 0 ? Number(cfg.streamIdleTimeoutMs) : defaultIdle
    }

    const CHAT_QUEUE_CONCURRENCY = 2
    const CHAT_BACKOFF_BASE_MS = 1000
    const CHAT_BACKOFF_MAX_MS = 30_000
    let chatBackoffUntil = 0
    let chatBackoffMs = CHAT_BACKOFF_BASE_MS
    let chatQueueTimer: ReturnType<typeof setTimeout> | null = null
    let chatActiveCount = 0
    const chatQueue: Array<{
      run: () => Promise<any>
      resolve: (value: any) => void
      reject: (reason?: any) => void
    }> = []

    const isChatEndpoint = (path: string): boolean => {
      const raw = String(path || "")
      let pathname = raw
      if (/^https?:/i.test(raw)) {
        try {
          pathname = new URL(raw).pathname
        } catch (error) {
          logBackgroundError("parse chat endpoint url", error)
          pathname = raw
        }
      }
      const normalized = pathname.toLowerCase()
      return (
        normalized.startsWith("/api/v1/chat/") ||
        normalized.startsWith("/api/v1/chats/")
      )
    }

    const updateChatBackoff = (resp: any) => {
      if (!resp || typeof resp.status !== "number") return
      if (resp.status === 429) {
        const retryDelay =
          typeof resp.retryAfterMs === "number" && resp.retryAfterMs > 0
            ? resp.retryAfterMs
            : chatBackoffMs
        chatBackoffUntil = Math.max(chatBackoffUntil, Date.now() + retryDelay)
        chatBackoffMs = Math.min(chatBackoffMs * 2, CHAT_BACKOFF_MAX_MS)
        return
      }
      if (resp.ok) {
        chatBackoffUntil = 0
        chatBackoffMs = CHAT_BACKOFF_BASE_MS
      }
    }

    const scheduleChatDrain = () => {
      if (chatQueueTimer) return
      const delay = Math.max(0, chatBackoffUntil - Date.now())
      chatQueueTimer = setTimeout(() => {
        chatQueueTimer = null
        drainChatQueue()
      }, delay)
    }

    const drainChatQueue = () => {
      if (chatActiveCount >= CHAT_QUEUE_CONCURRENCY) return
      if (chatQueue.length === 0) return
      const now = Date.now()
      if (chatBackoffUntil > now) {
        scheduleChatDrain()
        return
      }
      const task = chatQueue.shift()
      if (!task) return
      chatActiveCount += 1
      task
        .run()
        .then((resp) => {
          chatActiveCount -= 1
          updateChatBackoff(resp)
          task.resolve(resp)
          drainChatQueue()
        })
        .catch((err) => {
          chatActiveCount -= 1
          task.reject(err)
          drainChatQueue()
        })
    }

    const enqueueChatRequest = <T,>(run: () => Promise<T>): Promise<T> =>
      new Promise((resolve, reject) => {
        chatQueue.push({ run, resolve, reject })
        drainChatQueue()
      })

    const normalizeFileData = (input: any): Uint8Array | null => {
      if (!input) return null
      if (input instanceof ArrayBuffer) return new Uint8Array(input)
      if (typeof SharedArrayBuffer !== "undefined" && input instanceof SharedArrayBuffer) {
        return new Uint8Array(input)
      }
      if (ArrayBuffer.isView(input)) {
        return new Uint8Array(input.buffer, input.byteOffset, input.byteLength)
      }
      if (
        typeof input === "object" &&
        input !== null &&
        typeof (input as { byteLength?: number }).byteLength === "number" &&
        typeof (input as { slice?: unknown }).slice === "function" &&
        Object.prototype.toString.call(input) === "[object ArrayBuffer]"
      ) {
        try {
          return new Uint8Array(input as ArrayBuffer)
        } catch (error) {
          logBackgroundError("normalize arraybuffer-like input", error)
          return null
        }
      }
      // Accept common structured-clone shapes (e.g., { data: [...] })
      if (Array.isArray((input as any)?.data)) return new Uint8Array((input as any).data)
      if (Array.isArray(input)) return new Uint8Array(input)
      if (typeof input === 'string' && input.startsWith('data:')) {
        try {
          const [meta, payload = ''] = input.split(',', 2)
          const isBase64 = /;base64/i.test(meta)
          if (isBase64) {
            const binary = atob(payload)
            const out = new Uint8Array(binary.length)
            for (let i = 0; i < binary.length; i += 1) {
              out[i] = binary.charCodeAt(i)
            }
            return out
          }
          const text = decodeURIComponent(payload)
          return new TextEncoder().encode(text)
        } catch (error) {
          logBackgroundError('decode file data url', error)
          return null
        }
      }
      return null
    }

    const handleUpload = async (payload: {
      path?: string
      method?: string
      fields?: Record<string, any>
      file?: { name?: string; type?: string; data?: ArrayBuffer | Uint8Array | { data?: number[] } | number[] | string }
      fileFieldName?: string
      timeoutMs?: number
    }) => {
      console.log('[HANDLE_UPLOAD] Called', { path: payload?.path, hasFile: !!payload?.file })
      const { path, method = 'POST', fields = {}, file, fileFieldName } = payload || {}
      const cfg = await storage.get<any>('tldwConfig')
      const isAbsolute = typeof path === 'string' && /^https?:/i.test(path)
      const toArrayBuffer = (bytes: Uint8Array): ArrayBuffer => {
        if (bytes.buffer instanceof ArrayBuffer) {
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
        }
        return new Uint8Array(bytes).buffer as ArrayBuffer
      }
      if (!cfg?.serverUrl && !isAbsolute) {
        return { ok: false, status: 400, error: 'tldw server not configured' }
      }
      const baseUrl = cfg?.serverUrl ? String(cfg.serverUrl).replace(/\/$/, '') : ''
      const url = isAbsolute ? path : `${baseUrl}${path?.startsWith('/') ? '' : '/'}${path}`
      try {
        const form = new FormData()
        for (const [k, v] of Object.entries(fields || {})) {
          // Preserve arrays (e.g., urls) instead of stringifying them into JSON blobs
          if (Array.isArray(v)) {
            v.forEach((item) => form.append(k, typeof item === 'string' ? item : JSON.stringify(item)))
          } else {
            form.append(k, typeof v === 'string' ? v : JSON.stringify(v))
          }
        }
        if (file?.data !== undefined && file?.data !== null) {
          const bytes = normalizeFileData(file.data)
          if (!bytes || bytes.byteLength === 0) {
            return { ok: false, status: 400, error: 'File data missing or unreadable. Please re-select the file and try again.' }
          }
          const blob = new Blob([toArrayBuffer(bytes)], {
            type: file.type || 'application/octet-stream'
          })
          const filename = file.name || 'file'
          const trimmedFieldName =
            typeof fileFieldName === 'string' ? fileFieldName.trim() : ''
          if (trimmedFieldName) {
            form.append(trimmedFieldName, blob, filename)
          } else {
            try {
              const fileCtor =
                typeof File === "function" ? File : null
              if (fileCtor) {
                form.append('files', new fileCtor([blob], filename, { type: blob.type }))
              } else {
                form.append('files', blob, filename)
              }
            } catch (error) {
              logBackgroundError("append upload file", error)
              form.append('files', blob, filename)
            }
            // Backward-compat: also include singular key some servers accept
            form.append('file', blob, filename)
          }
        }
        const headers: Record<string, string> = {}
        if (cfg?.authMode === 'single-user') {
          const key = (cfg?.apiKey || '').trim()
          if (!key) {
            return {
              ok: false,
              status: 401,
              error: 'Add or update your API key in Settings → tldw server, then try again.'
            }
          }
          headers['X-API-KEY'] = key
        }
        if (cfg?.authMode === 'multi-user') {
          const token = (cfg?.accessToken || '').trim()
          if (!token) return { ok: false, status: 401, error: 'Not authenticated. Please login under Settings > tldw.' }
          headers['Authorization'] = `Bearer ${token}`
        }
        if (cfg?.orgId) {
          headers['X-TLDW-Org-Id'] = String(cfg.orgId)
        }
        const controller = new AbortController()
        const timeoutMs =
          Number(payload?.timeoutMs) > 0
            ? Number(payload?.timeoutMs)
            : Number(cfg?.uploadRequestTimeoutMs) > 0
              ? Number(cfg.uploadRequestTimeoutMs)
              : Number(cfg?.mediaRequestTimeoutMs) > 0
                ? Number(cfg.mediaRequestTimeoutMs)
                : Number(cfg?.requestTimeoutMs) > 0
                  ? Number(cfg.requestTimeoutMs)
                  : 60000
        const timeout = setTimeout(() => controller.abort(), timeoutMs)
        let resp: Response
        console.log('[HANDLE_UPLOAD] About to fetch', { url, method, timeoutMs })
        try {
          resp = await fetch(url, { method, headers, body: form, signal: controller.signal })
        } finally {
          clearTimeout(timeout)
        }
        console.log('[HANDLE_UPLOAD] Fetch completed', { status: resp.status, ok: resp.ok })
        const contentType = resp.headers.get('content-type') || ''
        let data: any = null
        if (contentType.includes('application/json')) data = await resp.json().catch(() => null)
        else data = await resp.text().catch(() => null)
        const error = resp.ok
          ? undefined
          : formatErrorMessage(data, `Upload failed: ${resp.status}`)
        return { ok: resp.ok, status: resp.status, data, error }
      } catch (e: any) {
        console.log('[HANDLE_UPLOAD] Fetch error', { message: e?.message, name: e?.name })
        const raw = String(e?.message || "")
        const isAbort = raw.toLowerCase().includes("abort")
        return {
          ok: false,
          status: 0,
          error: isAbort
            ? "Upload timed out waiting for the server response. The ingest may still complete."
            : raw || "Upload failed"
        }
      }
    }

    const runTldwRequest = async (payload: any) => {
      // DEBUG: Log incoming request
      console.log('[BG_DEBUG] runTldwRequest called', {
        path: payload?.path,
        method: payload?.method,
        noAuth: payload?.noAuth
      })

      return tldwRequest(payload, {
        // IMPORTANT: getConfig must fetch fresh config each time it's called
        // (not pre-fetch once), because the config may not be seeded yet when
        // runTldwRequest is first invoked, but may be available on retry.
        getConfig: async () => {
          const config = await storage.get<any>('tldwConfig')
          console.log('[BG_DEBUG] tldwConfig from storage', {
            hasConfig: !!config,
            serverUrl: config?.serverUrl,
            authMode: config?.authMode,
            hasApiKey: !!config?.apiKey,
            apiKeyPrefix: config?.apiKey?.substring?.(0, 10)
          })
          return config
        },
        refreshAuth: async () => {
          if (!refreshInFlight) {
            refreshInFlight = (async () => {
              try {
                await tldwAuth.refreshToken()
              } finally {
                refreshInFlight = null
              }
            })()
          }
          try {
            await refreshInFlight
          } catch (error) {
            logBackgroundError("refresh auth", error)
          }
        }
      })
    }

    const handleTldwRequest = async (payload: any) => {
      console.log('[BG_DEBUG] handleTldwRequest received', { path: payload?.path, method: payload?.method })
      const path = payload?.path
      if (isChatEndpoint(String(path || ""))) {
        return enqueueChatRequest(() => runTldwRequest(payload))
      }
      try {
        const result = await runTldwRequest(payload)
        console.log('[BG_DEBUG] handleTldwRequest result', { path: payload?.path, ok: result?.ok, status: result?.status })
        return result
      } catch (error) {
        console.log('[BG_DEBUG] handleTldwRequest error', { path: payload?.path, error: String(error) })
        throw error
      }
    }

    const extractIngestJobIds = (data: any): number[] => {
      const jobs = Array.isArray(data?.jobs) ? data.jobs : []
      const ids: number[] = []
      for (const item of jobs) {
        const id = Number(item?.id)
        if (Number.isFinite(id) && id > 0) {
          ids.push(Math.trunc(id))
        }
      }
      return ids
    }

    const extractMediaIdFromJobStatus = (data: any): number | null => {
      const direct = Number(data?.media_id)
      if (Number.isFinite(direct) && direct > 0) {
        return Math.trunc(direct)
      }
      const nested = Number(data?.result?.media_id)
      if (Number.isFinite(nested) && nested > 0) {
        return Math.trunc(nested)
      }
      return null
    }

    const extractMediaIdFromAddResponse = (data: any): number | null => {
      if (!data || typeof data !== "object") return null
      const root = data as Record<string, unknown>
      const fromRoot = pickMediaIdFromAny(root)
      if (fromRoot != null) return fromRoot
      const rows = Array.isArray(root.results) ? root.results : []
      for (const row of rows) {
        const mediaId = pickMediaIdFromAny(row)
        if (mediaId != null) return mediaId
      }
      return pickMediaIdFromAny(root.result)
    }

    const isQueuedStatus = (value: string): boolean =>
      value === "queued" || value === "pending"

    const isRunningStatus = (value: string): boolean =>
      value === "running" || value === "in_progress" || value === "processing"

    const pollIngestJobsForSession = async (
      session: IngestSession,
      opts?: { timeoutMs?: number; intervalMs?: number }
    ): Promise<{
      mediaId: number | null
      finalStatus:
        | "completed"
        | "failed"
        | "cancelled"
        | "auth_required"
        | "timeout"
      error?: string
    }> => {
      const timeoutMs = Math.max(10_000, Number(opts?.timeoutMs) || 5 * 60 * 1000)
      const intervalMs = Math.max(500, Number(opts?.intervalMs) || 1200)
      const deadline = Date.now() + timeoutMs
      const unresolved = new Set(session.jobIds.map((id) => Math.trunc(id)))
      let lastStatus: IngestLifecycleStatus | null = null
      let lastProgressPercent: number | null = null
      let lastProgressMessage = ""
      let finalStatus: "failed" | "cancelled" = "failed"
      let finalError = ""

      while (unresolved.size > 0 && Date.now() < deadline) {
        const activeSession = ingestSessions.get(session.funnelId)
        if (!activeSession || activeSession.status === "cancelled") {
          return { mediaId: null, finalStatus: "cancelled" }
        }

        let sawPending = false
        let anyQueued = false
        let anyRunning = false
        let anyFailed = false
        let anyCancelled = false
        let maxProgressPercent = 0
        let progressMessage = ""
        for (const jobId of Array.from(unresolved)) {
          const resp = (await handleTldwRequest({
            path: `/api/v1/media/ingest/jobs/${jobId}`,
            method: "GET",
            timeoutMs: intervalMs + 3000
          })) as { ok: boolean; status?: number; data?: any; error?: string } | undefined
          if (!resp?.ok) {
            if (isLikelyAuthError(Number(resp?.status || 0), resp?.error)) {
              return {
                mediaId: null,
                finalStatus: "auth_required",
                error: resp?.error || "Authentication required."
              }
            }
            finalError = resp?.error || finalError
            sawPending = true
            continue
          }
          const mediaId = extractMediaIdFromJobStatus(resp.data)
          if (mediaId != null) {
            return { mediaId, finalStatus: "completed" }
          }
          const status = String(resp.data?.status || "").toLowerCase()
          if (isQueuedStatus(status)) anyQueued = true
          else if (isRunningStatus(status)) anyRunning = true
          else if (status === "failed" || status === "quarantined") anyFailed = true
          else if (status === "cancelled") anyCancelled = true
          const progressPercent = Number(resp.data?.progress_percent)
          if (Number.isFinite(progressPercent) && progressPercent > maxProgressPercent) {
            maxProgressPercent = Math.min(100, Math.max(0, progressPercent))
          }
          if (!progressMessage) {
            const candidateMessage = String(resp.data?.progress_message || "").trim()
            if (candidateMessage) progressMessage = candidateMessage
          }

          if (TERMINAL_INGEST_JOB_STATUSES.has(status)) {
            unresolved.delete(jobId)
          } else {
            sawPending = true
          }
        }

        let statusUpdate: IngestLifecycleStatus = "queued"
        if (anyRunning) {
          statusUpdate = "running"
        } else if (!anyRunning && !anyQueued && anyFailed) {
          statusUpdate = "failed"
        } else if (!anyRunning && !anyQueued && anyCancelled && !anyFailed) {
          statusUpdate = "cancelled"
        } else if (anyQueued || sawPending) {
          statusUpdate = "queued"
        }

        if (
          statusUpdate !== lastStatus ||
          maxProgressPercent !== lastProgressPercent ||
          progressMessage !== lastProgressMessage
        ) {
          await emitIngestStatus(session, {
            status: statusUpdate,
            progressPercent: Number.isFinite(maxProgressPercent)
              ? maxProgressPercent
              : undefined,
            progressMessage: progressMessage || undefined
          })
          lastStatus = statusUpdate
          lastProgressPercent = Number.isFinite(maxProgressPercent)
            ? maxProgressPercent
            : null
          lastProgressMessage = progressMessage
        }

        if (!sawPending && unresolved.size === 0) {
          if (anyFailed) {
            finalStatus = "failed"
          } else if (anyCancelled && !anyFailed) {
            finalStatus = "cancelled"
          }
          break
        }
        if (!sawPending) break
        await new Promise((resolve) => setTimeout(resolve, intervalMs))
      }

      if (Date.now() >= deadline && unresolved.size > 0) {
        return {
          mediaId: null,
          finalStatus: "timeout",
          error: "Timed out while waiting for media ingest jobs."
        }
      }

      return {
        mediaId: null,
        finalStatus,
        error: finalError || undefined
      }
    }

    const cancelIngestSessionById = async (
      funnelId: string,
      reason?: string
    ): Promise<{ ok: boolean; error?: string }> => {
      const session = ingestSessions.get(funnelId)
      if (!session) return { ok: false, error: "Ingest session not found." }
      pendingAuthReplay.delete(funnelId)
      session.awaitingAuth = false
      session.status = "cancelled"
      await emitIngestStatus(session, {
        status: "cancelled",
        progressMessage: "Cancelling ingest...",
        canCancel: false,
        canRetry: true
      })
      for (const jobId of session.jobIds) {
        await handleTldwRequest({
          path: `/api/v1/media/ingest/jobs/${jobId}?reason=${encodeURIComponent(
            reason || "user_cancelled"
          )}`,
          method: "DELETE",
          timeoutMs: 8000
        }).catch((error) => {
          logBackgroundError(`cancel ingest job ${jobId}`, error)
        })
      }
      await emitIngestStatus(session, {
        status: "cancelled",
        progressMessage: "Ingest cancelled.",
        canCancel: false,
        canRetry: true
      })
      return { ok: true }
    }

    const startContextMenuIngest = async (
      session: IngestSession,
      options?: {
        trackContextClick?: boolean
        reason?: "initial" | "manual_retry" | "auth_replay"
      }
    ) => {
      ingestSessions.set(session.funnelId, session)
      session.awaitingAuth = false
      session.lastError = undefined
      session.mediaId = undefined
      session.jobIds = []

      if (options?.trackContextClick) {
        await appendIngestFunnelMetric("context_click", session.funnelId, {
          url: session.url
        })
      }

      await emitIngestStatus(session, {
        status: "queued",
        progressMessage: "Checking for existing media...",
        canCancel: false,
        canRetry: false
      })

      let existingMediaId: number | null = null
      try {
        existingMediaId = await findExistingMediaForUrl(
          session.url,
          session.normalizedUrl
        )
      } catch (error) {
        const msg = formatErrorMessage(error, "Authentication required.")
        await queueAuthRecovery(session, msg)
        return
      }

      if (existingMediaId != null) {
        session.mediaId = existingMediaId
        await appendIngestFunnelMetric("media_completed", session.funnelId, {
          mediaId: existingMediaId,
          deduped: true
        })
        await emitIngestStatus(session, {
          status: "completed",
          mediaId: existingMediaId,
          progressPercent: 100,
          progressMessage: "Already in your library. Opening media-scoped chat.",
          canCancel: false,
          canRetry: false
        })
        await sendIngestReadyMessage(session.tabId, {
          funnelId: session.funnelId,
          mediaId: String(existingMediaId),
          url: session.url,
          mode: "rag_media",
          timestampSeconds:
            typeof session.timestampSeconds === "number" &&
            session.timestampSeconds >= 0
              ? session.timestampSeconds
              : undefined
        })
        notify(
          "tldw_server",
          "Already ingested. Opened media-scoped chat in sidebar."
        )
        return
      }

      const addPayload = buildContextMenuAddPayload(session.url)
      const jobsResp = await handleUpload({
        path: "/api/v1/media/ingest/jobs",
        method: "POST",
        fields: addPayload.fields,
        timeoutMs: 180000
      })
      if (!jobsResp?.ok) {
        if (isLikelyAuthError(Number(jobsResp?.status || 0), jobsResp?.error)) {
          await queueAuthRecovery(
            session,
            jobsResp?.error || "Authentication required."
          )
          return
        }
        const addResp = await handleUpload(addPayload)
        if (!addResp?.ok) {
          if (isLikelyAuthError(Number(addResp?.status || 0), addResp?.error)) {
            await queueAuthRecovery(
              session,
              addResp?.error || "Authentication required."
            )
            return
          }
          const msg = addResp?.error || jobsResp?.error || "Ingest failed"
          session.lastError = msg
          await emitIngestStatus(session, {
            status: "failed",
            error: msg,
            progressMessage: msg,
            canCancel: false,
            canRetry: true
          })
          notify("tldw_server", msg)
          return
        }
        const mediaId = extractMediaIdFromAddResponse(addResp.data)
        if (mediaId == null) {
          const msg = "Ingest completed but media id was not returned."
          session.lastError = msg
          await emitIngestStatus(session, {
            status: "failed",
            error: msg,
            canCancel: false,
            canRetry: true
          })
          notify("tldw_server", msg)
          return
        }
        session.mediaId = mediaId
        await appendIngestFunnelMetric("media_completed", session.funnelId, {
          mediaId,
          fallback: true
        })
        await emitIngestStatus(session, {
          status: "completed",
          mediaId,
          progressPercent: 100,
          progressMessage: "Ingest complete. Opening media-scoped chat.",
          canCancel: false,
          canRetry: false
        })
        await sendIngestReadyMessage(session.tabId, {
          funnelId: session.funnelId,
          mediaId: String(mediaId),
          url: session.url,
          mode: "rag_media",
          timestampSeconds:
            typeof session.timestampSeconds === "number" &&
            session.timestampSeconds >= 0
              ? session.timestampSeconds
              : undefined
        })
        notify("tldw_server", "Ready. Opened media-scoped chat in sidebar.")
        return
      }

      session.jobIds = extractIngestJobIds(jobsResp.data)
      if (session.jobIds.length === 0) {
        const msg = "Ingest job submission returned no job IDs."
        session.lastError = msg
        await emitIngestStatus(session, {
          status: "failed",
          error: msg,
          canCancel: false,
          canRetry: true
        })
        notify("tldw_server", msg)
        return
      }

      await appendIngestFunnelMetric("job_queued", session.funnelId, {
        jobIds: session.jobIds,
        url: session.url
      })

      await emitIngestStatus(session, {
        status: "queued",
        progressPercent: 0,
        progressMessage: "Queued for processing.",
        canCancel: true,
        canRetry: false
      })
      notify("tldw_server", "Queued for processing. Preparing chat when ready…")

      const pollResult = await pollIngestJobsForSession(session, {
        timeoutMs: 10 * 60 * 1000,
        intervalMs: 1500
      })
      if (pollResult.finalStatus === "completed" && pollResult.mediaId != null) {
        session.mediaId = pollResult.mediaId
        await appendIngestFunnelMetric("media_completed", session.funnelId, {
          mediaId: pollResult.mediaId,
          deduped: false
        })
        await emitIngestStatus(session, {
          status: "completed",
          mediaId: pollResult.mediaId,
          progressPercent: 100,
          progressMessage: "Ingest complete. Opening media-scoped chat.",
          canCancel: false,
          canRetry: false
        })
        await sendIngestReadyMessage(session.tabId, {
          funnelId: session.funnelId,
          mediaId: String(pollResult.mediaId),
          url: session.url,
          mode: "rag_media",
          timestampSeconds:
            typeof session.timestampSeconds === "number" &&
            session.timestampSeconds >= 0
              ? session.timestampSeconds
              : undefined
        })
        notify("tldw_server", "Ready. Opened media-scoped chat in sidebar.")
        return
      }

      if (pollResult.finalStatus === "auth_required") {
        await queueAuthRecovery(
          session,
          pollResult.error || "Authentication required."
        )
        return
      }

      if (pollResult.finalStatus === "cancelled") {
        await emitIngestStatus(session, {
          status: "cancelled",
          progressMessage: "Ingest cancelled.",
          canCancel: false,
          canRetry: true
        })
        notify("tldw_server", "Ingest was cancelled.")
        return
      }

      const failureMessage =
        pollResult.error ||
        (pollResult.finalStatus === "timeout"
          ? "Ingest timed out. Retry or open Media to inspect job status."
          : "No completed media yet. Open Media to check job status.")
      session.lastError = failureMessage
      await emitIngestStatus(session, {
        status: "failed",
        error: failureMessage,
        progressMessage: failureMessage,
        canCancel: false,
        canRetry: true
      })
      notify("tldw_server", failureMessage)
    }

    const retryIngestSessionById = async (
      funnelId: string,
      reason: "manual_retry" | "auth_replay"
    ): Promise<{ ok: boolean; error?: string }> => {
      const session = ingestSessions.get(funnelId)
      if (!session) return { ok: false, error: "Ingest session not found." }
      if (session.status === "queued" || session.status === "running") {
        return { ok: false, error: "Ingest is already in progress." }
      }
      pendingAuthReplay.delete(funnelId)
      session.retryCount += 1
      void startContextMenuIngest(session, {
        trackContextClick: false,
        reason
      })
      return { ok: true }
    }

    const replayPendingAuthSessions = async () => {
      if (pendingAuthReplay.size === 0) return
      const cfg = await storage.get<any>("tldwConfig")
      if (!hasUsableAuthConfig(cfg)) return
      for (const funnelId of Array.from(pendingAuthReplay)) {
        pendingAuthReplay.delete(funnelId)
        const session = ingestSessions.get(funnelId)
        if (!session) continue
        session.awaitingAuth = false
        void startContextMenuIngest(session, {
          trackContextClick: false,
          reason: "auth_replay"
        })
      }
    }

    const handleRuntimeMessage = async (message: any, sender: any) => {
      // Simple ping for E2E tests - verifies message handler is working
      if (message.type === "tldw:ping") {
        return { ok: true, pong: true, timestamp: Date.now() }
      }
      if (message.type === "tldw:diagnostics") {
        return { ok: true, data: buildBackgroundDiagnostics() }
      }
      if (message.type === 'tldw:debug') {
        streamDebugEnabled = Boolean(message?.enable)
        return { ok: true }
      }
      if (message.type === 'tldw:models:refresh') {
        try {
          const models = await warmModels(true, true)
          const count = Array.isArray(models) ? models.length : 0
          return { ok: true, count }
        } catch (e: any) {
          return { ok: false, error: e?.message || 'Model refresh failed' }
        }
      }
      if (message.type === 'tldw:get-tab-id') {
        const tabId = sender?.tab?.id ?? null
        return { ok: tabId != null, tabId }
      }
      if (message.type === 'tldw:quick-ingest-batch') {
        console.log('[QUICK_INGEST] Message received')
        const payload = message.payload || {}
        const entries = Array.isArray(payload.entries) ? payload.entries : []
        const files = Array.isArray(payload.files) ? payload.files : []
        console.log('[QUICK_INGEST] Parsed payload', { entriesCount: entries.length, filesCount: files.length })
        const storeRemote = Boolean(payload.storeRemote)
        const processOnly = Boolean(payload.processOnly)
        const common = payload.common || {}
        const advancedValues = payload.advancedValues && typeof payload.advancedValues === 'object'
          ? payload.advancedValues
          : {}
        const fileDefaults = payload.fileDefaults && typeof payload.fileDefaults === 'object'
          ? payload.fileDefaults
          : {}
        // Chunking template options
        const chunkingTemplateName = typeof payload.chunkingTemplateName === 'string'
          ? payload.chunkingTemplateName
          : undefined
        const autoApplyTemplate = Boolean(payload.autoApplyTemplate)
        // processOnly=true forces local-only processing even if storeRemote was requested
        const shouldStoreRemote = storeRemote && !processOnly
        console.log('[QUICK_INGEST] Options', { storeRemote, processOnly, shouldStoreRemote })
        const cfg = await storage.get<any>('tldwConfig')
        console.log('[QUICK_INGEST] Config loaded', { serverUrl: cfg?.serverUrl, authMode: cfg?.authMode })
        const ingestTimeoutMs = Math.max(
          Number(cfg?.uploadRequestTimeoutMs) || 0,
          Number(cfg?.mediaRequestTimeoutMs) || 0,
          Number(cfg?.requestTimeoutMs) || 0,
          5 * 60 * 1000
        )
        const totalCount = entries.length + files.length
        let processedCount = 0

        const assignPath = (obj: any, path: string[], val: any) => {
          let cur = obj
          for (let i = 0; i < path.length; i++) {
            const seg = path[i]
            if (i === path.length - 1) cur[seg] = val
            else cur = (cur[seg] = cur[seg] || {})
          }
        }

        const buildFields = (rawType: string, entry?: any, defaults?: any) => {
          const mediaType = normalizeMediaType(rawType)
          const fields: Record<string, any> = {
            media_type: mediaType,
            perform_analysis: Boolean(common.perform_analysis),
            perform_chunking: Boolean(common.perform_chunking),
            overwrite_existing: Boolean(common.overwrite_existing)
          }
          const resolvedDefaults: {
            audio?: { language?: string; diarize?: boolean }
            document?: { ocr?: boolean }
            video?: { captions?: boolean }
          } = (() => {
            if (!defaults || typeof defaults !== 'object') return {}
            if (mediaType === 'audio') return { audio: defaults.audio }
            if (mediaType === 'video') {
              return { audio: defaults.audio, video: defaults.video }
            }
            if (mediaType === 'document' || mediaType === 'pdf' || mediaType === 'ebook') {
              return { document: defaults.document }
            }
            return {}
          })()
          const nested: Record<string, any> = {}
          for (const [k, v] of Object.entries(advancedValues as Record<string, any>)) {
            if (k.includes('.')) assignPath(nested, k.split('.'), v)
            else fields[k] = v
          }
          for (const [k, v] of Object.entries(nested)) fields[k] = v
          if (typeof entry?.keywords === "string") {
            const trimmed = entry.keywords.trim()
            if (trimmed) {
              fields.keywords = trimmed
            }
          }
          const audio = { ...(resolvedDefaults.audio || {}), ...(entry?.audio || {}) }
          const video = { ...(resolvedDefaults.video || {}), ...(entry?.video || {}) }
          const document = { ...(resolvedDefaults.document || {}), ...(entry?.document || {}) }
          if (audio.language && fields.transcription_language == null) {
            fields.transcription_language = audio.language
          }
          if (typeof audio.diarize === 'boolean' && fields.diarize == null) {
            fields.diarize = audio.diarize
          }
          if (typeof video.captions === 'boolean' && fields.timestamp_option == null) {
            fields.timestamp_option = video.captions
          }
          if (typeof document.ocr === 'boolean' && fields.pdf_parsing_engine == null) {
            fields.pdf_parsing_engine = document.ocr ? 'pymupdf4llm' : ''
          }
          // Add chunking template fields if provided
          if (chunkingTemplateName) {
            fields.chunking_template_name = chunkingTemplateName
          }
          if (autoApplyTemplate) {
            fields.auto_apply_template = true
          }
          return fields
        }

        const processWebScrape = async (url: string, entry?: any) => {
          const nestedBody: Record<string, any> = {}
          for (const [k, v] of Object.entries(advancedValues as Record<string, any>)) {
            if (k.includes('.')) assignPath(nestedBody, k.split('.'), v)
            else nestedBody[k] = v
          }
          const normalizeJsonField = (value: unknown) => {
            if (typeof value !== 'string') return value
            const trimmed = value.trim()
            if (!trimmed) return value
            const looksJson =
              (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
              (trimmed.startsWith('[') && trimmed.endsWith(']'))
            if (!looksJson) return value
            try {
              return JSON.parse(trimmed)
            } catch {
              return value
            }
          }
          const normalizedBody: Record<string, any> = { ...nestedBody }
          for (const key of ['custom_headers', 'custom_cookies', 'custom_titles']) {
            if (key in normalizedBody) {
              normalizedBody[key] = normalizeJsonField(normalizedBody[key])
            }
          }
          const body: any = {
            scrape_method: 'Individual URLs',
            url_input: url,
            mode: 'ephemeral',
            summarize_checkbox: Boolean(common.perform_analysis),
            ...normalizedBody
          }
          if (typeof entry?.keywords === "string") {
            const trimmed = entry.keywords.trim()
            if (trimmed) {
              body.keywords = trimmed
            }
          }
          const resp = await handleTldwRequest({
            path: '/api/v1/media/process-web-scraping',
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
            timeoutMs: ingestTimeoutMs
          }) as { ok: boolean; error?: string; status?: number; data?: any } | undefined
          if (!resp?.ok) {
            const msg = resp?.error || `Request failed: ${resp?.status}`
            throw new Error(msg)
          }
          return resp.data
        }

        const out: any[] = []

        const emitProgress = (result: any) => {
          processedCount += 1
          // Best-effort OS notification
          try {
            const label =
              result?.url ||
              result?.fileName ||
              (result?.type === 'file' ? 'File' : 'Item')
            const statusLabel =
              result?.status === 'ok'
                ? 'Completed'
                : result?.status === 'error'
                  ? 'Failed'
                  : 'Processed'
            const chromeNotifications = (
              globalThis as {
                chrome?: {
                  notifications?: {
                    create?: (options: {
                      type: string
                      iconUrl: string
                      title: string
                      message: string
                    }) => void
                  }
                }
              }
            ).chrome?.notifications
            chromeNotifications?.create?.({
              type: 'basic',
              iconUrl: '/icon.png',
              title: 'Quick Ingest',
              message: `${processedCount}/${totalCount}: ${label} – ${statusLabel}`
            })
          } catch (error) {
            logBackgroundError("quick ingest notification", error)
          }

          // In-app progress event for any open UI
          try {
            void browser.runtime
              .sendMessage({
                type: 'tldw:quick-ingest-progress',
                payload: {
                  result,
                  processedCount,
                  totalCount
                }
              })
              .catch((error) => {
                logBackgroundError("quick ingest progress message", error)
              })
          } catch (error) {
            logBackgroundError("quick ingest progress message", error)
          }
        }

        // Process URL entries
        for (const r of entries) {
          const url = String(r?.url || '').trim()
          if (!url) continue
          const explicitType = r?.type && typeof r.type === 'string' ? r.type : 'auto'
          const t = explicitType === 'auto' ? inferMediaTypeFromUrl(url) : explicitType
          try {
            let data: any
            if (shouldStoreRemote) {
              // Ingest & store via multipart form
              const resolvedDefaults =
                r?.defaults && typeof r.defaults === 'object' ? r.defaults : fileDefaults
              const fields: Record<string, any> = buildFields(t, r, resolvedDefaults)
              fields.urls = [url]
              const resp = await handleUpload({
                path: '/api/v1/media/add',
                method: 'POST',
                fields,
                timeoutMs: ingestTimeoutMs
              })
              if (!resp?.ok) {
                const msg = resp?.error || `Upload failed: ${resp?.status}`
                throw new Error(msg)
              }
              data = resp.data
            } else {
              // Process only (no store)
              if (t === 'html') {
                data = await processWebScrape(url, r)
              } else {
                const resolvedDefaults =
                  r?.defaults && typeof r.defaults === 'object' ? r.defaults : fileDefaults
                const fields = buildFields(t, r, resolvedDefaults)
                fields.urls = [url]
                const resp = await handleUpload({
                  path: getProcessPathForType(t),
                  method: 'POST',
                  fields,
                  timeoutMs: ingestTimeoutMs
                })
                if (!resp?.ok) {
                  const msg = resp?.error || `Upload failed: ${resp?.status}`
                  throw new Error(msg)
                }
                data = resp.data
              }
            }
            const result = { id: r.id, status: 'ok', url, type: t, data }
            out.push(result)
            emitProgress(result)
          } catch (e: any) {
            const result = {
              id: r.id,
              status: 'error',
              url,
              type: t,
              error: e?.message || 'Request failed'
            }
            out.push(result)
            emitProgress(result)
          }
        }

        // Process local files (upload or process)
        console.log('[QUICK_INGEST] Starting file processing loop', { fileCount: files.length })
        for (const f of files) {
          const id = f?.id || crypto.randomUUID()
          const name = f?.name || 'upload'
          const mediaType = inferUploadMediaTypeFromFile(name, f?.type)
          console.log('[QUICK_INGEST] Processing file', { id, name, mediaType, dataLength: f?.data?.length })
          const resolvedFileDefaults =
            f?.defaults && typeof f.defaults === 'object'
              ? f.defaults
              : fileDefaults
          try {
            let data: any
            if (shouldStoreRemote) {
              const fields: Record<string, any> = buildFields(
                mediaType,
                undefined,
                resolvedFileDefaults
              )
              console.log('[QUICK_INGEST] Calling handleUpload', { path: '/api/v1/media/add', name, mediaType })
              const resp = await handleUpload({
                path: '/api/v1/media/add',
                method: 'POST',
                fields,
                file: { name, type: f?.type || 'application/octet-stream', data: f?.data },
                timeoutMs: ingestTimeoutMs
              })
              console.log('[QUICK_INGEST] handleUpload returned', { ok: resp?.ok, status: resp?.status, error: resp?.error })
              if (!resp?.ok) {
                const msg = resp?.error || `Upload failed: ${resp?.status}`
                throw new Error(msg)
              }
              data = resp.data
            } else {
              const fields: Record<string, any> = buildFields(
                mediaType,
                undefined,
                resolvedFileDefaults
              )
              const resp = await handleUpload({
                path: getProcessPathForType(mediaType),
                method: 'POST',
                fields,
                file: { name, type: f?.type || 'application/octet-stream', data: f?.data },
                timeoutMs: ingestTimeoutMs
              })
              if (!resp?.ok) {
                const msg = resp?.error || `Upload failed: ${resp?.status}`
                throw new Error(msg)
              }
              data = resp.data
            }
            const result = { id, status: 'ok', fileName: name, type: mediaType, data }
            out.push(result)
            emitProgress(result)
          } catch (e: any) {
            const result = {
              id,
              status: 'error',
              fileName: name,
              type: 'file',
              error: e?.message || 'Upload failed'
            }
            out.push(result)
            emitProgress(result)
          }
        }

        return { ok: true, results: out }
      }
      if (message.type === "sidepanel") {
        try {
          const tabId = sender?.tab?.id ?? undefined
          ensureSidepanelOpen(tabId)
        } catch (error) {
          logBackgroundError("ensure sidepanel open", error)
        }
        return undefined
      }
      if (message.type === "tldw:media-ingest/cancel") {
        const funnelId = String(message?.payload?.funnelId || "").trim()
        if (!funnelId) {
          return { ok: false, error: "Missing funnelId" }
        }
        return await cancelIngestSessionById(
          funnelId,
          String(message?.payload?.reason || "user_cancelled")
        )
      }
      if (message.type === "tldw:media-ingest/retry") {
        const funnelId = String(message?.payload?.funnelId || "").trim()
        if (!funnelId) {
          return { ok: false, error: "Missing funnelId" }
        }
        return await retryIngestSessionById(funnelId, "manual_retry")
      }
      if (message.type === "tldw:media-ingest/open-auth-settings") {
        await openAuthSettings()
        return { ok: true }
      }
      if (message.type === "tldw:media-ingest/funnel-event") {
        const funnelId = String(message?.payload?.funnelId || "").trim()
        const event = String(message?.payload?.event || "").trim()
        if (!funnelId || !event) {
          return { ok: false, error: "Missing funnel metric payload" }
        }
        if (
          event === "context_click" ||
          event === "job_queued" ||
          event === "media_completed" ||
          event === "first_chat_message"
        ) {
          await appendIngestFunnelMetric(event as IngestFunnelEvent, funnelId, {
            ...(message?.payload?.metadata && typeof message.payload.metadata === "object"
              ? message.payload.metadata
              : {})
          })
          return { ok: true }
        }
        return { ok: false, error: "Unsupported funnel event" }
      }
      if (message.type === 'tldw:upload') {
        return handleUpload(message.payload || {})
      }
      if (message.type === 'tldw:request') {
        return handleTldwRequest(message.payload || {})
      }
      if (message.type === 'tldw:ingest') {
        try {
          const tabs = await browser.tabs.query({ active: true, currentWindow: true })
          const tab = tabs[0]
          const pageUrl = resolveContextMenuTargetUrl({ pageUrl: tab?.url || "" }, tab)
          if (!pageUrl) return { ok: false, status: 400, error: 'No active tab URL' }
          if (message.mode === "process") {
            return await handleTldwRequest(buildContextMenuProcessPayload(pageUrl))
          }
          return await handleUpload(buildContextMenuAddPayload(pageUrl))
        } catch (e: any) {
          return { ok: false, status: 0, error: e?.message || 'Ingest failed' }
        }
      }
      return undefined
    }

    console.log('[BG_STARTUP] Registering message listener')
    const chromeGlobal = (globalThis as any).chrome
    console.log('[BG_STARTUP] browser.runtime:', {
      hasSendMessage: !!browser?.runtime?.sendMessage,
      hasOnMessage: !!browser?.runtime?.onMessage,
      hasOnMessageAddListener: !!browser?.runtime?.onMessage?.addListener,
      browserType: typeof browser,
      chromeType: typeof chromeGlobal,
      sameSendMessage: browser?.runtime?.sendMessage === chromeGlobal?.runtime?.sendMessage,
      sameOnMessage: browser?.runtime?.onMessage === chromeGlobal?.runtime?.onMessage
    })

    // Also add a direct chrome listener as backup
    if (chromeGlobal?.runtime?.onMessage?.addListener) {
      chromeGlobal.runtime.onMessage.addListener((message: any, sender: any, sendResponse: any) => {
        console.log('[BG_MSG_CHROME] Received via chrome.runtime:', { type: message?.type })
        if (message?.type === 'tldw:ping') {
          sendResponse({ ok: true, pong: true, timestamp: Date.now(), source: 'chrome-listener' })
          return true
        }
        return false
      })
      console.log('[BG_STARTUP] Also added chrome.runtime.onMessage listener')
    }

    // Log raw listener registration
    console.log('[BG_STARTUP] About to add browser.runtime.onMessage listener', {
      onMessage: !!browser.runtime.onMessage,
      addListener: typeof browser.runtime.onMessage?.addListener
    })

    browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
      // Log EVERY message that arrives, even malformed ones
      console.log('[BG_MSG_RAW] Raw message received!', {
        messageType: typeof message,
        messageKeys: message ? Object.keys(message) : [],
        type: message?.type,
        hasPayload: !!message?.payload,
        senderUrl: sender?.url,
        senderId: sender?.id
      })
      console.log('[BG_MSG] Received message', { type: message?.type, hasPayload: !!message?.payload })
      void handleRuntimeMessage(message, sender)
        .then((response) => {
          console.log('[BG_MSG] Sending response', { type: message?.type, ok: response?.ok })
          sendResponse(response)
        })
        .catch((error) => {
          console.log('[BG_MSG] Handler error', { type: message?.type, error: String(error) })
          logBackgroundError("runtime message", error)
          sendResponse({
            ok: false,
            status: 0,
            error: (error as Error)?.message || "Background error"
          })
        })
      return true
    })
    console.log('[BG_STARTUP] Message listener registered')

    browser.storage.onChanged.addListener((changes, areaName) => {
      if (areaName !== "local") return
      if (!changes || !Object.prototype.hasOwnProperty.call(changes, "tldwConfig")) {
        return
      }
      void replayPendingAuthSessions()
    })

    browser.runtime.onConnect.addListener((port) => {
      console.log('[BG_CONNECT] Port connected', { name: port.name })
      if (port.name === "pgCopilot") {
        isCopilotRunning = true
        backgroundDiagnostics.ports.copilot += 1
        backgroundDiagnostics.lastCopilotAt = Date.now()
        port.onDisconnect.addListener(() => {
          isCopilotRunning = false
          backgroundDiagnostics.ports.copilot = Math.max(
            0,
            backgroundDiagnostics.ports.copilot - 1
          )
        })
      } else if (port.name === 'tldw:stt') {
        backgroundDiagnostics.ports.stt += 1
        backgroundDiagnostics.lastSttAt = Date.now()
        let ws: WebSocket | null = null
        let disconnected = false
        let connectTimer: ReturnType<typeof setTimeout> | null = null
        const safePost = (msg: any) => {
          if (disconnected) return
          try {
            port.postMessage(msg)
          } catch (error) {
            logBackgroundError("stt port postMessage", error)
          }
        }
        const onMsg = async (msg: any) => {
          try {
            if (msg?.action === 'connect') {
              const cfg = await storage.get<any>('tldwConfig')
              if (!cfg?.serverUrl) throw new Error('tldw server not configured')
              const base = cfg.serverUrl.replace(/^http/, 'ws').replace(/\/$/, '')
              const rawToken = cfg.authMode === 'single-user' ? cfg.apiKey : cfg.accessToken
              const token = String(rawToken || '').trim()
              if (!token) {
                throw new Error('Not authenticated. Configure tldw credentials in Settings > tldw.')
              }
              const url = `${base}/api/v1/audio/stream/transcribe?token=${encodeURIComponent(token)}`
              ws = new WebSocket(url)
              ws.binaryType = 'arraybuffer'
              connectTimer = setTimeout(() => {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                  safePost({ event: 'error', message: 'STT connection timeout. Check tldw server health.' })
                  try {
                    ws?.close()
                  } catch (error) {
                    logBackgroundError("stt websocket close (timeout)", error)
                  }
                  ws = null
                }
              }, 10000)
              ws.onopen = () => {
                if (connectTimer) {
                  clearTimeout(connectTimer)
                  connectTimer = null
                }
                safePost({ event: 'open' })
              }
              ws.onmessage = (ev) => safePost({ event: 'data', data: ev.data })
              ws.onerror = () => safePost({ event: 'error', message: 'STT websocket error' })
              ws.onclose = () => {
                if (connectTimer) {
                  clearTimeout(connectTimer)
                  connectTimer = null
                }
                safePost({ event: 'close' })
              }
            } else if (msg?.action === 'audio' && ws && ws.readyState === WebSocket.OPEN) {
              if (msg.data instanceof ArrayBuffer) {
                ws.send(msg.data)
              } else if (msg.data?.buffer) {
                ws.send(msg.data.buffer)
              }
            } else if (msg?.action === 'close') {
              try {
                ws?.close()
              } catch (error) {
                logBackgroundError("stt websocket close", error)
              }
              ws = null
            }
          } catch (e: any) {
            safePost({ event: 'error', message: e?.message || 'ws error' })
          }
        }
        port.onMessage.addListener(onMsg)
        port.onDisconnect.addListener(() => {
          disconnected = true
          backgroundDiagnostics.ports.stt = Math.max(
            0,
            backgroundDiagnostics.ports.stt - 1
          )
          try {
            port.onMessage.removeListener(onMsg)
          } catch (error) {
            logBackgroundError("stt port removeListener", error)
          }
          if (connectTimer) {
            clearTimeout(connectTimer)
            connectTimer = null
          }
          try {
            ws?.close()
          } catch (error) {
            logBackgroundError("stt websocket close (disconnect)", error)
          }
        })
      }
    })

    const actionApi = getActionApi()
    const openOptionsTab = () => {
      const url = browser.runtime.getURL("/options.html#/")
      browser.tabs.create({ url })
    }
    actionApi?.onClicked?.addListener((tab: any) => {
      if (actionIconClick === "webui") {
        openOptionsTab()
      } else {
        ensureSidepanelOpen(tab?.id)
      }
    })

    browser.contextMenus.onClicked.addListener(async (info, tab) => {
      if (info.menuItemId === "open-side-panel-pa") {
        ensureSidepanelOpen(tab?.id)
      } else if (info.menuItemId === "open-web-ui-pa") {
        openOptionsTab()
      } else if (info.menuItemId === transcribeMenuId.transcribe) {
        await handleTranscribeClick(info, tab, 'transcribe')
      } else if (info.menuItemId === transcribeMenuId.transcribeAndSummarize) {
        await handleTranscribeClick(info, tab, 'transcribe+summary')
      } else if (info.menuItemId === saveToNotesMenuId) {
        const selection = String(info.selectionText || '').trim()
        if (!selection) {
          notify(browser.i18n.getMessage("contextSaveToNotes"), browser.i18n.getMessage("contextSaveToNotesNoSelection"))
          return
        }
        const title = browser.i18n.getMessage("contextSaveToNotes") || "Save to Notes"
        const openingMessage =
          browser.i18n.getMessage("contextSaveToNotesOpeningSidebar") ||
          "Opening sidebar to save note…"
        notify(title, openingMessage)
        setTimeout(
          async () => {
            try {
              await ensureSidepanelOpen(tab.id!)
              await browser.runtime.sendMessage({
                from: "background",
                type: "save-to-notes",
                text: selection,
                payload: {
                  selectionText: selection,
                  pageUrl: info.pageUrl || (tab && tab.url) || "",
                  pageTitle: tab?.title || ""
                }
              })
            } catch (e: any) {
              const failureMessage =
                browser.i18n.getMessage("contextSaveToNotesDeliveryFailed") ||
                "Could not open the sidebar to save this note. Check that the tldw Assistant sidepanel is allowed on this site and try again."
              notify(title, failureMessage)
            }
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === narrateSelectionMenuId) {
        const selection = String(info.selectionText || "").trim()
        if (!selection) {
          notify(
            browser.i18n.getMessage("contextNarrateSelection"),
            browser.i18n.getMessage("contextNarrateSelectionNoSelection")
          )
          return
        }
        const title =
          browser.i18n.getMessage("contextNarrateSelection") ||
          "Narrate selection"
        const openingMessage =
          browser.i18n.getMessage("contextSidebarOpening") || "Opening sidebar..."
        notify(title, openingMessage)
        setTimeout(
          async () => {
            try {
              await ensureSidepanelOpen(tab?.id)
              await browser.runtime.sendMessage({
                from: "background",
                type: "narrate-selection",
                text: selection,
                payload: {
                  selectionText: selection,
                  pageUrl: info.pageUrl || (tab && tab.url) || "",
                  pageTitle: tab?.title || ""
                }
              })
            } catch (e) {
              console.error("[tldw] narrate selection failed:", e)
            }
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "send-to-tldw") {
        try {
          const targetUrl = resolveContextMenuTargetUrl(info, tab)
          if (!targetUrl) return
          const addPayload = buildContextMenuAddPayload(targetUrl)
          const session: IngestSession = {
            funnelId: createFunnelId(),
            url: targetUrl,
            normalizedUrl: normalizeUrlForDedupe(targetUrl),
            tabId: tab?.id,
            status: "queued",
            jobIds: [],
            createdAt: Date.now(),
            retryCount: 0,
            awaitingAuth: false,
            timestampSeconds: extractYouTubeTimestampSeconds(targetUrl)
          }
          notify("tldw_server", "Starting ingest…")
          void startContextMenuIngest(session, {
            trackContextClick: true,
            reason: "initial"
          })
        } catch (e) {
          console.error("Failed to send to tldw_server:", e)
          notify("tldw_server", "Failed to send item to tldw_server")
        }
      } else if (info.menuItemId === "process-local-tldw") {
        try {
          const targetUrl = resolveContextMenuTargetUrl(info, tab)
          if (!targetUrl) return
          const resp = await handleTldwRequest(buildContextMenuProcessPayload(targetUrl))
          if (!resp?.ok) {
            throw new Error(resp?.error || "Processing failed")
          }
          notify("tldw_server", "Processed page (not saved to server)")
        } catch (e) {
          console.error("Failed to process locally:", e)
          notify("tldw_server", "Failed to process page")
        }
      } else if (info.menuItemId === "summarize-pa") {
        ensureSidepanelOpen(tab?.id)
        // this is a bad method hope somone can fix it :)
        setTimeout(
          async () => {
            await browser.runtime.sendMessage({
              from: "background",
              type: "summary",
              text: info.selectionText
            })
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "rephrase-pa") {
        ensureSidepanelOpen(tab?.id)
        setTimeout(
          async () => {
            await browser.runtime.sendMessage({
              type: "rephrase",
              from: "background",
              text: info.selectionText
            })
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "translate-pg") {
        ensureSidepanelOpen(tab?.id)

        setTimeout(
          async () => {
            await browser.runtime.sendMessage({
              type: "translate",
              from: "background",
              text: info.selectionText
            })
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "explain-pa") {
        ensureSidepanelOpen(tab?.id)

        setTimeout(
          async () => {
            await browser.runtime.sendMessage({
              type: "explain",
              from: "background",
              text: info.selectionText
            })
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "custom-pg") {
        ensureSidepanelOpen(tab?.id)

        setTimeout(
          async () => {
            await browser.runtime.sendMessage({
              type: "custom",
              from: "background",
              text: info.selectionText
            })
          },
          isCopilotRunning ? 0 : 5000
        )
      } else if (info.menuItemId === "contextual-popup-pa") {
        const selection = String(info.selectionText || "").trim()
        if (!selection) {
          notify(
            browser.i18n.getMessage("contextCopilotPopup"),
            browser.i18n.getMessage("contextCopilotPopupNoSelection")
          )
          return
        }
        const tabId = tab?.id
        if (!tabId) {
          notify(
            browser.i18n.getMessage("contextCopilotPopup"),
            browser.i18n.getMessage("contextCopilotPopupNoTab")
          )
          return
        }
        try {
          await browser.tabs.sendMessage(
            tabId,
            {
              type: "tldw:popup:open",
              payload: {
                selectionText: selection,
                pageUrl: info.pageUrl || tab?.url || "",
                pageTitle: tab?.title || "",
                frameId: info.frameId
              }
            },
            typeof info.frameId === "number" ? { frameId: info.frameId } : undefined
          )
        } catch (error) {
          logBackgroundError("contextual popup sendMessage", error)
          notify(
            browser.i18n.getMessage("contextCopilotPopup"),
            browser.i18n.getMessage("contextCopilotPopupDeliveryFailed")
          )
        }
      }
    })

    browser.commands.onCommand.addListener((command) => {
      switch (command) {
        case "execute_side_panel":
          browser.tabs
            .query({ active: true, currentWindow: true })
            .then((tabs) => {
              const tab = tabs[0]
              ensureSidepanelOpen(tab?.id)
            })
            .catch(() => {
              ensureSidepanelOpen()
            })
          break
        default:
          break
      }
    })

    // Stream handler via Port API
    browser.runtime.onConnect.addListener((port) => {
      if (port.name === 'tldw:stream') {
        backgroundDiagnostics.ports.stream += 1
        backgroundDiagnostics.lastStreamAt = Date.now()
        let abort: AbortController | null = null
        let idleTimer: any = null
        let closed = false
        let disconnected = false
        const safePost = (msg: any) => {
          if (disconnected) return
          try {
            port.postMessage(msg)
          } catch (error) {
            logBackgroundError("stream port postMessage", error)
          }
        }
        const onMsg = async (msg: any) => {
          try {
            const cfg = await storage.get<any>('tldwConfig')
            if (!cfg?.serverUrl) throw new Error('tldw server not configured')
            const baseUrl = String(cfg.serverUrl).replace(/\/$/, '')
            const path = msg.path as string
            const url = path.startsWith('http') ? path : `${baseUrl}${path.startsWith('/') ? '' : '/'}${path}`
            const headers: Record<string, string> = { ...(msg.headers || {}) }
            for (const k of Object.keys(headers)) {
              const kl = k.toLowerCase()
              if (kl === 'x-api-key' || kl === 'authorization') delete headers[k]
            }
            if (cfg.authMode === 'single-user') {
              const key = (cfg.apiKey || '').trim()
              if (!key) {
                safePost({
                  event: 'error',
                  message:
                    'Add or update your API key in Settings → tldw server, then try again.'
                })
                return
              }
              headers['X-API-KEY'] = key
            } else if (cfg.authMode === 'multi-user') {
              const token = (cfg.accessToken || '').trim()
              if (token) headers['Authorization'] = `Bearer ${token}`
              else { safePost({ event: 'error', message: 'Not authenticated. Please login under Settings > tldw.' }); return }
            }
            headers['Accept'] = 'text/event-stream'
            headers['Cache-Control'] = headers['Cache-Control'] || 'no-cache'
            headers['Connection'] = headers['Connection'] || 'keep-alive'
            abort = new AbortController()
            const idleMs = deriveStreamIdleTimeout(cfg, path, Number(msg?.streamIdleTimeoutMs))
            const resetIdle = () => {
              if (idleTimer) clearTimeout(idleTimer)
              idleTimer = setTimeout(() => {
                if (!closed) {
                  try {
                    abort?.abort()
                  } catch (error) {
                    logBackgroundError("stream abort", error)
                  }
                  safePost({ event: 'error', message: 'Stream timeout: no updates received' })
                }
              }, idleMs)
            }
            // Ensure SSE-friendly headers
            headers['Accept'] = headers['Accept'] || 'text/event-stream'
            headers['Cache-Control'] = headers['Cache-Control'] || 'no-cache'
            headers['Connection'] = headers['Connection'] || 'keep-alive'

            let resp = await fetch(url, {
              method: msg.method || 'POST',
              headers,
              body: typeof msg.body === 'string' ? msg.body : JSON.stringify(msg.body),
              signal: abort.signal
            })
            if (resp.status === 401 && cfg.authMode === 'multi-user' && cfg.refreshToken) {
              if (!refreshInFlight) {
                refreshInFlight = (async () => {
                  try {
                    await tldwAuth.refreshToken()
                  } finally {
                    refreshInFlight = null
                  }
                })()
              }
              try {
                await refreshInFlight
              } catch (error) {
                logBackgroundError("refresh auth (stream)", error)
              }
              const updated = await storage.get<any>('tldwConfig')
              if (updated?.accessToken) headers['Authorization'] = `Bearer ${updated.accessToken}`
              const retryController = new AbortController()
              abort = retryController
              resp = await fetch(url, {
                method: msg.method || 'POST',
                headers,
                body: typeof msg.body === 'string' ? msg.body : JSON.stringify(msg.body),
                signal: retryController.signal
              })
            }
            if (!resp.ok) {
              const ct = resp.headers.get('content-type') || ''
              let errMsg: any = resp.statusText
              if (ct.includes('application/json')) {
                const j = await resp.json().catch(() => null)
                if (j && (j.detail || j.error || j.message)) errMsg = j.detail || j.error || j.message
              } else {
                const t = await resp.text().catch(() => null)
                if (t) errMsg = t
              }
              safePost({
                event: "error",
                message: formatErrorMessage(errMsg, `HTTP ${resp.status}`)
              })
              return
            }
            if (!resp.body) throw new Error('No response body')
            const reader = resp.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            resetIdle()
            while (true) {
              const { done, value } = await reader.read()
              if (done) break
              resetIdle()
              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split('\n')
              buffer = lines.pop() || ''
              for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed) continue
                // Any SSE activity resets idle timer
                resetIdle()
                if (trimmed.startsWith('event:')) {
                  const name = trimmed.slice(6).trim()
                  if (streamDebugEnabled) {
                    try {
                      await browser.runtime.sendMessage({
                        type: 'tldw:stream-debug',
                        payload: { kind: 'event', name, time: Date.now() }
                      })
                    } catch (error) {
                      logBackgroundError("stream debug event", error)
                    }
                  }
                } else if (trimmed.startsWith('data:')) {
                  const data = trimmed.slice(5).trim()
                  if (streamDebugEnabled) {
                    try {
                      await browser.runtime.sendMessage({
                        type: 'tldw:stream-debug',
                        payload: { kind: 'data', data, time: Date.now() }
                      })
                    } catch (error) {
                      logBackgroundError("stream debug data", error)
                    }
                  }
                  if (data === '[DONE]') {
                    closed = true
                    if (idleTimer) clearTimeout(idleTimer)
                    safePost({ event: 'done' })
                    return
                  }
                  safePost({ event: 'data', data })
                } else if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                  // Some servers may omit the 'data:' prefix; treat JSON lines as data
                  const data = trimmed
                  if (streamDebugEnabled) {
                    try {
                      await browser.runtime.sendMessage({
                        type: 'tldw:stream-debug',
                        payload: { kind: 'data', data, time: Date.now() }
                      })
                    } catch (error) {
                      logBackgroundError("stream debug json", error)
                    }
                  }
                  safePost({ event: 'data', data })
                }
              }
            }
            closed = true
            if (idleTimer) clearTimeout(idleTimer)
            safePost({ event: 'done' })
          } catch (e: any) {
            if (idleTimer) clearTimeout(idleTimer)
            safePost({
              event: "error",
              message: formatErrorMessage(e, "Stream error")
            })
          }
        }
        port.onMessage.addListener(onMsg)
        port.onDisconnect.addListener(() => {
          disconnected = true
          backgroundDiagnostics.ports.stream = Math.max(
            0,
            backgroundDiagnostics.ports.stream - 1
          )
          try {
            port.onMessage.removeListener(onMsg)
          } catch (error) {
            logBackgroundError("stream port removeListener", error)
          }
          try {
            abort?.abort()
          } catch (error) {
            logBackgroundError("stream abort (disconnect)", error)
          }
        })
      }
    })

    if (browser?.alarms) {
      browser.alarms.onAlarm.addListener((alarm) => {
        if (alarm.name !== MODEL_WARM_ALARM_NAME) return
        backgroundDiagnostics.alarmFires += 1
        backgroundDiagnostics.lastAlarmAt = Date.now()
        void warmModels(true)
      })
    }

    initialize()
  },
  persistent: false
})
