import React from "react"
import { useMutation } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { buildRestorableDictionaryEntryPayload } from "./dictionaryEntryUtils"

type BulkEntryOperation = "activate" | "deactivate" | "delete" | "group"

type UseDictionaryEntryRowOperationsParams = {
  dictionaryId: number
  entries: any[]
  allEntries: any[]
  allEntriesById: Map<number, any>
  filteredEntryIds: number[]
  orderedEntryIds: number[]
  canReorderEntries: boolean
  entriesQueryKey: readonly unknown[]
  allEntriesQueryKey: readonly unknown[]
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  notification: {
    warning: (config: { message: string; description?: string }) => void
    success: (config: { message: string; description?: string }) => void
    error: (config: { message: string; description?: string }) => void
  }
  queryClient: {
    setQueryData: (
      queryKey: readonly unknown[],
      updater: (current: unknown) => unknown
    ) => void
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  showUndoNotification: (config: {
    title: string
    description: string
    duration: number
    onUndo: () => Promise<void>
    onDismiss: () => void
  }) => void
  t: (key: string, options?: Record<string, unknown>) => string
}

type UseDictionaryEntryRowOperationsResult = {
  selectedEntryRowKeys: React.Key[]
  setSelectedEntryRowKeys: React.Dispatch<React.SetStateAction<React.Key[]>>
  selectedEntryIds: number[]
  canEscalateSelectAllFilteredEntries: boolean
  bulkGroupName: string
  setBulkGroupName: React.Dispatch<React.SetStateAction<string>>
  bulkEntryAction: BulkEntryOperation | null
  reorderBusyEntryId: number | null
  handleSelectAllFilteredEntries: () => void
  handleBulkEntryAction: (operation: BulkEntryOperation) => Promise<void>
  handleMoveEntry: (entryId: number, direction: -1 | 1) => Promise<void>
  handleDeleteEntryWithUndo: (entryRecord: any) => Promise<void>
}

export function useDictionaryEntryRowOperations({
  dictionaryId,
  entries,
  allEntries,
  allEntriesById,
  filteredEntryIds,
  orderedEntryIds,
  canReorderEntries,
  entriesQueryKey,
  allEntriesQueryKey,
  confirmDanger,
  notification,
  queryClient,
  showUndoNotification,
  t,
}: UseDictionaryEntryRowOperationsParams): UseDictionaryEntryRowOperationsResult {
  const [selectedEntryRowKeys, setSelectedEntryRowKeys] = React.useState<React.Key[]>([])
  const [bulkGroupName, setBulkGroupName] = React.useState("")
  const [bulkEntryAction, setBulkEntryAction] = React.useState<BulkEntryOperation | null>(null)
  const [reorderBusyEntryId, setReorderBusyEntryId] = React.useState<number | null>(null)
  const { mutateAsync: deleteEntry } = useMutation({
    mutationFn: (entryId: number) => tldwClient.deleteDictionaryEntry(entryId),
  })

  const selectedEntryIds = React.useMemo(
    () =>
      selectedEntryRowKeys
        .map((entryId) => Number(entryId))
        .filter((entryId) => Number.isFinite(entryId) && entryId > 0),
    [selectedEntryRowKeys]
  )
  const canEscalateSelectAllFilteredEntries =
    selectedEntryIds.length > 0 &&
    selectedEntryIds.length < filteredEntryIds.length

  React.useEffect(() => {
    setSelectedEntryRowKeys((currentSelection) => {
      const filteredSelection = currentSelection.filter((entryId) =>
        allEntriesById.has(Number(entryId))
      )
      if (
        filteredSelection.length === currentSelection.length &&
        filteredSelection.every((entryId, index) => entryId === currentSelection[index])
      ) {
        return currentSelection
      }
      return filteredSelection
    })
  }, [allEntriesById])

  React.useEffect(() => {
    setSelectedEntryRowKeys([])
    setBulkGroupName("")
    setReorderBusyEntryId(null)
  }, [dictionaryId])

  const handleSelectAllFilteredEntries = React.useCallback(() => {
    setSelectedEntryRowKeys(filteredEntryIds)
  }, [filteredEntryIds])

  const handleBulkEntryAction = React.useCallback(
    async (operation: BulkEntryOperation) => {
      if (selectedEntryIds.length === 0) return

      const trimmedGroupName = bulkGroupName.trim()
      if (operation === "group" && !trimmedGroupName) {
        notification.warning({
          message: "Group name required",
          description: "Provide a group name before running bulk set group.",
        })
        return
      }

      if (operation === "delete") {
        const ok = await confirmDanger({
          title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
          content: `Delete ${selectedEntryIds.length} selected entries?`,
          okText: t("common:delete", { defaultValue: "Delete" }),
          cancelText: t("common:cancel", { defaultValue: "Cancel" }),
        })
        if (!ok) return
      }

      setBulkEntryAction(operation)
      try {
        const payload: {
          entry_ids: number[]
          operation: BulkEntryOperation
          group_name?: string
        } = {
          entry_ids: selectedEntryIds,
          operation,
        }
        if (operation === "group") {
          payload.group_name = trimmedGroupName
        }

        const result = await tldwClient.bulkDictionaryEntries(payload)
        const failedIds = Array.isArray(result?.failed_ids)
          ? result.failed_ids
              .map((entryId: unknown) => Number(entryId))
              .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0)
          : []
        const affectedCount =
          typeof result?.affected_count === "number"
            ? result.affected_count
            : selectedEntryIds.length - failedIds.length

        if (failedIds.length > 0) {
          notification.warning({
            message: "Bulk action completed with errors",
            description:
              result?.message ||
              `${affectedCount} entries updated, ${failedIds.length} failed.`,
          })
          setSelectedEntryRowKeys(failedIds)
        } else {
          notification.success({
            message: "Bulk action complete",
            description:
              result?.message || `${affectedCount} entries updated successfully.`,
          })
          setSelectedEntryRowKeys([])
          if (operation === "group") {
            setBulkGroupName("")
          }
        }

        await queryClient.invalidateQueries({
          queryKey: ["tldw:listDictionaryEntries", dictionaryId],
        })
        await queryClient.invalidateQueries({ queryKey: allEntriesQueryKey })
      } catch (error: any) {
        notification.error({
          message: "Bulk action failed",
          description: error?.message || "Unable to complete bulk action.",
        })
      } finally {
        setBulkEntryAction(null)
      }
    },
    [
      allEntriesQueryKey,
      bulkGroupName,
      confirmDanger,
      dictionaryId,
      notification,
      queryClient,
      selectedEntryIds,
      t,
    ]
  )

  const persistEntryOrder = React.useCallback(
    async (nextOrderedEntryIds: number[], changedEntryId?: number) => {
      if (nextOrderedEntryIds.length <= 1) return
      if (nextOrderedEntryIds.length !== orderedEntryIds.length) {
        notification.error({
          message: "Reorder failed",
          description: "Current filter hides entries. Clear filters and retry.",
        })
        return
      }
      const isSameOrder =
        nextOrderedEntryIds.length === orderedEntryIds.length &&
        nextOrderedEntryIds.every(
          (entryId, index) => entryId === orderedEntryIds[index]
        )
      if (isSameOrder) return

      setReorderBusyEntryId(changedEntryId ?? -1)
      try {
        await tldwClient.reorderDictionaryEntries(dictionaryId, {
          entry_ids: nextOrderedEntryIds,
        })
        await queryClient.invalidateQueries({
          queryKey: ["tldw:listDictionaryEntries", dictionaryId],
        })
        await queryClient.invalidateQueries({ queryKey: allEntriesQueryKey })
      } catch (error: any) {
        notification.error({
          message: "Reorder failed",
          description:
            error?.message || "Unable to persist entry priority. Please retry.",
        })
      } finally {
        setReorderBusyEntryId(null)
      }
    },
    [allEntriesQueryKey, dictionaryId, notification, orderedEntryIds, queryClient]
  )

  const handleMoveEntry = React.useCallback(
    async (entryId: number, direction: -1 | 1) => {
      if (!canReorderEntries || reorderBusyEntryId != null) return
      const currentIndex = orderedEntryIds.findIndex((id) => id === entryId)
      if (currentIndex < 0) return
      const nextIndex = currentIndex + direction
      if (nextIndex < 0 || nextIndex >= orderedEntryIds.length) return

      const nextOrder = [...orderedEntryIds]
      ;[nextOrder[currentIndex], nextOrder[nextIndex]] = [
        nextOrder[nextIndex],
        nextOrder[currentIndex],
      ]
      await persistEntryOrder(nextOrder, entryId)
    },
    [canReorderEntries, orderedEntryIds, persistEntryOrder, reorderBusyEntryId]
  )

  const handleDeleteEntryWithUndo = React.useCallback(
    async (entryRecord: any) => {
      const ok = await confirmDanger({
        title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
        content: "Delete entry?",
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" }),
      })
      if (!ok) return

      const entryId = Number(entryRecord?.id)
      if (!Number.isFinite(entryId) || entryId <= 0) {
        notification.error({
          message: "Delete failed",
          description: "Entry ID is invalid. Please refresh and retry.",
        })
        return
      }

      const entrySnapshot = { ...entryRecord }
      const previousEntries = Array.isArray(entries) ? [...entries] : []

      queryClient.setQueryData(entriesQueryKey, (current: unknown) => {
        const currentEntries = Array.isArray(current) ? current : previousEntries
        return currentEntries.filter((entry: any) => Number(entry?.id) !== entryId)
      })
      queryClient.setQueryData(allEntriesQueryKey, (current: unknown) => {
        const currentEntries = Array.isArray(current) ? current : allEntries
        return currentEntries.filter((entry: any) => Number(entry?.id) !== entryId)
      })

      try {
        await deleteEntry(entryId)
        const previewPattern = String(entrySnapshot?.pattern || "Entry")
        showUndoNotification({
          title: "Entry deleted",
          description: `"${previewPattern}" was removed. Undo to restore it.`,
          duration: 10,
          onUndo: async () => {
            const payload = buildRestorableDictionaryEntryPayload(entrySnapshot)
            const restored = await tldwClient.addDictionaryEntry(dictionaryId, payload)
            queryClient.setQueryData(entriesQueryKey, (current: unknown) => {
              const currentEntries = Array.isArray(current) ? current : []
              return [...currentEntries, restored || { ...entrySnapshot, ...payload }]
            })
            queryClient.setQueryData(allEntriesQueryKey, (current: unknown) => {
              const currentEntries = Array.isArray(current) ? current : []
              return [...currentEntries, restored || { ...entrySnapshot, ...payload }]
            })
            await queryClient.invalidateQueries({
              queryKey: ["tldw:listDictionaryEntries", dictionaryId],
            })
            await queryClient.invalidateQueries({ queryKey: allEntriesQueryKey })
          },
          onDismiss: () => {
            void queryClient.invalidateQueries({
              queryKey: ["tldw:listDictionaryEntries", dictionaryId],
            })
            void queryClient.invalidateQueries({ queryKey: allEntriesQueryKey })
          },
        })
      } catch (deleteError: any) {
        queryClient.setQueryData(entriesQueryKey, () => previousEntries)
        queryClient.setQueryData(allEntriesQueryKey, () => allEntries)
        notification.error({
          message: "Delete failed",
          description:
            (deleteError?.message
              ? `${deleteError.message}.`
              : "Failed to delete entry.") + " Please retry.",
        })
      }
    },
    [
      allEntries,
      allEntriesQueryKey,
      confirmDanger,
      deleteEntry,
      dictionaryId,
      entries,
      entriesQueryKey,
      notification,
      queryClient,
      showUndoNotification,
      t,
    ]
  )

  return {
    selectedEntryRowKeys,
    setSelectedEntryRowKeys,
    selectedEntryIds,
    canEscalateSelectAllFilteredEntries,
    bulkGroupName,
    setBulkGroupName,
    bulkEntryAction,
    reorderBusyEntryId,
    handleSelectAllFilteredEntries,
    handleBulkEntryAction,
    handleMoveEntry,
    handleDeleteEntryWithUndo,
  }
}
