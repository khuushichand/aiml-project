import { bgRequest } from "@/services/background-proxy"
import { tldwClient } from "./TldwApiClient"

export type LlamaGrammarRecord = {
  id: string
  name: string
  description?: string | null
  grammar_text: string
  validation_status?: "unchecked" | "valid" | "invalid"
  validation_error?: string | null
  last_validated_at?: string | null
  is_archived?: boolean
  created_at?: string | null
  updated_at?: string | null
  version?: number
}

export type LlamaGrammarListResponse = {
  items: LlamaGrammarRecord[]
  total: number
  limit: number
  offset: number
}

export type CreateLlamaGrammarInput = {
  name: string
  description?: string
  grammar_text: string
}

export type UpdateLlamaGrammarInput = Partial<CreateLlamaGrammarInput> & {
  version?: number
}

export class TldwLlamaGrammarsService {
  async list(params?: {
    include_archived?: boolean
    limit?: number
    offset?: number
  }): Promise<LlamaGrammarListResponse> {
    await tldwClient.initialize().catch(() => null)
    const qs = new URLSearchParams()
    if (params?.include_archived) qs.set("include_archived", "true")
    if (typeof params?.limit === "number") qs.set("limit", String(params.limit))
    if (typeof params?.offset === "number") qs.set("offset", String(params.offset))
    const query = qs.toString()
    return await bgRequest<LlamaGrammarListResponse>({
      path: `/api/v1/chat/grammars${query ? `?${query}` : ""}`,
      method: "GET"
    })
  }

  async create(input: CreateLlamaGrammarInput): Promise<LlamaGrammarRecord> {
    await tldwClient.initialize().catch(() => null)
    return await bgRequest<LlamaGrammarRecord>({
      path: "/api/v1/chat/grammars",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: input
    })
  }

  async update(id: string, input: UpdateLlamaGrammarInput): Promise<LlamaGrammarRecord> {
    await tldwClient.initialize().catch(() => null)
    return await bgRequest<LlamaGrammarRecord>({
      path: `/api/v1/chat/grammars/${encodeURIComponent(id)}`,
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: input
    })
  }

  async remove(id: string, params?: {
    hard_delete?: boolean
  }): Promise<void> {
    await tldwClient.initialize().catch(() => null)
    const query = params?.hard_delete ? "?hard_delete=true" : ""
    await bgRequest({
      path: `/api/v1/chat/grammars/${encodeURIComponent(id)}${query}`,
      method: "DELETE"
    })
  }
}

export const tldwLlamaGrammars = new TldwLlamaGrammarsService()
