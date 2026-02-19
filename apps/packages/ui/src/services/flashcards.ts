import { bgRequest, bgUpload } from "@/services/background-proxy"
import type { AllowedPath } from "@/services/tldw/openapi-guard"
import {
  buildQuery,
  createResourceClient
} from "@/services/resource-client"

const decksClient = createResourceClient({
  basePath: "/api/v1/flashcards/decks" as AllowedPath
})

const flashcardsClient = createResourceClient({
  basePath: "/api/v1/flashcards" as AllowedPath
})

// Minimal client types based on openapi.json
export type Deck = {
  id: number
  name: string
  description?: string | null
  deleted: boolean
  client_id: string
  version: number
  created_at?: string | null
  last_modified?: string | null
}

export type Flashcard = {
  uuid: string
  deck_id?: number | null
  front: string
  back: string
  notes?: string | null
  extra?: string | null
  is_cloze: boolean
  tags?: string[] | null
  ef: number
  interval_days: number
  repetitions: number
  lapses: number
  due_at?: string | null
  created_at?: string | null
  last_reviewed_at?: string | null
  last_modified?: string | null
  deleted: boolean
  client_id: string
  version: number
  model_type: "basic" | "basic_reverse" | "cloze"
  reverse: boolean
  source_ref_type?: "media" | "message" | "note" | "manual" | null
  source_ref_id?: string | null
  conversation_id?: string | null
  message_id?: string | null
}

export type FlashcardCreate = {
  deck_id?: number | null
  front: string
  back: string
  notes?: string | null
  extra?: string | null
  is_cloze?: boolean | null
  tags?: string[] | null
  source_ref_type?: "media" | "message" | "note" | "manual" | null
  source_ref_id?: string | null
  model_type?: Flashcard["model_type"] | null
  reverse?: boolean | null
}

export type FlashcardUpdate = {
  deck_id?: number | null
  front?: string | null
  back?: string | null
  notes?: string | null
  extra?: string | null
  is_cloze?: boolean | null
  tags?: string[] | null
  expected_version?: number | null
  model_type?: Flashcard["model_type"] | null
  reverse?: boolean | null
}

export type FlashcardResetSchedulingRequest = {
  expected_version: number
}

export type FlashcardListResponse = {
  items: Flashcard[]
  count: number
  total?: number | null
}

export type FlashcardReviewRequest = {
  card_uuid: string
  rating: number // 0-5
  answer_time_ms?: number | null
}

export type FlashcardGeneratedDraft = {
  front: string
  back: string
  tags?: string[] | null
  model_type?: "basic" | "basic_reverse" | "cloze"
  notes?: string | null
  extra?: string | null
}

export type FlashcardsGenerateRequest = {
  text: string
  num_cards?: number
  card_type?: "basic" | "basic_reverse" | "cloze"
  difficulty?: "easy" | "medium" | "hard" | "mixed"
  focus_topics?: string[] | null
  provider?: string | null
  model?: string | null
}

export type FlashcardsGenerateResponse = {
  flashcards: FlashcardGeneratedDraft[]
  count: number
}

export type FlashcardReviewResponse = {
  uuid: string
  ef: number
  interval_days: number
  repetitions: number
  lapses: number
  due_at?: string | null
  last_reviewed_at?: string | null
  last_modified?: string | null
  version: number
}

export type FlashcardsImportRequest = {
  content: string
  delimiter?: string | null
  has_header?: boolean | null
}

export type FlashcardsImportJsonRequest = {
  content: string
  filename?: string | null
}

export type FlashcardsImportApkgRequest = {
  bytes: Uint8Array
  filename?: string | null
}

export type FlashcardsImportError = {
  line?: number | null
  index?: number | null
  error: string
}

export type FlashcardsImportResponse = {
  imported: number
  items: Array<{
    uuid: string
    deck_id: number
  }>
  errors: FlashcardsImportError[]
}

export type FlashcardsExportParams = {
  deck_id?: number | null
  tag?: string | null
  q?: string | null
  format?: "csv" | "apkg" | null
  include_reverse?: boolean | null
  delimiter?: string | null
  include_header?: boolean | null
  extended_header?: boolean | null
}

export type FlashcardDeckProgress = {
  deck_id: number
  deck_name: string
  total: number
  new: number
  learning: number
  due: number
  mature: number
}

export type FlashcardAnalyticsSummary = {
  reviewed_today: number
  retention_rate_today?: number | null
  lapse_rate_today?: number | null
  avg_answer_time_ms_today?: number | null
  study_streak_days: number
  generated_at: string
  decks: FlashcardDeckProgress[]
}

// Decks
export async function listDecks(options?: { signal?: AbortSignal }): Promise<Deck[]> {
  return await decksClient.list<Deck[]>(undefined, {
    abortSignal: options?.signal
  })
}

export async function createDeck(
  input: { name: string; description?: string | null },
  options?: { signal?: AbortSignal }
): Promise<Deck> {
  return await decksClient.create<Deck>(input, {
    abortSignal: options?.signal
  })
}

// Flashcards CRUD
export async function listFlashcards(params: {
  deck_id?: number | null
  tag?: string | null
  due_status?: "new" | "learning" | "due" | "all" | null
  q?: string | null
  limit?: number
  offset?: number
  order_by?: "due_at" | "created_at" | null
}): Promise<FlashcardListResponse> {
  return await flashcardsClient.list<FlashcardListResponse>({
    deck_id: params.deck_id,
    tag: params.tag,
    due_status: params.due_status,
    q: params.q,
    limit: params.limit,
    offset: params.offset,
    order_by: params.order_by
  })
}

export async function createFlashcard(
  input: FlashcardCreate,
  options?: { signal?: AbortSignal }
): Promise<Flashcard> {
  return await flashcardsClient.create<Flashcard>(input, {
    abortSignal: options?.signal
  })
}

export async function getFlashcard(card_uuid: string): Promise<Flashcard> {
  return await flashcardsClient.get<Flashcard>(card_uuid)
}

export async function updateFlashcard(card_uuid: string, input: FlashcardUpdate): Promise<void> {
  await flashcardsClient.update<void>(card_uuid, input)
}

export async function deleteFlashcard(card_uuid: string, expected_version: number): Promise<void> {
  await flashcardsClient.remove<void>(card_uuid, {
    expected_version
  })
}

export async function resetFlashcardScheduling(
  card_uuid: string,
  input: FlashcardResetSchedulingRequest
): Promise<Flashcard> {
  return await bgRequest<Flashcard, AllowedPath, "POST">({
    path: `/api/v1/flashcards/${card_uuid}/reset-scheduling` as AllowedPath,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

// Review
export async function reviewFlashcard(input: FlashcardReviewRequest): Promise<FlashcardReviewResponse> {
  return await bgRequest<FlashcardReviewResponse, AllowedPath, "POST">({
    path: "/api/v1/flashcards/review",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

export async function generateFlashcards(
  input: FlashcardsGenerateRequest
): Promise<FlashcardsGenerateResponse> {
  return await bgRequest<FlashcardsGenerateResponse, AllowedPath, "POST">({
    path: "/api/v1/flashcards/generate",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

// Import
export async function getFlashcardsImportLimits(): Promise<any> {
  return await bgRequest<any, AllowedPath, "GET">({
    path: "/api/v1/config/flashcards-import-limits",
    method: "GET"
  })
}

export async function importFlashcards(payload: FlashcardsImportRequest, overrides?: {
  max_lines?: number | null
  max_line_length?: number | null
  max_field_length?: number | null
}): Promise<FlashcardsImportResponse> {
  const query = buildQuery({
    max_lines: overrides?.max_lines,
    max_line_length: overrides?.max_line_length,
    max_field_length: overrides?.max_field_length
  })
  const path = `/api/v1/flashcards/import${query}` as AllowedPath
  return await bgRequest<FlashcardsImportResponse, AllowedPath, "POST">({
    path,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export async function importFlashcardsJson(
  payload: FlashcardsImportJsonRequest,
  overrides?: {
    max_items?: number | null
    max_field_length?: number | null
  }
): Promise<FlashcardsImportResponse> {
  const query = buildQuery({
    max_items: overrides?.max_items,
    max_field_length: overrides?.max_field_length
  })
  const path = `/api/v1/flashcards/import/json${query}` as AllowedPath
  const filename = (payload.filename || "flashcards.json").trim() || "flashcards.json"
  const lowerName = filename.toLowerCase()
  const mimeType =
    lowerName.endsWith(".jsonl") || lowerName.endsWith(".ndjson")
      ? "application/x-ndjson"
      : "application/json"
  const bytes = new TextEncoder().encode(payload.content)

  return await bgUpload<FlashcardsImportResponse, AllowedPath, "POST">({
    path,
    method: "POST",
    fileFieldName: "file",
    file: {
      name: filename,
      type: mimeType,
      data: bytes
    }
  })
}

export async function importFlashcardsApkg(
  payload: FlashcardsImportApkgRequest,
  overrides?: {
    max_items?: number | null
    max_field_length?: number | null
  }
): Promise<FlashcardsImportResponse> {
  const query = buildQuery({
    max_items: overrides?.max_items,
    max_field_length: overrides?.max_field_length
  })
  const path = `/api/v1/flashcards/import/apkg${query}` as AllowedPath
  const filename = (payload.filename || "flashcards.apkg").trim() || "flashcards.apkg"

  return await bgUpload<FlashcardsImportResponse, AllowedPath, "POST">({
    path,
    method: "POST",
    fileFieldName: "file",
    file: {
      name: filename,
      type: "application/apkg",
      data: payload.bytes
    }
  })
}

export async function getFlashcardsAnalyticsSummary(params?: {
  deck_id?: number | null
  signal?: AbortSignal
}): Promise<FlashcardAnalyticsSummary> {
  const query = buildQuery({
    deck_id: params?.deck_id
  })
  const path = `/api/v1/flashcards/analytics/summary${query}` as AllowedPath
  return await bgRequest<FlashcardAnalyticsSummary, AllowedPath, "GET">({
    path,
    method: "GET",
    abortSignal: params?.signal
  })
}

// Export (returns text/csv or file-like payload)
export async function exportFlashcards(params: FlashcardsExportParams = {}): Promise<string> {
  const query = buildQuery({
    deck_id: params.deck_id,
    tag: params.tag,
    q: params.q,
    format: params.format,
    include_reverse: params.include_reverse,
    delimiter: params.delimiter,
    include_header: params.include_header,
    extended_header: params.extended_header
  })
  const path = `/api/v1/flashcards/export${query}` as AllowedPath
  // Force accept text so bgRequest returns text
  return await bgRequest<string, AllowedPath, "GET">({
    path,
    method: "GET",
    headers: { Accept: "text/plain, text/csv, application/octet-stream, application/json;q=0.5" }
  })
}

// Export binary (APKG). Uses direct fetch to preserve binary payload.
export async function exportFlashcardsFile(params: FlashcardsExportParams & { format: 'apkg' }): Promise<Blob> {
  const query = buildQuery({
    deck_id: params.deck_id,
    tag: params.tag,
    q: params.q,
    format: "apkg",
    include_reverse: params.include_reverse,
    // CSV specific options ignored for apkg on server side, but safe to pass
    delimiter: params.delimiter,
    include_header: params.include_header,
    extended_header: params.extended_header
  })
  const path = `/api/v1/flashcards/export${query}` as AllowedPath
  const response = await bgRequest<{
    ok: boolean
    status: number
    data?: ArrayBuffer
    error?: string
    headers?: Record<string, string>
  }>({
    path,
    method: "GET",
    headers: { Accept: "application/octet-stream" },
    responseType: "arrayBuffer",
    returnResponse: true
  })
  if (!response) {
    throw new Error("Export failed")
  }
  if (!response.ok) {
    throw new Error(response.error || `Export failed: ${response.status}`)
  }
  const headers = new Headers(response.headers || {})
  return new Blob([response.data ?? new Uint8Array()], {
    type: headers.get("content-type") || "application/octet-stream"
  })
}
