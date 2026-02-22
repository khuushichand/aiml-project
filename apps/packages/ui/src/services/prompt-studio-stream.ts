import type { TldwConfig } from "@/services/tldw/TldwApiClient"

export const buildPromptStudioWebSocketUrl = (
  config: Pick<TldwConfig, "serverUrl" | "authMode" | "apiKey" | "accessToken">,
  projectId?: number | null
): string => {
  const serverUrl = String(config.serverUrl || "").trim()
  if (!serverUrl) {
    throw new Error("tldw server is not configured")
  }

  const base = serverUrl.replace(/^http/i, "ws").replace(/\/$/, "")
  const params = new URLSearchParams()

  if (config.authMode === "multi-user") {
    const token = String(config.accessToken || "").trim()
    if (!token) {
      throw new Error("Not authenticated. Please log in under Settings.")
    }
    params.set("token", token)
  } else {
    const apiKey = String(config.apiKey || "").trim()
    if (!apiKey) {
      throw new Error("API key missing. Update Settings -> tldw server.")
    }
    params.set("api_key", apiKey)
  }

  if (typeof projectId === "number" && Number.isFinite(projectId)) {
    params.set("project_id", String(projectId))
  }

  return `${base}/api/v1/prompt-studio/ws?${params.toString()}`
}

const STATUS_EVENT_TYPES = new Set([
  "job_created",
  "job_started",
  "job_progress",
  "job_completed",
  "job_failed",
  "job_cancelled",
  "job_retrying",
  "evaluation_started",
  "evaluation_progress",
  "evaluation_completed",
  "optimization_started",
  "optimization_iteration",
  "optimization_completed",
  "subscribed",
  "job_update"
])

export const isPromptStudioStatusEvent = (payload: unknown): boolean => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return false
  const type = (payload as Record<string, unknown>).type
  return typeof type === "string" && STATUS_EVENT_TYPES.has(type)
}
