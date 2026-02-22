import { apiSend } from "@/services/api-send"
import { appendPathQuery, toAllowedPath } from "@/services/tldw/path-utils"

export type PromptSearchField =
  | "name"
  | "author"
  | "details"
  | "system_prompt"
  | "user_prompt"
  | "keywords"

export type PromptSearchItem = {
  id: number
  uuid: string
  name: string
  author?: string | null
  details?: string | null
  system_prompt?: string | null
  user_prompt?: string | null
  last_modified?: string
  version?: number
  usage_count?: number
  last_used_at?: string | null
  keywords?: string[]
  deleted?: boolean
  relevance_score?: number | null
}

export type PromptSearchResponse = {
  items: PromptSearchItem[]
  total_matches: number
  page: number
  per_page: number
}

export type SearchPromptsParams = {
  searchQuery: string
  searchFields?: PromptSearchField[]
  page?: number
  resultsPerPage?: number
  includeDeleted?: boolean
}

export type PromptExportFormat = "csv" | "markdown"
export type PromptExportResponse = {
  message: string
  file_path?: string | null
  file_content_b64?: string | null
}

export type PromptCollection = {
  collection_id: number
  name: string
  description?: string | null
  prompt_ids: number[]
}

export type PromptCollectionListResponse = {
  collections: PromptCollection[]
}

export type PromptCollectionCreatePayload = {
  name: string
  description?: string | null
  prompt_ids?: number[]
}

export type PromptCollectionCreateResponse = {
  collection_id: number
}

export type PromptCollectionUpdatePayload = {
  name?: string
  description?: string | null
  prompt_ids?: number[]
}

export const buildPromptSearchQuery = ({
  searchQuery,
  searchFields = [],
  page = 1,
  resultsPerPage = 20,
  includeDeleted = false
}: SearchPromptsParams): string => {
  const qs = new URLSearchParams()
  qs.set("search_query", searchQuery)
  qs.set("page", String(page))
  qs.set("results_per_page", String(resultsPerPage))
  qs.set("include_deleted", includeDeleted ? "true" : "false")

  for (const field of searchFields) {
    qs.append("search_fields", field)
  }

  return `?${qs.toString()}`
}

export async function searchPromptsServer(
  params: SearchPromptsParams
): Promise<PromptSearchResponse> {
  const query = buildPromptSearchQuery(params)
  const response = await apiSend<PromptSearchResponse>({
    path: appendPathQuery(toAllowedPath("/api/v1/prompts/search"), query),
    method: "POST"
  })

  if (!response.ok) {
    throw new Error(response.error || "Failed to search prompts")
  }

  return (
    response.data || {
      items: [],
      total_matches: 0,
      page: params.page || 1,
      per_page: params.resultsPerPage || 20
    }
  )
}

export const buildPromptExportQuery = (format: PromptExportFormat): string => {
  const qs = new URLSearchParams()
  qs.set("export_format", format)
  return `?${qs.toString()}`
}

export async function exportPromptsServer(
  format: PromptExportFormat
): Promise<PromptExportResponse> {
  const response = await apiSend<PromptExportResponse>({
    path: appendPathQuery(
      toAllowedPath("/api/v1/prompts/export"),
      buildPromptExportQuery(format)
    ),
    method: "GET"
  })

  if (!response.ok) {
    throw new Error(response.error || "Failed to export prompts")
  }

  return (
    response.data || {
      message: ""
    }
  )
}

export async function listPromptCollectionsServer(): Promise<PromptCollection[]> {
  const response = await apiSend<PromptCollectionListResponse>({
    path: toAllowedPath("/api/v1/prompts/collections"),
    method: "GET"
  })

  if (!response.ok) {
    throw new Error(response.error || "Failed to load prompt collections")
  }

  return response.data?.collections || []
}

export async function createPromptCollectionServer(
  payload: PromptCollectionCreatePayload
): Promise<PromptCollectionCreateResponse> {
  const response = await apiSend<PromptCollectionCreateResponse>({
    path: toAllowedPath("/api/v1/prompts/collections/create"),
    method: "POST",
    body: payload
  })

  if (!response.ok || !response.data) {
    throw new Error(response.error || "Failed to create prompt collection")
  }

  return response.data
}

export async function updatePromptCollectionServer(
  collectionId: number,
  payload: PromptCollectionUpdatePayload
): Promise<PromptCollection> {
  const response = await apiSend<PromptCollection>({
    path: toAllowedPath(`/api/v1/prompts/collections/${collectionId}`),
    method: "PUT",
    body: payload
  })

  if (!response.ok || !response.data) {
    throw new Error(response.error || "Failed to update prompt collection")
  }

  return response.data
}
