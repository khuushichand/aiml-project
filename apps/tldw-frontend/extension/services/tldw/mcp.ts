import { bgRequestClient } from "@/services/background-proxy"

export type McpToolTier = "read" | "write" | "exec" | string

export type McpToolDefinition = {
  name?: string
  description?: string | null
  parameters?: Record<string, unknown>
  input_schema?: Record<string, unknown>
  json_schema?: Record<string, unknown>
  tier?: McpToolTier
  [key: string]: unknown
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

export const fetchMcpTools = async (): Promise<McpToolDefinition[]> => {
  try {
    const res = await bgRequestClient<unknown>({
      path: "/api/v1/mcp/tools",
      method: "GET"
    })
    if (!res) return []
    if (Array.isArray(res)) return res as McpToolDefinition[]
    if (isRecord(res)) {
      if (Array.isArray(res.tools)) return res.tools as McpToolDefinition[]
      if (Array.isArray(res.data)) return res.data as McpToolDefinition[]
    }
    return []
  } catch {
    return []
  }
}

export const executeMcpTool = async (
  payload: Record<string, unknown>
): Promise<Record<string, unknown>> => {
  return await bgRequestClient<Record<string, unknown>>({
    path: "/api/v1/mcp/tools/execute",
    method: "POST",
    body: payload
  })
}
