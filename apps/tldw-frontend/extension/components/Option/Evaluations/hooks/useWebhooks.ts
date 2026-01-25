/**
 * useWebhooks hook
 * Handles webhook CRUD operations and queries
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  deleteWebhook,
  listWebhooks,
  registerWebhook,
  type EvaluationWebhook
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

export function useWebhooksList(enabled = true) {
  return useQuery({
    queryKey: ["evaluations", "webhooks"],
    queryFn: () => listWebhooks(),
    enabled
  })
}

export function useRegisterWebhook() {
  const { t } = useTranslation(["evaluations", "common"])
  const queryClient = useQueryClient()
  const notification = useAntdNotification()
  const setWebhookSecretText = useEvaluationsStore((s) => s.setWebhookSecretText)

  return useMutation({
    mutationFn: async (payload: { url: string; events: string[] }) =>
      ensureOk<{ data: EvaluationWebhook }>(await registerWebhook(payload)),
    onSuccess: (resp) => {
      const secret =
        isRecord(resp) && isRecord(resp.data) && typeof resp.data.secret === "string"
          ? resp.data.secret
          : null
      setWebhookSecretText(secret)
      void queryClient.invalidateQueries({
        queryKey: ["evaluations", "webhooks"]
      })
      notification.success({
        message: t("evaluations:webhookCreateSuccessTitle", {
          defaultValue: "Webhook registered"
        })
      })
    },
    onError: (error: unknown) => {
      notification.error({
        message: t("evaluations:webhookCreateErrorTitle", {
          defaultValue: "Failed to register webhook"
        }),
        description: error instanceof Error ? error.message : undefined
      })
    }
  })
}

export function useDeleteWebhook() {
  const { t } = useTranslation(["evaluations", "common"])
  const queryClient = useQueryClient()
  const notification = useAntdNotification()

  return useMutation({
    mutationFn: async (webhookId: string) =>
      ensureOk(await deleteWebhook(webhookId)),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["evaluations", "webhooks"]
      })
      notification.success({
        message: t("common:deleted", { defaultValue: "Deleted" })
      })
    },
    onError: (error: unknown) => {
      notification.error({
        message: t("evaluations:webhookDeleteErrorTitle", {
          defaultValue: "Failed to delete webhook"
        }),
        description: error instanceof Error ? error.message : undefined
      })
    }
  })
}

// Webhook event options
export const webhookEventOptions = [
  { value: "evaluation.started", label: "evaluation.started" },
  { value: "evaluation.completed", label: "evaluation.completed" },
  { value: "evaluation.failed", label: "evaluation.failed" },
  { value: "evaluation.cancelled", label: "evaluation.cancelled" },
  { value: "evaluation.progress", label: "evaluation.progress" }
]

// Default events when registering a new webhook
export const defaultWebhookEvents = [
  "evaluation.started",
  "evaluation.completed",
  "evaluation.failed"
]
