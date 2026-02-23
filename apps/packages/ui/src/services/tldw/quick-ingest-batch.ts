import { browser } from "wxt/browser"
import { bgRequest, bgUpload } from "@/services/background-proxy"
import {
  getProcessPathForType,
  inferIngestTypeFromUrl,
  inferUploadMediaTypeFromFile,
  normalizeMediaType
} from "@/services/tldw/media-routing"

type TypeDefaults = {
  audio?: { language?: string; diarize?: boolean }
  document?: { ocr?: boolean }
  video?: { captions?: boolean }
}

type QuickIngestEntry = {
  id: string
  url: string
  type: "auto" | "html" | "pdf" | "document" | "audio" | "video"
  defaults?: TypeDefaults
  keywords?: string
  audio?: { language?: string; diarize?: boolean }
  document?: { ocr?: boolean }
  video?: { captions?: boolean }
}

type QuickIngestFilePayload = {
  id?: string
  name?: string
  type?: string
  data?: number[] | Uint8Array | ArrayBuffer
  defaults?: TypeDefaults
}

type QuickIngestBatchInput = {
  entries: QuickIngestEntry[]
  files: QuickIngestFilePayload[]
  storeRemote: boolean
  processOnly: boolean
  common?: {
    perform_analysis?: boolean
    perform_chunking?: boolean
    overwrite_existing?: boolean
  }
  advancedValues?: Record<string, any>
  fileDefaults?: TypeDefaults
  chunkingTemplateName?: string
  autoApplyTemplate?: boolean
}

type QuickIngestBatchResult = {
  id: string
  status: "ok" | "error"
  url?: string
  fileName?: string
  type: string
  data?: unknown
  error?: string
}

type QuickIngestBatchResponse = {
  ok: boolean
  error?: string
  results?: QuickIngestBatchResult[]
}

export type QuickIngestStartAck = {
  ok: boolean
  sessionId?: string
  error?: string
}

export type QuickIngestCancelInput = {
  sessionId: string
  reason?: string
}

export type QuickIngestCancelResponse = {
  ok: boolean
  error?: string
}

const EXTENSION_TIMEOUT_MS = 10_000
const DIRECT_INGEST_TIMEOUT_MS = 5 * 60 * 1000

const hasExtensionMessagingRuntime = (): boolean =>
  Boolean(browser?.runtime?.sendMessage && browser?.runtime?.id)

const sendExtensionMessageWithTimeout = async <T>(
  message: Record<string, unknown>,
  timeoutMs: number = EXTENSION_TIMEOUT_MS
): Promise<T> => {
  const extensionPromise = browser.runtime.sendMessage(message)
  const timeoutPromise = new Promise<null>((resolve) => {
    setTimeout(() => resolve(null), timeoutMs)
  })
  const result = await Promise.race([extensionPromise, timeoutPromise])
  if (result === null) {
    throw new Error("Extension messaging timed out. Please try again or reload the page.")
  }
  return result as T
}

const assignPath = (obj: Record<string, any>, path: string[], val: any) => {
  let cur: Record<string, any> = obj
  for (let i = 0; i < path.length; i += 1) {
    const seg = path[i]
    if (!seg) continue
    if (i === path.length - 1) {
      cur[seg] = val
      return
    }
    const existing = cur[seg]
    if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
      cur[seg] = {}
    }
    cur = cur[seg]
  }
}

const normalizeJsonField = (value: unknown) => {
  if (typeof value !== "string") return value
  const trimmed = value.trim()
  if (!trimmed) return value
  const looksJson =
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  if (!looksJson) return value
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

const serializeUploadFields = (
  fields: Record<string, any>
): Record<string, any> => {
  const serialized: Record<string, any> = {}
  for (const [key, value] of Object.entries(fields || {})) {
    if (value == null) continue
    if (Array.isArray(value)) {
      serialized[key] = value.map((entry) =>
        typeof entry === "string" ? entry : JSON.stringify(entry)
      )
      continue
    }
    if (typeof value === "object") {
      serialized[key] = JSON.stringify(value)
      continue
    }
    serialized[key] = value
  }
  return serialized
}

const buildFields = ({
  rawType,
  entry,
  defaults,
  common,
  advancedValues,
  chunkingTemplateName,
  autoApplyTemplate
}: {
  rawType: string
  entry?: QuickIngestEntry
  defaults?: TypeDefaults
  common?: QuickIngestBatchInput["common"]
  advancedValues?: Record<string, any>
  chunkingTemplateName?: string
  autoApplyTemplate?: boolean
}): Record<string, any> => {
  const mediaType = normalizeMediaType(rawType)
  const fields: Record<string, any> = {
    media_type: mediaType,
    perform_analysis: Boolean(common?.perform_analysis),
    perform_chunking: Boolean(common?.perform_chunking),
    overwrite_existing: Boolean(common?.overwrite_existing)
  }

  const nested: Record<string, any> = {}
  for (const [key, value] of Object.entries(advancedValues || {})) {
    if (key.includes(".")) assignPath(nested, key.split("."), value)
    else fields[key] = value
  }
  for (const [key, value] of Object.entries(nested)) {
    fields[key] = value
  }

  if (typeof entry?.keywords === "string") {
    const trimmed = entry.keywords.trim()
    if (trimmed) {
      fields.keywords = trimmed
    }
  }

  const resolvedDefaults: TypeDefaults = (() => {
    if (!defaults || typeof defaults !== "object") return {}
    if (mediaType === "audio") return { audio: defaults.audio }
    if (mediaType === "video") {
      return { audio: defaults.audio, video: defaults.video }
    }
    if (mediaType === "document" || mediaType === "pdf" || mediaType === "ebook") {
      return { document: defaults.document }
    }
    return {}
  })()

  const audio = { ...(resolvedDefaults.audio || {}), ...(entry?.audio || {}) }
  const video = { ...(resolvedDefaults.video || {}), ...(entry?.video || {}) }
  const document = {
    ...(resolvedDefaults.document || {}),
    ...(entry?.document || {})
  }

  if (audio.language && fields.transcription_language == null) {
    fields.transcription_language = audio.language
  }
  if (typeof audio.diarize === "boolean" && fields.diarize == null) {
    fields.diarize = audio.diarize
  }
  if (typeof video.captions === "boolean" && fields.timestamp_option == null) {
    fields.timestamp_option = video.captions
  }
  if (typeof document.ocr === "boolean" && fields.pdf_parsing_engine == null) {
    fields.pdf_parsing_engine = document.ocr ? "pymupdf4llm" : ""
  }

  if (chunkingTemplateName) {
    fields.chunking_template_name = chunkingTemplateName
  }
  if (autoApplyTemplate) {
    fields.auto_apply_template = true
  }

  return fields
}

const processWebScrape = async ({
  url,
  entry,
  common,
  advancedValues
}: {
  url: string
  entry?: QuickIngestEntry
  common?: QuickIngestBatchInput["common"]
  advancedValues?: Record<string, any>
}): Promise<any> => {
  const nestedBody: Record<string, any> = {}
  for (const [key, value] of Object.entries(advancedValues || {})) {
    if (key.includes(".")) assignPath(nestedBody, key.split("."), value)
    else nestedBody[key] = value
  }

  const normalizedBody: Record<string, any> = { ...nestedBody }
  for (const key of ["custom_headers", "custom_cookies", "custom_titles"]) {
    if (key in normalizedBody) {
      normalizedBody[key] = normalizeJsonField(normalizedBody[key])
    }
  }

  const body: Record<string, any> = {
    scrape_method: "Individual URLs",
    url_input: url,
    mode: "ephemeral",
    summarize_checkbox: Boolean(common?.perform_analysis),
    ...normalizedBody
  }

  if (typeof entry?.keywords === "string") {
    const trimmed = entry.keywords.trim()
    if (trimmed) {
      body.keywords = trimmed
    }
  }

  return await bgRequest<any>({
    path: "/api/v1/media/process-web-scraping",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    timeoutMs: DIRECT_INGEST_TIMEOUT_MS
  })
}

const runDirectQuickIngestBatch = async (
  input: QuickIngestBatchInput
): Promise<QuickIngestBatchResponse> => {
  const entries = Array.isArray(input.entries) ? input.entries : []
  const files = Array.isArray(input.files) ? input.files : []
  const fileDefaults =
    input.fileDefaults && typeof input.fileDefaults === "object"
      ? input.fileDefaults
      : {}
  const shouldStoreRemote = Boolean(input.storeRemote) && !Boolean(input.processOnly)

  const out: QuickIngestBatchResult[] = []

  for (const entry of entries) {
    const url = String(entry?.url || "").trim()
    if (!url) continue

    const explicitType =
      entry?.type && typeof entry.type === "string" ? entry.type : "auto"
    const resolvedType =
      explicitType === "auto" ? inferIngestTypeFromUrl(url) : explicitType

    try {
      let data: unknown
      if (shouldStoreRemote) {
        const fields = buildFields({
          rawType: resolvedType,
          entry,
          defaults:
            entry?.defaults && typeof entry.defaults === "object"
              ? entry.defaults
              : fileDefaults,
          common: input.common,
          advancedValues: input.advancedValues,
          chunkingTemplateName: input.chunkingTemplateName,
          autoApplyTemplate: input.autoApplyTemplate
        })
        fields.urls = [url]
        data = await bgUpload<any>({
          path: "/api/v1/media/add",
          method: "POST",
          fields: serializeUploadFields(fields),
          timeoutMs: DIRECT_INGEST_TIMEOUT_MS
        })
      } else if (resolvedType === "html") {
        data = await processWebScrape({
          url,
          entry,
          common: input.common,
          advancedValues: input.advancedValues
        })
      } else {
        const fields = buildFields({
          rawType: resolvedType,
          entry,
          defaults:
            entry?.defaults && typeof entry.defaults === "object"
              ? entry.defaults
              : fileDefaults,
          common: input.common,
          advancedValues: input.advancedValues,
          chunkingTemplateName: input.chunkingTemplateName,
          autoApplyTemplate: input.autoApplyTemplate
        })
        fields.urls = [url]
        data = await bgUpload<any>({
          path: getProcessPathForType(resolvedType),
          method: "POST",
          fields: serializeUploadFields(fields),
          timeoutMs: DIRECT_INGEST_TIMEOUT_MS
        })
      }

      out.push({
        id: entry.id,
        status: "ok",
        url,
        type: resolvedType,
        data
      })
    } catch (error) {
      out.push({
        id: entry.id,
        status: "error",
        url,
        type: resolvedType,
        error: error instanceof Error ? error.message : String(error || "Request failed")
      })
    }
  }

  for (const file of files) {
    const id = String(file?.id || crypto.randomUUID())
    const fileName = String(file?.name || "upload")
    const mediaType = inferUploadMediaTypeFromFile(fileName, file?.type)

    try {
      const fields = buildFields({
        rawType: mediaType,
        defaults:
          file?.defaults && typeof file.defaults === "object"
            ? file.defaults
            : fileDefaults,
        common: input.common,
        advancedValues: input.advancedValues,
        chunkingTemplateName: input.chunkingTemplateName,
        autoApplyTemplate: input.autoApplyTemplate
      })
      const path = shouldStoreRemote
        ? "/api/v1/media/add"
        : getProcessPathForType(mediaType)

      const data = await bgUpload<any>({
        path,
        method: "POST",
        fields: serializeUploadFields(fields),
        file: {
          name: fileName,
          type: file?.type || "application/octet-stream",
          data:
            (file?.data as number[] | Uint8Array | ArrayBuffer | undefined) || []
        },
        timeoutMs: DIRECT_INGEST_TIMEOUT_MS
      })

      out.push({
        id,
        status: "ok",
        fileName,
        type: mediaType,
        data
      })
    } catch (error) {
      out.push({
        id,
        status: "error",
        fileName,
        type: "file",
        error: error instanceof Error ? error.message : String(error || "Upload failed")
      })
    }
  }

  return { ok: true, results: out }
}

export const submitQuickIngestBatch = async (
  input: QuickIngestBatchInput
): Promise<QuickIngestBatchResponse> => {
  if (hasExtensionMessagingRuntime()) {
    const result = await sendExtensionMessageWithTimeout<QuickIngestBatchResponse>({
      type: "tldw:quick-ingest-batch",
      payload: input
    })
    return result
  }

  return await runDirectQuickIngestBatch(input)
}

export const startQuickIngestSession = async (
  input: QuickIngestBatchInput
): Promise<QuickIngestStartAck> => {
  if (hasExtensionMessagingRuntime()) {
    return await sendExtensionMessageWithTimeout<QuickIngestStartAck>({
      type: "tldw:quick-ingest/start",
      payload: input
    })
  }

  // Direct runtimes currently run ingest synchronously. Return a local ack
  // so session-native callers can still establish a run identity.
  return {
    ok: true,
    sessionId: `qi-direct-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  }
}

export const cancelQuickIngestSession = async (
  input: QuickIngestCancelInput
): Promise<QuickIngestCancelResponse> => {
  const sessionId = String(input?.sessionId || "").trim()
  if (!sessionId) {
    return { ok: false, error: "Missing session id." }
  }

  if (hasExtensionMessagingRuntime()) {
    return await sendExtensionMessageWithTimeout<QuickIngestCancelResponse>({
      type: "tldw:quick-ingest/cancel",
      payload: {
        sessionId,
        reason: input?.reason
      }
    })
  }

  return { ok: true }
}
