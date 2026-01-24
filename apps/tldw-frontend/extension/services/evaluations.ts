import { apiSend } from "@/services/api-send"
import type { PathOrUrl } from "@/services/tldw/openapi-guard"

type UnknownRecord = Record<string, unknown>

// Lightweight client for the Evaluations module.
// Shapes are intentionally loose for now; we can tighten them
// using OpenAPI-derived types later if needed.

export type EvaluationSummary = {
  id: string
  name?: string
  description?: string
  eval_type?: string
  created?: number
  created_at?: string | number | null
  dataset_id?: string | null
  metadata?: UnknownRecord | null
}

export type EvaluationDetail = EvaluationSummary & {
  eval_spec?: UnknownRecord
  updated_at?: string | number | null
  deleted?: boolean
}

export type EvaluationRunSummary = {
  id: string
  status?: string
  created_at?: string
  completed_at?: string | null
}

export type EvaluationListResponse = {
  object?: "list"
  data: EvaluationSummary[]
  has_more?: boolean
  first_id?: string | null
  last_id?: string | null
}

export type DatasetSample = {
  input: unknown
  expected?: unknown
  metadata?: UnknownRecord
}

export type DatasetResponse = {
  id: string
  object?: string
  name: string
  description?: string | null
  sample_count: number
  created: number
  created_at?: number | null
  created_by: string
  metadata?: UnknownRecord | null
  samples?: DatasetSample[]
}

export type DatasetListResponse = {
  object?: "list"
  data: DatasetResponse[]
  has_more?: boolean
  first_id?: string | null
  last_id?: string | null
  total?: number | null
}

export type EvaluationRateLimitStatus = {
  tier: string
  limits: {
    evaluations_per_minute: number
    evaluations_per_day: number
    tokens_per_day: number
    cost_per_day: number
    cost_per_month: number
  }
  usage: {
    evaluations_today: number
    tokens_today: number
    cost_today: number
    cost_month: number
  }
  remaining: {
    daily_evaluations: number
    daily_tokens: number
    daily_cost: number
    monthly_cost: number
  }
  reset_at: string
}

export type EvaluationRunDetail = {
  id: string
  eval_id: string
  status: string
  target_model: string
  created: number
  created_at?: number | null
  started_at?: number | null
  completed_at?: number | null
  progress?: UnknownRecord | null
  error_message?: string | null
  results?: UnknownRecord | null
  usage?: UnknownRecord | null
}

export type CreateEvaluationPayload = {
  name: string
  description?: string
  eval_type: string
  eval_spec: UnknownRecord
  dataset_id?: string
  dataset?: DatasetSample[]
  metadata?: UnknownRecord
}

export type CreateRunPayload = {
  target_model: string
  config?: UnknownRecord
  dataset_override?: { samples: DatasetSample[] }
  webhook_url?: string
}

export type EvaluationHistoryFilters = {
  user_id?: string
  type?: string
  start_date?: string
  end_date?: string
}

export type EvaluationHistoryItem = {
  id: string
  user_id?: string
  type?: string
  created_at?: string
  eval_id?: string
  run_id?: string
  detail?: UnknownRecord
}

export type EvaluationWebhook = {
  id: string
  url: string
  events: string[]
  created_at?: string
  secret?: string
  is_active?: boolean
}

const withIdempotency = (
  key?: string | null
): Record<string, string> | undefined => {
  if (!key) return undefined
  return { "Idempotency-Key": key }
}

export async function listEvaluations(params?: {
  limit?: number
  after?: string
  eval_type?: string
}) {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  if (params?.after) query.set("after", params.after)
  if (params?.eval_type) query.set("eval_type", params.eval_type)

  const path =
    "/api/v1/evaluations" + (query.toString() ? `?${query.toString()}` : "")

  return await apiSend<EvaluationListResponse>({
    path: path as PathOrUrl,
    method: "GET"
  })
}

export async function getEvaluation(evalId: string) {
  return await apiSend<EvaluationDetail>({
    path: `/api/v1/evaluations/${encodeURIComponent(evalId)}` as PathOrUrl,
    method: "GET"
  })
}

export async function updateEvaluation(
  evalId: string,
  payload: Partial<CreateEvaluationPayload>
) {
  return await apiSend<EvaluationDetail>({
    path: `/api/v1/evaluations/${encodeURIComponent(evalId)}` as PathOrUrl,
    method: "PATCH",
    body: payload
  })
}

export async function deleteEvaluation(evalId: string) {
  return await apiSend<void>({
    path: `/api/v1/evaluations/${encodeURIComponent(evalId)}` as PathOrUrl,
    method: "DELETE"
  })
}

export async function listRuns(evalId: string, params?: { limit?: number }) {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  const path =
    `/api/v1/evaluations/${encodeURIComponent(evalId)}/runs` +
    (query.toString() ? `?${query.toString()}` : "")

  return await apiSend<{
    object?: "list"
    data: EvaluationRunSummary[]
    has_more?: boolean
    first_id?: string | null
    last_id?: string | null
  }>({
    path: path as PathOrUrl,
    method: "GET"
  })
}

export async function listRunsGlobal(params?: {
  limit?: number
  eval_id?: string
  status?: string
}) {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  if (params?.eval_id) query.set("eval_id", params.eval_id)
  if (params?.status) query.set("status", params.status)
  const path =
    "/api/v1/evaluations/runs" +
    (query.toString() ? `?${query.toString()}` : "")

  return await apiSend<{
    object?: "list"
    data: EvaluationRunSummary[]
    has_more?: boolean
    first_id?: string | null
    last_id?: string | null
  }>({
    path: path as PathOrUrl,
    method: "GET"
  })
}

export async function cancelRun(runId: string) {
  return await apiSend({
    path: `/api/v1/evaluations/runs/${encodeURIComponent(runId)}/cancel` as PathOrUrl,
    method: "POST"
  })
}

export async function getRateLimits() {
  return await apiSend<EvaluationRateLimitStatus>({
    path: "/api/v1/evaluations/rate-limits" as PathOrUrl,
    method: "GET"
  })
}

export async function listDatasets(params?: {
  limit?: number
  offset?: number
}) {
  const query = new URLSearchParams()
  if (params?.limit != null) query.set("limit", String(params.limit))
  if (params?.offset != null) query.set("offset", String(params.offset))

  const path =
    "/api/v1/evaluations/datasets" +
    (query.toString() ? `?${query.toString()}` : "")

  return await apiSend<DatasetListResponse>({
    path: path as PathOrUrl,
    method: "GET"
  })
}

export async function getDataset(
  datasetId: string,
  params?: { limit?: number; offset?: number; include_samples?: boolean }
) {
  const search = new URLSearchParams()
  if (params?.limit != null) search.set("limit", String(params.limit))
  if (params?.offset != null) search.set("offset", String(params.offset))
  if (params?.include_samples) search.set("include_samples", "true")
  const path =
    `/api/v1/evaluations/datasets/${encodeURIComponent(datasetId)}` +
    (search.toString() ? `?${search.toString()}` : "")

  return await apiSend<DatasetResponse>({
    path: path as PathOrUrl,
    method: "GET"
  })
}

export async function createDataset(payload: {
  name: string
  description?: string
  samples: DatasetSample[]
  metadata?: UnknownRecord
}) {
  return await apiSend<DatasetResponse>({
    path: "/api/v1/evaluations/datasets" as PathOrUrl,
    method: "POST",
    body: payload
  })
}

export async function deleteDataset(datasetId: string) {
  return await apiSend<void>({
    path: `/api/v1/evaluations/datasets/${encodeURIComponent(
      datasetId
    )}` as PathOrUrl,
    method: "DELETE"
  })
}

export async function createEvaluation(
  payload: CreateEvaluationPayload,
  options?: { idempotencyKey?: string }
) {
  return await apiSend({
    path: "/api/v1/evaluations" as PathOrUrl,
    method: "POST",
    headers: withIdempotency(options?.idempotencyKey),
    body: payload
  })
}

export async function createSpecializedEvaluation(
  endpoint:
    | "geval"
    | "rag"
    | "response-quality"
    | "propositions"
    | "ocr"
    | "ocr-pdf"
    | "batch"
    | "embeddings"
    | "embeddings-ab"
    | "embeddings-batch"
    | string,
  payload: UnknownRecord,
  options?: { idempotencyKey?: string }
) {
  return await apiSend({
    path: `/api/v1/evaluations/${endpoint}` as PathOrUrl,
    method: "POST",
    headers: withIdempotency(options?.idempotencyKey),
    body: payload
  })
}

export async function createRun(
  evalId: string,
  payload: CreateRunPayload,
  options?: { idempotencyKey?: string }
) {
  return await apiSend({
    path: `/api/v1/evaluations/${encodeURIComponent(evalId)}/runs` as PathOrUrl,
    method: "POST",
    headers: withIdempotency(options?.idempotencyKey),
    body: payload
  })
}

export async function getRun(runId: string) {
  return await apiSend<EvaluationRunDetail>({
    path: `/api/v1/evaluations/runs/${encodeURIComponent(runId)}` as PathOrUrl,
    method: "GET"
  })
}

export async function getHistory(filters?: EvaluationHistoryFilters) {
  return await apiSend<{ data?: EvaluationHistoryItem[] }>({
    path: "/api/v1/evaluations/history" as PathOrUrl,
    method: "POST",
    body: filters || {}
  })
}

export async function registerWebhook(payload: {
  url: string
  events: string[]
}) {
  return await apiSend<EvaluationWebhook>({
    path: "/api/v1/evaluations/webhooks" as PathOrUrl,
    method: "POST",
    body: payload
  })
}

export async function listWebhooks() {
  return await apiSend<{ data?: EvaluationWebhook[] }>({
    path: "/api/v1/evaluations/webhooks" as PathOrUrl,
    method: "GET"
  })
}

export async function deleteWebhook(webhookId: string) {
  return await apiSend<void>({
    path: `/api/v1/evaluations/webhooks/${encodeURIComponent(
      webhookId
    )}` as PathOrUrl,
    method: "DELETE"
  })
}
