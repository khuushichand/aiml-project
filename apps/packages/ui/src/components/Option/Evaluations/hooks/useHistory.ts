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

// Helper to ensure API responses are ok
const ensureOk = <T,>(resp: any): T => {
  if (!resp?.ok) {
    const err = new Error(resp?.error || `HTTP ${resp?.status}`)
    ;(err as any).resp = resp
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
      ensureOk<{
        data: {
          total_count: number
          items?: EvaluationHistoryItem[]
        }
      }>(
        await getHistory(filters)
      ),
    onSuccess: (resp) => {
      const list =
        resp?.data?.items ||
        (Array.isArray(resp?.data) ? resp?.data : (resp?.data as any)?.data) ||
        []
      const totalCount = resp?.data?.total_count
      setHistoryResults(list as EvaluationHistoryItem[], typeof totalCount === "number" ? totalCount : undefined)
    },
    onError: (error: any) => {
      notification.error({
        message: t("evaluations:historyErrorTitle", {
          defaultValue: "Failed to fetch history"
        }),
        description: error?.message
      })
    }
  })
}

// History filter presets
export const historyTypePresets = [
  { value: "model_graded", label: "model_graded" },
  { value: "rag", label: "rag" },
  { value: "response_quality", label: "response_quality" },
  { value: "proposition_extraction", label: "proposition_extraction" },
  { value: "ocr", label: "ocr" }
]
