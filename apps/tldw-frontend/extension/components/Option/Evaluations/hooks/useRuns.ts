/**
 * useRuns hook
 * Handles evaluation run operations and queries
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  cancelRun,
  createRun,
  createSpecializedEvaluation,
  getRateLimits,
  getRun,
  listRuns,
  listRunsGlobal,
  type CreateRunPayload
} from "@/services/evaluations"
import { useEvaluationsStore } from "@/store/evaluations"
import { metricsFromResults } from "../utils/metricsFormatter"

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

// Parse rate limit snapshot from response headers
export const parseQuotaSnapshot = (
  headers?: Record<string, unknown> | null
): {
  limitDay?: number
  remainingDay?: number
  limitMinute?: number
  remainingMinute?: number
  reset?: string | null
} | null => {
  if (!headers) return null
  const h: Record<string, string> = {}
  for (const [k, v] of Object.entries(headers)) {
    h[k.toLowerCase()] = String(v)
  }
  const num = (s?: string | null) => {
    if (s == null) return undefined
    const n = Number(s)
    return Number.isFinite(n) ? n : undefined
  }
  const snapshot = {
    limitDay: num(h["x-ratelimit-limit-day"] || h["x-ratelimit-day-limit"]),
    remainingDay: num(
      h["x-ratelimit-remaining-day"] || h["x-ratelimit-day-remaining"]
    ),
    limitMinute: num(
      h["x-ratelimit-limit-minute"] || h["x-ratelimit-minute-limit"]
    ),
    remainingMinute: num(
      h["x-ratelimit-remaining-minute"] || h["x-ratelimit-minute-remaining"]
    ),
    reset: h["x-ratelimit-reset"] || h["x-ratelimit-reset-at"] || null
  }
  const hasData = Object.values(snapshot).some(
    (v) => v !== undefined && v !== null
  )
  return hasData ? snapshot : null
}

// Extract metrics summary from run results
export const extractMetricsSummary = (
  results: unknown
): { key: string; value: number }[] => {
  return metricsFromResults(results, 20)
}

export function useRateLimits() {
  return useQuery({
    queryKey: ["evaluations", "rate-limits"],
    queryFn: () => getRateLimits()
  })
}

export function useRunsList(evalId: string | null, params?: { limit?: number }) {
  return useQuery({
    queryKey: ["evaluations", "runs", evalId, params || { limit: 20 }],
    queryFn: () => listRuns(evalId as string, params || { limit: 20 }),
    enabled: !!evalId
  })
}

export function useRunsListGlobal(params?: {
  limit?: number
  eval_id?: string
  status?: string
}) {
  return useQuery({
    queryKey: ["evaluations", "runs", "global", params],
    queryFn: () => listRunsGlobal(params)
  })
}

export function useRunDetail(
  runId: string | null,
  options?: { enablePolling?: boolean; captureQuota?: boolean }
) {
  const setQuotaSnapshot = useEvaluationsStore((s) => s.setQuotaSnapshot)
  const setIsPolling = useEvaluationsStore((s) => s.setIsPolling)
  const enablePolling = options?.enablePolling !== false
  const captureQuota = options?.captureQuota !== false

  return useQuery({
    queryKey: ["evaluations", "run", runId],
    queryFn: async () => {
      const resp = await getRun(runId as string)
      // Parse quota from headers
      if (captureQuota) {
        const headers =
          isRecord(resp) && isRecord(resp.headers) ? resp.headers : null
        const snapshot = parseQuotaSnapshot(headers)
        if (snapshot) setQuotaSnapshot(snapshot)
      }
      return resp
    },
    enabled: !!runId,
    refetchInterval: enablePolling
      ? (query) => {
        const queryData = query?.state?.data
        const dataRecord =
          isRecord(queryData) && isRecord(queryData.data)
            ? queryData.data
            : undefined
        const status = dataRecord?.status
        if (!status) {
          if (enablePolling) {
            setIsPolling(false)
          }
          return false
        }
        const isPolling = ["running", "pending"].includes(
          String(status).toLowerCase()
        )
        if (enablePolling) {
          setIsPolling(isPolling)
        }
        return isPolling ? 3000 : false
      }
      : false
  })
}

export function useCreateRun() {
  const { t } = useTranslation(["evaluations", "common"])
  const queryClient = useQueryClient()
  const notification = useAntdNotification()
  const selectedEvalId = useEvaluationsStore((s) => s.selectedEvalId)
  const setSelectedRunId = useEvaluationsStore((s) => s.setSelectedRunId)
  const setQuotaSnapshot = useEvaluationsStore((s) => s.setQuotaSnapshot)

  return useMutation({
    mutationFn: async (params: {
      evalId: string
      payload: CreateRunPayload
      idempotencyKey?: string
    }) =>
      ensureOk(
        await createRun(params.evalId, params.payload, {
          idempotencyKey: params.idempotencyKey
        })
      ),
    onSuccess: (resp: unknown) => {
      const record = isRecord(resp) ? resp : {}
      const data = isRecord(record.data) ? record.data : {}
      const runId = data.id ?? data.run_id
      const snapshot = parseQuotaSnapshot(
        isRecord(record.headers) ? record.headers : null
      )
      if (snapshot) setQuotaSnapshot(snapshot)
      if (runId) {
        setSelectedRunId(String(runId))
        void queryClient.invalidateQueries({
          queryKey: ["evaluations", "runs", selectedEvalId]
        })
      }
      notification.success({
        message: t("evaluations:runCreateSuccessTitle", {
          defaultValue: "Run started"
        }),
        description: t("evaluations:runCreateSuccessDescription", {
          defaultValue:
            "Your evaluation run has started. You can monitor it from the server UI."
        })
      })
    },
    onError: (error: unknown) => {
      const retryAfter =
        isRecord(error) &&
        isRecord(error.resp) &&
        typeof error.resp.retryAfterMs === "number"
          ? error.resp.retryAfterMs
          : null
      notification.error({
        message: t("evaluations:runCreateErrorTitle", {
          defaultValue: "Failed to start run"
        }),
        description:
          (error instanceof Error ? error.message : null) ||
          t("evaluations:runCreateErrorDescription", {
            defaultValue:
              "The server rejected this run request. Check the model and try again."
          }) +
            (retryAfter
              ? ` — retry after ${Math.ceil(Number(retryAfter) / 1000)}s`
              : "")
      })
    }
  })
}

export function useCancelRun() {
  const { t } = useTranslation(["evaluations", "common"])
  const queryClient = useQueryClient()
  const notification = useAntdNotification()
  const selectedEvalId = useEvaluationsStore((s) => s.selectedEvalId)
  const selectedRunId = useEvaluationsStore((s) => s.selectedRunId)

  return useMutation({
    mutationFn: async (runId: string) => ensureOk(await cancelRun(runId)),
    onSuccess: () => {
      notification.success({
        message: t("evaluations:runCancelSuccessTitle", {
          defaultValue: "Run cancellation requested"
        })
      })
      if (selectedEvalId) {
        void queryClient.invalidateQueries({
          queryKey: ["evaluations", "runs", selectedEvalId]
        })
      }
      if (selectedRunId) {
        void queryClient.invalidateQueries({
          queryKey: ["evaluations", "run", selectedRunId]
        })
      }
    },
    onError: (error: unknown) => {
      notification.error({
        message: t("evaluations:runCancelErrorTitle", {
          defaultValue: "Failed to cancel run"
        }),
        description: error instanceof Error ? error.message : undefined
      })
    }
  })
}

export function useAdhocEvaluation() {
  const { t } = useTranslation(["evaluations", "common"])
  const notification = useAntdNotification()
  const setAdhocResult = useEvaluationsStore((s) => s.setAdhocResult)

  return useMutation({
    mutationFn: async (payload: { endpoint: string; body: unknown }) =>
      ensureOk(
        await createSpecializedEvaluation(payload.endpoint, payload.body)
      ),
    onSuccess: (resp: unknown) => {
      if (isRecord(resp) && "data" in resp) {
        setAdhocResult(resp.data)
      } else {
        setAdhocResult(resp)
      }
      notification.success({
        message: t("evaluations:runCreateSuccessTitle", {
          defaultValue: "Run started"
        }),
        description: t("evaluations:runCreateSuccessDescription", {
          defaultValue:
            "Your evaluation run has started. You can monitor it from the server UI."
        })
      })
    },
    onError: (error: unknown) => {
      notification.error({
        message: t("evaluations:createErrorTitle", {
          defaultValue: "Failed to create evaluation"
        }),
        description: error instanceof Error ? error.message : undefined
      })
    }
  })
}

// Adhoc endpoint options
export const adhocEndpointOptions = [
  { value: "response-quality", label: "response-quality" },
  { value: "rag", label: "rag" },
  { value: "geval", label: "geval" },
  { value: "propositions", label: "propositions" },
  { value: "ocr", label: "ocr" },
  { value: "ocr-pdf", label: "ocr-pdf" },
  { value: "batch", label: "batch" }
]
