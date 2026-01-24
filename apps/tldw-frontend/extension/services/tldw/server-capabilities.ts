import { tldwClient } from "./TldwApiClient"

export type ServerCapabilities = {
  hasChat: boolean
  hasRag: boolean
  hasMedia: boolean
  hasNotes: boolean
  hasPrompts: boolean
  hasFlashcards: boolean
  hasQuizzes: boolean
  hasCharacters: boolean
  hasWorldBooks: boolean
  hasChatDictionaries: boolean
  hasChatKnowledgeSave: boolean
  hasChatDocuments: boolean
  hasChatbooks: boolean
  hasChatQueue: boolean
  hasChatSaveToDb: boolean
  hasAudio: boolean
  hasEmbeddings: boolean
  hasMetrics: boolean
  hasMcp: boolean
  hasReading: boolean
  hasWebSearch: boolean
  hasFeedbackExplicit: boolean
  hasFeedbackImplicit: boolean
  specVersion: string | null
}

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null

const defaultCapabilities: ServerCapabilities = {
  hasChat: false,
  hasRag: false,
  hasMedia: false,
  hasNotes: false,
  hasPrompts: false,
  hasFlashcards: false,
  hasQuizzes: false,
  hasCharacters: false,
  hasWorldBooks: false,
  hasChatDictionaries: false,
  hasChatKnowledgeSave: false,
  hasChatDocuments: false,
  hasChatbooks: false,
  hasChatQueue: false,
  hasChatSaveToDb: false,
  hasAudio: false,
  hasEmbeddings: false,
  hasMetrics: false,
  hasMcp: false,
  hasReading: false,
  hasWebSearch: false,
  hasFeedbackExplicit: false,
  hasFeedbackImplicit: false,
  specVersion: null
}

const fallbackSpec = {
  info: { version: "local-fallback" },
  paths: Object.fromEntries(
    [
      "/api/v1/chat/completions",
      "/api/v1/feedback/explicit",
      "/api/v1/rag/search",
      "/api/v1/rag/health",
      "/api/v1/rag/",
      "/api/v1/rag/feedback/implicit",
      "/api/v1/media/add",
      "/api/v1/media/",
      "/api/v1/media/process-videos",
      "/api/v1/media/process-documents",
      "/api/v1/media/process-pdfs",
      "/api/v1/media/process-ebooks",
      "/api/v1/media/process-audios",
      "/api/v1/notes/",
      "/api/v1/prompts",
      "/api/v1/flashcards",
      "/api/v1/flashcards/decks",
      "/api/v1/quizzes",
      "/api/v1/quizzes/generate",
      "/api/v1/characters",
      "/api/v1/characters/world-books",
      "/api/v1/chat/dictionaries",
      "/api/v1/chat/dictionaries/validate",
      "/api/v1/chat/dictionaries/process",
      "/api/v1/chat/knowledge/save",
      "/api/v1/chat/documents",
      "/api/v1/chat/documents/generate",
      "/api/v1/chat/documents/bulk",
      "/api/v1/chat/documents/jobs",
      "/api/v1/chat/documents/prompts",
      "/api/v1/chat/documents/statistics",
      "/api/v1/chat/queue/status",
      "/api/v1/chat/queue/activity",
      "/api/v1/chatbooks/export",
      "/api/v1/chatbooks/preview",
      "/api/v1/chatbooks/import",
      "/api/v1/chatbooks/export/jobs",
      "/api/v1/chatbooks/import/jobs",
      "/api/v1/chatbooks/download",
      "/api/v1/chatbooks/cleanup",
      "/api/v1/chatbooks/health",
      "/api/v1/audio/transcriptions",
      "/api/v1/audio/speech",
      "/api/v1/audio/health",
      "/api/v1/embeddings/models",
      "/api/v1/embeddings/providers-config",
      "/api/v1/embeddings/health",
      "/api/v1/metrics/health",
      "/api/v1/metrics",
      "/api/v1/mcp/health",
      "/api/v1/reading/save",
      "/api/v1/reading/items",
      "/api/v1/research/websearch"
    ].map((p) => [p, {}])
  )
}

const normalizePaths = (raw: unknown): Record<string, unknown> => {
  const out: Record<string, unknown> = {}
  if (!isRecord(raw)) return out
  for (const key of Object.keys(raw)) {
    const k = key.trim()
    out[k] = raw[key]
    if (k.endsWith("/")) {
      out[k.slice(0, -1)] = raw[key]
    } else {
      out[`${k}/`] = raw[key]
    }
  }
  return out
}

const resolveSchemaRef = (schema: unknown, spec: unknown): unknown => {
  if (!isRecord(schema)) return schema
  const ref = schema.$ref
  if (typeof ref !== "string") return schema
  const prefix = "#/components/schemas/"
  if (!ref.startsWith(prefix)) return schema
  const name = ref.slice(prefix.length)
  if (!isRecord(spec)) return schema
  const components = isRecord(spec.components) ? spec.components : null
  const schemas = components && isRecord(components.schemas) ? components.schemas : null
  const resolved = schemas ? schemas[name] : null
  return resolved ?? schema
}

const schemaHasProperty = (
  schema: unknown,
  property: string,
  spec: unknown,
  seen: Set<string> = new Set()
): boolean => {
  if (!isRecord(schema)) return false
  const ref = typeof schema.$ref === "string" ? schema.$ref : null
  if (ref) {
    if (seen.has(ref)) return false
    seen.add(ref)
    return schemaHasProperty(resolveSchemaRef(schema, spec), property, spec, seen)
  }
  if (isRecord(schema.properties) && schema.properties[property]) return true

  const combos = [
    ...(Array.isArray(schema.allOf) ? schema.allOf : []),
    ...(Array.isArray(schema.anyOf) ? schema.anyOf : []),
    ...(Array.isArray(schema.oneOf) ? schema.oneOf : [])
  ]
  for (const entry of combos) {
    if (schemaHasProperty(entry, property, spec, seen)) return true
  }
  return false
}

const detectChatSaveToDb = (spec: unknown): boolean => {
  if (!isRecord(spec)) return false
  const paths = isRecord(spec.paths) ? spec.paths : {}
  const chatPath = isRecord(paths["/api/v1/chat/completions"])
    ? paths["/api/v1/chat/completions"]
    : {}
  const post = isRecord(chatPath.post) ? chatPath.post : {}
  const requestBody = isRecord(post.requestBody) ? post.requestBody : {}
  const content = isRecord(requestBody.content) ? requestBody.content : {}
  const jsonSchema =
    (isRecord(content["application/json"]) ? content["application/json"] : null) ??
    (isRecord(content["application/json;charset=utf-8"])
      ? content["application/json;charset=utf-8"]
      : null)
  const schema = isRecord(jsonSchema) ? jsonSchema.schema : null
  return schemaHasProperty(schema, "save_to_db", spec)
}

const computeCapabilities = (spec: unknown): ServerCapabilities => {
  if (!isRecord(spec)) return { ...defaultCapabilities }
  const paths = normalizePaths(spec.paths || {})
  const has = (p: string) => Boolean(paths[p])
  const hasChatSaveToDb = detectChatSaveToDb(spec)
  const specInfo = isRecord(spec.info) ? spec.info : {}
  const specVersion =
    typeof specInfo.version === "string" ? specInfo.version : null

  return {
    hasChat: has("/api/v1/chat/completions"),
    hasRag: has("/api/v1/rag/search") || has("/api/v1/rag/health") || has("/api/v1/rag/"),
    hasMedia:
      has("/api/v1/media/add") ||
      has("/api/v1/media/") ||
      has("/api/v1/media/process-videos") ||
      has("/api/v1/media/process-documents"),
    hasNotes: has("/api/v1/notes/"),
    hasPrompts: has("/api/v1/prompts") || has("/api/v1/prompts/"),
    hasFlashcards:
      has("/api/v1/flashcards") ||
      has("/api/v1/flashcards/") ||
      has("/api/v1/flashcards/decks"),
    hasQuizzes:
      has("/api/v1/quizzes") ||
      has("/api/v1/quizzes/") ||
      has("/api/v1/quizzes/generate"),
    hasCharacters: has("/api/v1/characters") || has("/api/v1/characters/"),
    hasWorldBooks: has("/api/v1/characters/world-books"),
    hasChatDictionaries: has("/api/v1/chat/dictionaries"),
    hasChatKnowledgeSave: has("/api/v1/chat/knowledge/save"),
    hasChatDocuments: has("/api/v1/chat/documents") || has("/api/v1/chat/documents/generate"),
    hasChatbooks: has("/api/v1/chatbooks/export") || has("/api/v1/chatbooks/health"),
    hasChatQueue: has("/api/v1/chat/queue/status") || has("/api/v1/chat/queue/activity"),
    hasChatSaveToDb,
    hasAudio:
      has("/api/v1/audio/speech") ||
      has("/api/v1/audio/transcriptions") ||
      has("/api/v1/audio/health"),
    hasEmbeddings:
      has("/api/v1/embeddings/models") ||
      has("/api/v1/embeddings/providers-config") ||
      has("/api/v1/embeddings/health"),
    hasMetrics: has("/api/v1/metrics/health") || has("/api/v1/metrics"),
    hasMcp: has("/api/v1/mcp/health"),
    hasReading: has("/api/v1/reading/save") && has("/api/v1/reading/items"),
    hasWebSearch: has("/api/v1/research/websearch"),
    hasFeedbackExplicit: has("/api/v1/feedback/explicit"),
    hasFeedbackImplicit: has("/api/v1/rag/feedback/implicit"),
    specVersion
  }
}

let capabilitiesPromise: Promise<ServerCapabilities> | null = null

export const getServerCapabilities = async (): Promise<ServerCapabilities> => {
  if (!capabilitiesPromise) {
    capabilitiesPromise = (async () => {
      let spec: unknown = null
      try {
        const healthy = await tldwClient.healthCheck()
        if (healthy) {
          spec = await tldwClient.getOpenAPISpec()
        }
      } catch {
        // ignore, fall back to bundled spec
      }
      if (!spec) {
        spec = fallbackSpec
      }
      return computeCapabilities(spec)
    })()
  }
  return capabilitiesPromise
}
