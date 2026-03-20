import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { QueryClient } from "@tanstack/react-query"
import type { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  characterImportQueueReducer,
  initialCharacterImportQueueState,
  shouldHandleImportUploadEvent,
  summarizeCharacterImportQueue
} from "../import-state-model"

type CharacterImportResult = {
  success: boolean
  fileName: string
  message: string
}

type CharacterImportOptions = {
  allowImageOnly?: boolean
  suppressNotifications?: boolean
  invalidateOnSuccess?: boolean
}

type CharacterImportPreview = {
  id: string
  file: File
  fileName: string
  format: string
  name: string
  description: string
  tagCount: number
  fieldCount: number
  avatarUrl: string | null
  parseError: {
    key: string
    fallback: string
    values?: Record<string, string | number>
  } | null
}

const IMPORT_IMAGE_EXTENSIONS = new Set([".png", ".webp", ".jpeg", ".jpg"])

const getImportFileExtension = (fileName: string): string => {
  const idx = fileName.lastIndexOf(".")
  return idx >= 0 ? fileName.slice(idx).toLowerCase() : ""
}

export interface UseCharacterImportQueueDeps {
  /** i18n translator */
  t: (key: string, opts?: Record<string, any>) => string
  /** Notification API */
  notification: ReturnType<typeof useAntdNotification>
  /** React Query client for cache invalidation */
  qc: QueryClient
  /** Parse a file for import preview */
  parseCharacterImportPreview: (
    file: File,
    index: number
  ) => Promise<CharacterImportPreview>
}

export function useCharacterImportQueue(deps: UseCharacterImportQueueDeps) {
  const { t, notification, qc, parseCharacterImportPreview } = deps

  const [importing, setImporting] = React.useState(false)
  const [importPreviewOpen, setImportPreviewOpen] = React.useState(false)
  const [importPreviewLoading, setImportPreviewLoading] = React.useState(false)
  const [importPreviewItems, setImportPreviewItems] = React.useState<CharacterImportPreview[]>([])
  const [importPreviewProcessing, setImportPreviewProcessing] = React.useState(false)
  const [importQueueState, dispatchImportQueue] = React.useReducer(
    characterImportQueueReducer,
    initialCharacterImportQueueState
  )
  const importDropDepthRef = React.useRef(0)
  const importButtonContainerRef = React.useRef<HTMLDivElement | null>(null)

  const resolveImportDetail = (error: unknown) => {
    const details = (error as any)?.details
    if (details && typeof details === "object") {
      return (details as any).detail ?? details
    }
    return null
  }

  const revokeImportPreviewAvatarUrls = React.useCallback(
    (items: CharacterImportPreview[]) => {
      if (typeof URL === "undefined" || typeof URL.revokeObjectURL !== "function") {
        return
      }
      for (const item of items) {
        const extension = getImportFileExtension(item.fileName)
        if (item.avatarUrl && IMPORT_IMAGE_EXTENSIONS.has(extension)) {
          try {
            URL.revokeObjectURL(item.avatarUrl)
          } catch {
            // no-op cleanup
          }
        }
      }
    },
    []
  )

  const resetImportPreview = React.useCallback(() => {
    setImportPreviewOpen(false)
    setImportPreviewProcessing(false)
    setImportPreviewLoading(false)
    importDropDepthRef.current = 0
    dispatchImportQueue({ type: "queue/reset" })
    setImportPreviewItems((previous) => {
      revokeImportPreviewAvatarUrls(previous)
      return []
    })
  }, [revokeImportPreviewAvatarUrls])

  // Cleanup avatar object URLs on unmount
  React.useEffect(() => {
    return () => {
      revokeImportPreviewAvatarUrls(importPreviewItems)
    }
  }, [importPreviewItems, revokeImportPreviewAvatarUrls])

  const importablePreviewItems = React.useMemo(
    () => importPreviewItems.filter((item) => !item.parseError),
    [importPreviewItems]
  )

  const importQueueItemsById = React.useMemo(() => {
    const map = new Map<string, (typeof importQueueState.items)[number]>()
    for (const item of importQueueState.items) {
      map.set(item.id, item)
    }
    return map
  }, [importQueueState.items])

  const importQueueSummary = React.useMemo(
    () => summarizeCharacterImportQueue(importQueueState.items),
    [importQueueState.items]
  )

  const retryableFailedPreviewItems = React.useMemo(
    () =>
      importablePreviewItems.filter((item) => {
        const state = importQueueItemsById.get(item.id)?.state
        return state === "failure"
      }),
    [importQueueItemsById, importablePreviewItems]
  )

  const importPreviewHasSuccessfulCompletion =
    importQueueSummary.complete && importQueueSummary.success > 0

  const importCharacterFile = React.useCallback(
    async (
      file: File,
      options?: CharacterImportOptions
    ): Promise<CharacterImportResult> => {
      const allowImageOnly = options?.allowImageOnly ?? false
      const suppressNotifications = options?.suppressNotifications ?? false
      const invalidateOnSuccess = options?.invalidateOnSuccess ?? true
      setImporting(true)
      try {
        const response = await tldwClient.importCharacterFile(file, {
          allowImageOnly
        })
        if (invalidateOnSuccess) {
          qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        }
        const message =
          response?.message ||
          t("settings:manageCharacters.import.success", {
            defaultValue: "Character imported successfully"
          })
        if (!suppressNotifications) {
          notification.success({
            message: t("settings:manageCharacters.import.title", {
              defaultValue: "Import complete"
            }),
            description: message
          })
        }
        return { success: true, fileName: file.name, message }
      } catch (err: any) {
        const detail = resolveImportDetail(err)
        if (
          detail?.code === "missing_character_data" &&
          detail?.can_import_image_only &&
          !allowImageOnly
        ) {
          const message =
            detail?.message ||
            t("settings:manageCharacters.import.imageOnlyDesc", {
              defaultValue:
                "No character data detected in the image metadata. Import as an image-only character?"
            })
          if (suppressNotifications) {
            return { success: false, fileName: file.name, message }
          }
          const { Modal } = await import("antd")
          Modal.confirm({
            title: t("settings:manageCharacters.import.imageOnlyTitle", {
              defaultValue: "No character data detected"
            }),
            content: message,
            okText: t("settings:manageCharacters.import.imageOnlyConfirm", {
              defaultValue: "Import image only"
            }),
            cancelText: t("common:cancel", { defaultValue: "Cancel" }),
            onOk: () =>
              void importCharacterFile(file, { allowImageOnly: true })
          })
          return { success: false, fileName: file.name, message }
        }
        const errorMessage =
          err?.message ||
          t("settings:manageCharacters.import.errorDesc", {
            defaultValue: "Unable to import character. Please try again."
          })
        if (!suppressNotifications) {
          notification.error({
            message: t("settings:manageCharacters.import.errorTitle", {
              defaultValue: "Import failed"
            }),
            description: errorMessage
          })
        }
        return { success: false, fileName: file.name, message: errorMessage }
      } finally {
        setImporting(false)
      }
    },
    [notification, qc, t]
  )

  const runBatchImport = React.useCallback(
    async (batchItems: CharacterImportPreview[]) => {
      const results: (CharacterImportResult & { id: string })[] = []
      setImportPreviewProcessing(true)
      try {
        for (const nextItem of batchItems) {
          dispatchImportQueue({ type: "item/processing", id: nextItem.id })
          const result = await importCharacterFile(nextItem.file, {
            suppressNotifications: true,
            invalidateOnSuccess: false
          })
          results.push({ ...result, id: nextItem.id })
          if (result.success) {
            dispatchImportQueue({
              type: "item/success",
              id: nextItem.id,
              message: result.message
            })
          } else {
            dispatchImportQueue({
              type: "item/failure",
              id: nextItem.id,
              message: result.message
            })
          }
        }
      } finally {
        setImportPreviewProcessing(false)
      }

      const successCount = results.filter((r) => r.success).length
      const failed = results.filter((r) => !r.success)

      if (successCount > 0) {
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      }

      if (failed.length === 0) {
        notification.success({
          message: t("settings:manageCharacters.import.batchSuccessTitle", {
            defaultValue: "Batch import complete"
          }),
          description: t("settings:manageCharacters.import.batchSuccessDesc", {
            defaultValue: "Imported {{count}} files successfully.",
            count: successCount
          })
        })
        return
      }

      const failureDetails = failed
        .map((r) => `${r.fileName}: ${r.message}`)
        .join(" | ")

      const message =
        successCount > 0
          ? t("settings:manageCharacters.import.batchPartialTitle", {
              defaultValue: "Batch import partially complete"
            })
          : t("settings:manageCharacters.import.batchFailedTitle", {
              defaultValue: "Batch import failed"
            })
      const description = `${t("settings:manageCharacters.import.batchSummary", {
        defaultValue: "{{success}} succeeded, {{failed}} failed.",
        success: successCount,
        failed: failed.length
      })} ${failureDetails}`.trim()

      if (successCount > 0) {
        notification.warning({ message, description })
      } else {
        notification.error({ message, description })
      }
    },
    [importCharacterFile, notification, qc, t]
  )

  const openImportPreviewForBatch = React.useCallback(
    async (batch: File[]) => {
      setImportPreviewLoading(true)
      try {
        const previews = await Promise.all(
          batch.map((nextFile, index) =>
            parseCharacterImportPreview(nextFile, index)
          )
        )
        setImportPreviewItems((previous) => {
          revokeImportPreviewAvatarUrls(previous)
          return previews
        })
        dispatchImportQueue({
          type: "queue/replace",
          files: previews.map((item) => ({
            id: item.id,
            fileName: item.fileName
          }))
        })
        for (const item of previews) {
          if (!item.parseError) continue
          dispatchImportQueue({
            type: "item/failure",
            id: item.id,
            message: t(item.parseError.key, {
              defaultValue: item.parseError.fallback,
              ...(item.parseError.values || {})
            })
          })
        }
        dispatchImportQueue({ type: "drag/leave" })
        setImportPreviewProcessing(false)
        setImportPreviewOpen(true)
      } catch (error: any) {
        notification.error({
          message: t("settings:manageCharacters.import.previewErrorTitle", {
            defaultValue: "Preview unavailable"
          }),
          description:
            error?.message ||
            t("settings:manageCharacters.import.previewErrorDesc", {
              defaultValue:
                "Could not build an import preview. Try uploading the file again."
            })
        })
      } finally {
        setImportPreviewLoading(false)
      }
    },
    [notification, parseCharacterImportPreview, revokeImportPreviewAvatarUrls, t]
  )

  const handleConfirmImportPreview = React.useCallback(async () => {
    if (importPreviewProcessing) return

    const skippedCount = importPreviewItems.length - importablePreviewItems.length
    if (importablePreviewItems.length === 0) {
      notification.error({
        message: t("settings:manageCharacters.import.previewNothingTitle", {
          defaultValue: "No importable files"
        }),
        description: t("settings:manageCharacters.import.previewNothingDesc", {
          defaultValue: "Fix preview errors or choose different files."
        })
      })
      return
    }

    await runBatchImport(importablePreviewItems)

    if (skippedCount > 0) {
      notification.warning({
        message: t("settings:manageCharacters.import.previewSkippedTitle", {
          defaultValue: "Some files were skipped"
        }),
        description: t("settings:manageCharacters.import.previewSkippedDesc", {
          defaultValue:
            "{{count}} files were skipped because preview parsing failed.",
          count: skippedCount
        })
      })
    }
  }, [
    importPreviewProcessing,
    importPreviewItems.length,
    importablePreviewItems,
    notification,
    runBatchImport,
    t
  ])

  const handleRetryFailedImportPreview = React.useCallback(async () => {
    if (importPreviewProcessing) return
    if (retryableFailedPreviewItems.length === 0) return
    await runBatchImport(retryableFailedPreviewItems)
  }, [importPreviewProcessing, retryableFailedPreviewItems, runBatchImport])

  const handleImportUpload = React.useCallback(
    async (file: File, fileList: File[]) => {
      const batch = (fileList && fileList.length > 0 ? fileList : [file]).filter(
        Boolean
      )

      if (
        !shouldHandleImportUploadEvent({
          file,
          fileList: batch
        })
      ) {
        return false
      }

      await openImportPreviewForBatch(batch)
      return false
    },
    [openImportPreviewForBatch]
  )

  const isImportBusy =
    importing || importPreviewLoading || importPreviewProcessing

  const handleImportDragEnter = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      if (isImportBusy) return
      event.preventDefault()
      event.stopPropagation()
      importDropDepthRef.current += 1
      dispatchImportQueue({ type: "drag/enter" })
    },
    [isImportBusy]
  )

  const handleImportDragLeave = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      if (isImportBusy) return
      event.preventDefault()
      event.stopPropagation()
      importDropDepthRef.current = Math.max(importDropDepthRef.current - 1, 0)
      if (importDropDepthRef.current === 0) {
        dispatchImportQueue({ type: "drag/leave" })
      }
    },
    [isImportBusy]
  )

  const handleImportDragOver = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      if (isImportBusy) return
      event.preventDefault()
      event.stopPropagation()
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "copy"
      }
    },
    [isImportBusy]
  )

  const handleImportDrop = React.useCallback(
    async (event: React.DragEvent<HTMLDivElement>) => {
      if (isImportBusy) return
      event.preventDefault()
      event.stopPropagation()
      importDropDepthRef.current = 0
      dispatchImportQueue({ type: "drag/leave" })

      const files = Array.from(event.dataTransfer?.files || []).filter(
        Boolean
      ) as File[]
      if (files.length === 0) return
      await openImportPreviewForBatch(files)
    },
    [isImportBusy, openImportPreviewForBatch]
  )

  const triggerImportPicker = React.useCallback(() => {
    const uploadButton =
      importButtonContainerRef.current?.querySelector<HTMLButtonElement>("button")
    uploadButton?.click()
  }, [])

  const getImportQueueStateLabel = React.useCallback(
    (state: "queued" | "processing" | "success" | "failure") => {
      if (state === "processing") {
        return t("settings:manageCharacters.import.state.processing", {
          defaultValue: "Processing"
        })
      }
      if (state === "success") {
        return t("settings:manageCharacters.import.state.success", {
          defaultValue: "Success"
        })
      }
      if (state === "failure") {
        return t("settings:manageCharacters.import.state.failure", {
          defaultValue: "Failed"
        })
      }
      return t("settings:manageCharacters.import.state.queued", {
        defaultValue: "Queued"
      })
    },
    [t]
  )

  const getImportQueueStateColor = React.useCallback(
    (state: "queued" | "processing" | "success" | "failure") => {
      if (state === "processing") return "processing"
      if (state === "success") return "success"
      if (state === "failure") return "error"
      return "default"
    },
    []
  )

  return {
    // refs
    importButtonContainerRef,
    // state
    importing,
    importPreviewOpen,
    setImportPreviewOpen,
    importPreviewLoading,
    importPreviewItems,
    importPreviewProcessing,
    importQueueState,
    dispatchImportQueue,
    // computed
    importablePreviewItems,
    importQueueItemsById,
    importQueueSummary,
    retryableFailedPreviewItems,
    importPreviewHasSuccessfulCompletion,
    isImportBusy,
    // callbacks
    importCharacterFile,
    runBatchImport,
    openImportPreviewForBatch,
    handleConfirmImportPreview,
    handleRetryFailedImportPreview,
    handleImportUpload,
    handleImportDragEnter,
    handleImportDragLeave,
    handleImportDragOver,
    handleImportDrop,
    triggerImportPicker,
    resetImportPreview,
    getImportQueueStateLabel,
    getImportQueueStateColor
  }
}
