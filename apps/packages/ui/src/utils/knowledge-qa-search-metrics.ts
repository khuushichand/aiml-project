import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })
const METRICS_KEY = "knowledgeQaSearchMetrics"
const MAX_RECENT_EVENTS = 100

export type KnowledgeQaSearchMetricEvent =
  | { type: "search_submit"; query_length: number }
  | { type: "search_cancel" }
  | { type: "search_clear_full" }
  | {
      type: "search_complete"
      duration_ms: number
      result_count: number
      has_answer: boolean
      used_streaming: boolean
    }
  | { type: "answer_feedback_submit"; helpful: boolean }
  | { type: "source_feedback_submit"; relevant: boolean }
  | { type: "workspace_handoff"; source_count: number }
  | {
      type: "suggestion_accept"
      source: "history" | "example" | "source_title"
    }

type RecentEvent = {
  type: KnowledgeQaSearchMetricEvent["type"]
  at: number
  details: Record<string, number | string | boolean>
}

export type KnowledgeQaSearchMetrics = {
  version: 1
  submitCount: number
  cancelCount: number
  clearFullCount: number
  completeCount: number
  totalSearchDurationMs: number
  lastSearchDurationMs: number | null
  answerFeedbackCount: number
  sourceFeedbackCount: number
  workspaceHandoffCount: number
  suggestionAcceptCount: number
  lastEventAt: number | null
  recentEvents: RecentEvent[]
}

const DEFAULT_METRICS: KnowledgeQaSearchMetrics = {
  version: 1,
  submitCount: 0,
  cancelCount: 0,
  clearFullCount: 0,
  completeCount: 0,
  totalSearchDurationMs: 0,
  lastSearchDurationMs: null,
  answerFeedbackCount: 0,
  sourceFeedbackCount: 0,
  workspaceHandoffCount: 0,
  suggestionAcceptCount: 0,
  lastEventAt: null,
  recentEvents: [],
}

const readMetrics = async (): Promise<KnowledgeQaSearchMetrics> => {
  const stored = await storage.get<KnowledgeQaSearchMetrics | undefined>(METRICS_KEY)
  if (!stored || typeof stored !== "object") {
    return DEFAULT_METRICS
  }
  return {
    ...DEFAULT_METRICS,
    ...stored,
    recentEvents: Array.isArray(stored.recentEvents)
      ? stored.recentEvents.slice(-MAX_RECENT_EVENTS)
      : [],
  }
}

const writeMetrics = async (metrics: KnowledgeQaSearchMetrics) => {
  await storage.set(METRICS_KEY, metrics)
}

export const trackKnowledgeQaSearchMetric = async (
  event: KnowledgeQaSearchMetricEvent
) => {
  try {
    const metrics = await readMetrics()
    const now = Date.now()
    metrics.lastEventAt = now

    switch (event.type) {
      case "search_submit":
        metrics.submitCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: { query_length: event.query_length },
        })
        break
      case "search_cancel":
        metrics.cancelCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: {},
        })
        break
      case "search_clear_full":
        metrics.clearFullCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: {},
        })
        break
      case "search_complete":
        metrics.completeCount += 1
        metrics.totalSearchDurationMs += Math.max(0, Math.round(event.duration_ms))
        metrics.lastSearchDurationMs = Math.max(0, Math.round(event.duration_ms))
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: {
            duration_ms: Math.max(0, Math.round(event.duration_ms)),
            result_count: Math.max(0, Math.round(event.result_count)),
            has_answer: event.has_answer,
            used_streaming: event.used_streaming,
          },
        })
        break
      case "answer_feedback_submit":
        metrics.answerFeedbackCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: { helpful: event.helpful },
        })
        break
      case "source_feedback_submit":
        metrics.sourceFeedbackCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: { relevant: event.relevant },
        })
        break
      case "workspace_handoff":
        metrics.workspaceHandoffCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: {
            source_count: Math.max(0, Math.round(event.source_count)),
          },
        })
        break
      case "suggestion_accept":
        metrics.suggestionAcceptCount += 1
        metrics.recentEvents.push({
          type: event.type,
          at: now,
          details: { source: event.source },
        })
        break
      default:
        break
    }

    if (metrics.recentEvents.length > MAX_RECENT_EVENTS) {
      metrics.recentEvents.splice(0, metrics.recentEvents.length - MAX_RECENT_EVENTS)
    }

    await writeMetrics(metrics)
  } catch (error) {
    console.warn("[knowledge-qa-search-metrics] Failed to track metric", error)
  }
}
