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

export type DeckSchedulerSettings = {
  new_steps_minutes: number[]
  relearn_steps_minutes: number[]
  graduating_interval_days: number
  easy_interval_days: number
  easy_bonus: number
  interval_modifier: number
  max_interval_days: number
  leech_threshold: number
  enable_fuzz: boolean
}

export type DeckSchedulerType = "sm2_plus" | "fsrs"

export type FsrsSchedulerSettings = {
  target_retention: number
  maximum_interval_days: number
  enable_fuzz: boolean
}

export type DeckSchedulerSettingsEnvelope = {
  sm2_plus: DeckSchedulerSettings
  fsrs: FsrsSchedulerSettings
}

export type DeckSchedulerSettingsEnvelopeUpdate = {
  sm2_plus?: Partial<DeckSchedulerSettings>
  fsrs?: Partial<FsrsSchedulerSettings>
}

export type FlashcardIntervalPreviews = {
  again: string
  hard: string
  good: string
  easy: string
}

export type StudyAssistantAction =
  | "explain"
  | "mnemonic"
  | "follow_up"
  | "fact_check"
  | "freeform"

export type StudyAssistantInputModality = "text" | "voice_transcript"

export type StudyAssistantThreadSummary = {
  id: number
  context_type: "flashcard" | "quiz_attempt_question"
  flashcard_uuid?: string | null
  quiz_attempt_id?: number | null
  question_id?: number | null
  last_message_at?: string | null
  message_count: number
  deleted: boolean
  client_id: string
  version: number
  created_at?: string | null
  last_modified?: string | null
}

export type StudyAssistantMessage = {
  id: number
  thread_id: number
  role: "user" | "assistant"
  action_type: StudyAssistantAction
  input_modality: StudyAssistantInputModality
  content: string
  structured_payload: Record<string, unknown>
  context_snapshot: Record<string, unknown>
  provider?: string | null
  model?: string | null
  created_at?: string | null
  client_id: string
}

export type StudyAssistantFactCheckPayload = {
  verdict: "correct" | "partially_correct" | "incorrect"
  corrections: string[]
  missing_points: string[]
  next_prompt: string
}

export type StudyAssistantRespondRequest = {
  action: StudyAssistantAction
  message?: string | null
  input_modality?: StudyAssistantInputModality
  provider?: string | null
  model?: string | null
  expected_thread_version?: number | null
}

export type StudyAssistantContextResponse = {
  thread: StudyAssistantThreadSummary
  messages: StudyAssistantMessage[]
  context_snapshot: Record<string, unknown>
  available_actions: StudyAssistantAction[]
}

export type StudyAssistantRespondResponse = {
  thread: StudyAssistantThreadSummary
  user_message: StudyAssistantMessage
  assistant_message: StudyAssistantMessage
  structured_payload: Record<string, unknown>
  context_snapshot: Record<string, unknown>
}

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
  scheduler_type: DeckSchedulerType
  scheduler_settings_json?: string | null
  scheduler_settings: DeckSchedulerSettingsEnvelope
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
  queue_state: "new" | "learning" | "review" | "relearning" | "suspended"
  step_index?: number | null
  suspended_reason?: "manual" | "leech" | null
  last_modified?: string | null
  deleted: boolean
  client_id: string
  version: number
  model_type: "basic" | "basic_reverse" | "cloze"
  reverse: boolean
  scheduler_type?: DeckSchedulerType | null
  source_ref_type?: "media" | "message" | "note" | "manual" | null
  source_ref_id?: string | null
  conversation_id?: string | null
  message_id?: string | null
  next_intervals?: FlashcardIntervalPreviews | null
}

export type DeckUpdate = {
  name?: string | null
  description?: string | null
  scheduler_type?: DeckSchedulerType | null
  scheduler_settings?: DeckSchedulerSettingsEnvelopeUpdate | null
  expected_version?: number | null
}

export type DeckCreateInput = {
  name: string
  description?: string | null
  scheduler_type?: DeckSchedulerType | null
  scheduler_settings?: DeckSchedulerSettingsEnvelope | null
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

export type FlashcardBulkUpdateItem = FlashcardUpdate & {
  uuid: string
}

export type FlashcardBulkUpdateError = {
  code: "validation_error" | "not_found" | "conflict"
  message: string
  invalid_fields?: string[]
  invalid_deck_ids?: number[]
}

export type FlashcardBulkUpdateResult = {
  uuid: string
  status: "updated" | "validation_error" | "not_found" | "conflict"
  flashcard?: Flashcard | null
  error?: FlashcardBulkUpdateError | null
}

export type FlashcardBulkUpdateResponse = {
  results: FlashcardBulkUpdateResult[]
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
  scheduler_type: DeckSchedulerType
  queue_state: Flashcard["queue_state"]
  step_index?: number | null
  suspended_reason?: Flashcard["suspended_reason"]
  next_intervals: FlashcardIntervalPreviews
}

export type FlashcardNextReviewResponse = {
  card?: Flashcard | null
  selection_reason?: "learning_due" | "review_due" | "new" | "none" | null
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

export type StructuredQaImportPreviewRequest = {
  content: string
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

export type StructuredQaImportPreviewDraft = {
  front: string
  back: string
  line_start: number
  line_end: number
  notes?: string | null
  extra?: string | null
  tags?: string[] | null
}

export type StructuredQaImportPreviewResponse = {
  drafts: StructuredQaImportPreviewDraft[]
  errors: Array<{ line?: number | null; error: string }>
  detected_format: "qa_labels"
  skipped_blocks: number
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
  input: DeckCreateInput,
  options?: { signal?: AbortSignal }
): Promise<Deck> {
  return await decksClient.create<Deck>(input, {
    abortSignal: options?.signal
  })
}

export async function updateDeck(
  deck_id: number,
  input: DeckUpdate,
  options?: { signal?: AbortSignal }
): Promise<Deck> {
  return await decksClient.update<Deck>(String(deck_id), input, {
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

export async function createFlashcardsBulk(
  input: FlashcardCreate[]
): Promise<FlashcardListResponse> {
  return await bgRequest<FlashcardListResponse, AllowedPath, "POST">({
    path: "/api/v1/flashcards/bulk",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

export async function updateFlashcardsBulk(
  input: FlashcardBulkUpdateItem[]
): Promise<FlashcardBulkUpdateResponse> {
  return await bgRequest<FlashcardBulkUpdateResponse, AllowedPath, "PATCH">({
    path: "/api/v1/flashcards/bulk",
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: input
  })
}

export async function getFlashcard(card_uuid: string): Promise<Flashcard> {
  return await flashcardsClient.get<Flashcard>(card_uuid)
}

export async function getFlashcardAssistant(
  card_uuid: string,
  options?: { signal?: AbortSignal }
): Promise<StudyAssistantContextResponse> {
  return await bgRequest<StudyAssistantContextResponse, AllowedPath, "GET">({
    path: `/api/v1/flashcards/${card_uuid}/assistant` as AllowedPath,
    method: "GET",
    abortSignal: options?.signal
  })
}

export async function respondFlashcardAssistant(
  card_uuid: string,
  input: StudyAssistantRespondRequest,
  options?: { signal?: AbortSignal }
): Promise<StudyAssistantRespondResponse> {
  return await bgRequest<StudyAssistantRespondResponse, AllowedPath, "POST">({
    path: `/api/v1/flashcards/${card_uuid}/assistant/respond` as AllowedPath,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: input,
    abortSignal: options?.signal
  })
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

export async function getNextReviewCard(
  deck_id?: number | null
): Promise<FlashcardNextReviewResponse> {
  const query = buildQuery({
    deck_id
  })
  return await bgRequest<FlashcardNextReviewResponse, AllowedPath, "GET">({
    path: `/api/v1/flashcards/review/next${query}` as AllowedPath,
    method: "GET"
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

export async function previewStructuredQaImport(
  payload: StructuredQaImportPreviewRequest,
  overrides?: {
    max_lines?: number | null
    max_line_length?: number | null
    max_field_length?: number | null
  }
): Promise<StructuredQaImportPreviewResponse> {
  const query = buildQuery({
    max_lines: overrides?.max_lines,
    max_line_length: overrides?.max_line_length,
    max_field_length: overrides?.max_field_length
  })
  const path = `/api/v1/flashcards/import/structured/preview${query}` as AllowedPath
  return await bgRequest<StructuredQaImportPreviewResponse, AllowedPath, "POST">({
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
