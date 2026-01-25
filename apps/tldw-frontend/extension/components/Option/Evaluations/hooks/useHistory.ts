/**
 * useHistory hook
 * Handles evaluation history queries
 */

import { useMutation } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  getHistory,
  type EvaluationHistoryFilters,
  type EvaluationHistoryItem
} from "@/services/evaluations"
import { useEvaluationsStore } from "@/store/evaluations"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

// Helper to ensure API responses are ok
const ensureOk = <T,>(resp: unknown): T => {
  const record = isRecord(resp) ? resp : {}
  if (record.ok !== true) {
    const status = typeof record.status === "number" ? record.status : undefined
    const message =
      typeof record.error === "string"
        ? record.error
        : status
          ? `HTTP ${status}`
          : "Request failed"
    const err = new Error(message)
    ;(err as { resp?: unknown }).resp = resp
    throw err
  }
  return resp as T
}

export function useFetchHistory() {
  const { t } = useTranslation(["evaluations", "common"])
  const notification = useAntdNotification()
  const setHistoryResults = useEvaluationsStore((s) => s.setHistoryResults)

  return useMutation({
    mutationFn: async (filters: EvaluationHistoryFilters) =>
      ensureOk<{ data: { data?: EvaluationHistoryItem[] } }>(
        await getHistory(filters)
      ),
    onSuccess: (resp) => {
      const data = isRecord(resp) ? resp.data : undefined
      const list =
        (isRecord(data) && Array.isArray(data.data) && data.data) ||
        (Array.isArray(data) && data) ||
        (isRecord(data) && Array.isArray(data.items) && data.items) ||
        []
      setHistoryResults(list as EvaluationHistoryItem[])
    },
    onError: (error: unknown) => {
      notification.error({
        message: t("evaluations:historyErrorTitle", {
          defaultValue: "Failed to fetch history"
        }),
        description: error instanceof Error ? error.message : undefined
      })
    }
  })
}

// History filter presets
export const historyTypePresets = [
  { value: "evaluation.created", label: "evaluation.created" },
  { value: "evaluation.started", label: "evaluation.started" },
  { value: "evaluation.completed", label: "evaluation.completed" },
  { value: "evaluation.failed", label: "evaluation.failed" },
  { value: "evaluation.cancelled", label: "evaluation.cancelled" },
  { value: "run.created", label: "run.created" },
  { value: "run.started", label: "run.started" },
  { value: "run.completed", label: "run.completed" },
  { value: "run.failed", label: "run.failed" }
]
