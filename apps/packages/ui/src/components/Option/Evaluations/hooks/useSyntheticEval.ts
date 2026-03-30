/**
 * useSyntheticEval hook
 * Shared review-queue queries and mutations for synthetic eval drafts.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  listSyntheticEvalQueue,
  promoteSyntheticEvalSamples,
  reviewSyntheticEvalSample
} from "@/services/evaluations"

const ensureOk = <T,>(resp: any): T => {
  if (!resp?.ok) {
    const err = new Error(resp?.error || `HTTP ${resp?.status}`)
    ;(err as any).resp = resp
    throw err
  }
  return resp as T
}

export function useSyntheticEvalQueue(params: {
  recipeKind?: string | null
  reviewState?: string | null
  sourceKind?: string | null
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: [
      "evaluations",
      "synthetic",
      "queue",
      params.recipeKind || null,
      params.reviewState || null,
      params.sourceKind || null,
      params.limit || 50,
      params.offset || 0
    ],
    queryFn: async () =>
      ensureOk(
        await listSyntheticEvalQueue({
          recipe_kind: params.recipeKind || undefined,
          review_state: params.reviewState || undefined,
          source_kind: params.sourceKind || undefined,
          limit: params.limit,
          offset: params.offset
        })
      )
  })
}

export function useReviewSyntheticEvalSample() {
  const queryClient = useQueryClient()
  const { t } = useTranslation(["evaluations", "common"])
  const notification = useAntdNotification()

  return useMutation({
    mutationFn: async (params: {
      sampleId: string
      action: string
      reviewer_id?: string
      notes?: string
      action_payload?: Record<string, any>
      resulting_review_state?: string
    }) =>
      ensureOk(
        await reviewSyntheticEvalSample(params.sampleId, {
          action: params.action,
          reviewer_id: params.reviewer_id,
          notes: params.notes,
          action_payload: params.action_payload,
          resulting_review_state: params.resulting_review_state
        })
      ),
    onSuccess: () => {
      notification.success({
        message: t("evaluations:syntheticReviewActionSuccessTitle", {
          defaultValue: "Review updated"
        })
      })
      void queryClient.invalidateQueries({
        queryKey: ["evaluations", "synthetic", "queue"]
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("evaluations:syntheticReviewActionErrorTitle", {
          defaultValue: "Failed to update review"
        }),
        description: error?.message
      })
    }
  })
}

export function usePromoteSyntheticEvalSamples() {
  const queryClient = useQueryClient()
  const { t } = useTranslation(["evaluations", "common"])
  const notification = useAntdNotification()

  return useMutation({
    mutationFn: async (params: {
      sample_ids: string[]
      dataset_name: string
      dataset_description?: string
      dataset_metadata?: Record<string, any>
      promoted_by?: string
      promotion_reason?: string
    }) =>
      ensureOk(
        await promoteSyntheticEvalSamples(params)
      ),
    onSuccess: () => {
      notification.success({
        message: t("evaluations:syntheticPromoteSuccessTitle", {
          defaultValue: "Synthetic dataset promoted"
        })
      })
      void queryClient.invalidateQueries({
        queryKey: ["evaluations", "synthetic", "queue"]
      })
      void queryClient.invalidateQueries({
        queryKey: ["evaluations", "datasets"]
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("evaluations:syntheticPromoteErrorTitle", {
          defaultValue: "Failed to promote synthetic dataset"
        }),
        description: error?.message
      })
    }
  })
}
