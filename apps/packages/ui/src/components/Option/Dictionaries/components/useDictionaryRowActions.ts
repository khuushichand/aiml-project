import React from "react"
import { useMutation } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { buildDictionaryDeletionConfirmationCopy } from "../listUtils"
import { getActiveFocusableElement } from "./focusUtils"
import { useDictionaryExportActions } from "./useDictionaryExportActions"

type UseDictionaryRowActionsParams = {
  notification: {
    error: (config: { message: string; description?: string }) => void
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  setStatsFor: React.Dispatch<React.SetStateAction<any | null>>
  statsDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  setVersionHistoryFor: React.Dispatch<React.SetStateAction<any | null>>
  versionHistoryDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

type UseDictionaryRowActionsResult = {
  exportDictionaryAsJson: (record: any) => Promise<void>
  exportDictionaryAsMarkdown: (record: any) => Promise<void>
  openDictionaryStatsModal: (record: any) => Promise<void>
  openDictionaryVersionHistoryModal: (record: any) => Promise<void>
  confirmAndDeleteDictionary: (record: any) => Promise<void>
}

export function useDictionaryRowActions({
  notification,
  confirmDanger,
  t,
  queryClient,
  setStatsFor,
  statsDialogFocusReturnRef,
  setVersionHistoryFor,
  versionHistoryDialogFocusReturnRef,
}: UseDictionaryRowActionsParams): UseDictionaryRowActionsResult {
  const { mutate: deleteDict } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteDictionary(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
    },
  })

  const { exportDictionaryAsJson, exportDictionaryAsMarkdown } =
    useDictionaryExportActions({
      notification,
      confirmDanger,
      t,
    })

  const openDictionaryStatsModal = React.useCallback(
    async (record: any) => {
      statsDialogFocusReturnRef.current = getActiveFocusableElement()
      try {
        const [stats, activity] = await Promise.all([
          tldwClient.dictionaryStatistics(record.id),
          tldwClient.dictionaryActivity(record.id, { limit: 10, offset: 0 }).catch(() => null),
        ])
        setStatsFor({
          ...stats,
          default_token_budget:
            stats?.default_token_budget ?? record?.default_token_budget ?? null,
          recent_activity: Array.isArray(activity?.events) ? activity.events : [],
          recent_activity_total: Number(activity?.total || 0),
        })
      } catch (error: any) {
        statsDialogFocusReturnRef.current = null
        notification.error({ message: "Stats failed", description: error?.message })
      }
    },
    [notification, setStatsFor, statsDialogFocusReturnRef]
  )

  const confirmAndDeleteDictionary = React.useCallback(
    async (record: any) => {
      const confirmationCopy = buildDictionaryDeletionConfirmationCopy(record)
      const ok = await confirmDanger({
        title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
        content: confirmationCopy,
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" }),
      })
      if (ok) deleteDict(record.id)
    },
    [confirmDanger, deleteDict, t]
  )

  const openDictionaryVersionHistoryModal = React.useCallback(
    async (record: any) => {
      versionHistoryDialogFocusReturnRef.current = getActiveFocusableElement()
      setVersionHistoryFor(record)
    },
    [setVersionHistoryFor, versionHistoryDialogFocusReturnRef]
  )

  return {
    exportDictionaryAsJson,
    exportDictionaryAsMarkdown,
    openDictionaryStatsModal,
    openDictionaryVersionHistoryModal,
    confirmAndDeleteDictionary,
  }
}
