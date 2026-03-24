import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildDuplicateWorldBookName,
  WORLD_BOOK_FORM_DEFAULTS
} from "../worldBookFormUtils"
import { normalizeKeywordList } from "../worldBookEntryUtils"
import {
  convertWorldBookImport,
  getWorldBookImportFormatLabel,
  getWorldBookImportJsonErrorMessage,
  validateWorldBookImportConversion,
  type WorldBookImportFormat
} from "../worldBookInteropUtils"

const IMPORT_PREVIEW_ENTRY_LIMIT = 5
const IMPORT_PREVIEW_CONTENT_LIMIT = 140

const truncateImportPreviewContent = (content: unknown): string => {
  const text = String(content || "")
  if (text.length <= IMPORT_PREVIEW_CONTENT_LIMIT) return text
  return `${text.slice(0, IMPORT_PREVIEW_CONTENT_LIMIT - 3)}...`
}

const normalizeKeywords = (value: any): string[] => {
  return normalizeKeywordList(value)
}

const normalizeEntryGroup = (value: unknown): string | null => {
  const normalized = String(value ?? "").trim()
  return normalized.length > 0 ? normalized : null
}

export interface ImportPreview {
  name?: string
  entryCount: number
  conflict?: boolean
  format?: WorldBookImportFormat
  warnings?: string[]
  settings?: {
    scanDepth?: number
    tokenBudget?: number
    recursiveScanning?: boolean
    enabled?: boolean
  }
  previewEntries?: Array<{
    keywords: string[]
    contentPreview: string
  }>
}

export interface UseWorldBookImportExportDeps {
  /** World books list from the query */
  data: any[] | undefined
  /** React Query client for cache invalidation */
  qc: { invalidateQueries: (opts: { queryKey: string[] }) => void }
  /** Notification API */
  notification: {
    success: (opts: { message: string; description?: string }) => void
    error: (opts: { message: string; description?: string }) => void
  }
  /** Selected world book keys for bulk export */
  selectedWorldBookKeys: React.Key[]
}

export function useWorldBookImportExport(deps: UseWorldBookImportExportDeps) {
  const { data, qc, notification, selectedWorldBookKeys } = deps

  // Import state
  const [openImport, setOpenImport] = React.useState(false)
  const [importFormatHelpOpen, setImportFormatHelpOpen] = React.useState(false)
  const [importErrorDetailsOpen, setImportErrorDetailsOpen] = React.useState(false)
  const [importPreviewEntriesOpen, setImportPreviewEntriesOpen] = React.useState(false)
  const [mergeOnConflict, setMergeOnConflict] = React.useState(false)
  const [importPreview, setImportPreview] = React.useState<ImportPreview | null>(null)
  const [importPayload, setImportPayload] = React.useState<any | null>(null)
  const [importError, setImportError] = React.useState<string | null>(null)
  const [importErrorDetails, setImportErrorDetails] = React.useState<string | null>(null)
  const [importFileName, setImportFileName] = React.useState<string | null>(null)

  // Export state
  const [exportingId, setExportingId] = React.useState<number | null>(null)
  const [bulkExportMode, setBulkExportMode] = React.useState<"all" | "selected" | null>(null)
  const [duplicatingId, setDuplicatingId] = React.useState<number | null>(null)

  const exportJsonFile = React.useCallback((payload: unknown, fileName: string) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = fileName
    anchor.click()
    URL.revokeObjectURL(url)
  }, [])

  const exportSingleWorldBook = React.useCallback(
    async (record: any) => {
      if (!record?.id) return
      setExportingId(record.id)
      try {
        const exported = await tldwClient.exportWorldBook(record.id)
        const safeName = String(record?.name || "world-book")
          .trim()
          .replace(/[^a-zA-Z0-9._-]+/g, "-")
          .replace(/^-+|-+$/g, "") || "world-book"
        exportJsonFile(exported, `${safeName}.json`)
      } catch (e: any) {
        notification.error({ message: "Export failed", description: e?.message })
      } finally {
        setExportingId(null)
      }
    },
    [exportJsonFile, notification]
  )

  const exportWorldBookBundle = React.useCallback(
    async (mode: "all" | "selected") => {
      if (bulkExportMode) return

      const source = Array.isArray(data) ? data : []
      const selectedIdSet = new Set(
        selectedWorldBookKeys
          .map((key) => Number(key))
          .filter((id) => Number.isFinite(id) && id > 0)
      )
      const targetBooks =
        mode === "all"
          ? source
          : source.filter((book: any) => selectedIdSet.has(Number(book?.id)))
      if (targetBooks.length === 0) return

      setBulkExportMode(mode)
      try {
        const exportedBooks = await Promise.all(
          targetBooks.map(async (book: any) => ({
            id: Number(book?.id),
            name: String(book?.name || ""),
            data: await tldwClient.exportWorldBook(book.id)
          }))
        )
        const timestamp = new Date().toISOString()
        const fileSafeDate = timestamp.slice(0, 10)
        exportJsonFile(
          {
            bundle_type: "tldw-world-books-export",
            bundle_version: 1,
            exported_at: timestamp,
            export_mode: mode,
            world_books: exportedBooks
          },
          `world-books-${mode}-${fileSafeDate}.json`
        )
        notification.success({
          message: mode === "all" ? "Exported all world books" : "Exported selected world books",
          description: `Downloaded ${exportedBooks.length} world books.`
        })
      } catch (e: any) {
        notification.error({
          message: "Export failed",
          description: e?.message || "Could not export world books."
        })
      } finally {
        setBulkExportMode(null)
      }
    },
    [bulkExportMode, data, exportJsonFile, notification, selectedWorldBookKeys]
  )

  const duplicateWorldBook = React.useCallback(
    async (record: any) => {
      if (!record?.id || duplicatingId != null) return
      setDuplicatingId(record.id)
      try {
        await tldwClient.initialize()
        const duplicateName = buildDuplicateWorldBookName(record.name, (data || []) as any[])
        const created = await tldwClient.createWorldBook({
          name: duplicateName,
          description: record.description,
          scan_depth:
            typeof record.scan_depth === "number"
              ? record.scan_depth
              : WORLD_BOOK_FORM_DEFAULTS.scan_depth,
          token_budget:
            typeof record.token_budget === "number"
              ? record.token_budget
              : WORLD_BOOK_FORM_DEFAULTS.token_budget,
          recursive_scanning:
            typeof record.recursive_scanning === "boolean"
              ? record.recursive_scanning
              : WORLD_BOOK_FORM_DEFAULTS.recursive_scanning,
          enabled:
            typeof record.enabled === "boolean"
              ? record.enabled
              : WORLD_BOOK_FORM_DEFAULTS.enabled
        })

        const createdId = Number(created?.id)
        if (!Number.isFinite(createdId) || createdId <= 0) {
          throw new Error("Could not determine duplicated world book ID")
        }

        const entriesResponse = await tldwClient.listWorldBookEntries(record.id, false)
        const sourceEntries = Array.isArray(entriesResponse?.entries) ? entriesResponse.entries : []

        for (const entry of sourceEntries) {
          await tldwClient.addWorldBookEntry(createdId, {
            keywords: normalizeKeywords(entry?.keywords),
            content: String(entry?.content || ""),
            group: normalizeEntryGroup(entry?.group ?? entry?.metadata?.group),
            priority:
              typeof entry?.priority === "number"
                ? entry.priority
                : 0,
            enabled:
              typeof entry?.enabled === "boolean"
                ? entry.enabled
                : true,
            case_sensitive: !!entry?.case_sensitive,
            regex_match: !!entry?.regex_match,
            whole_word_match:
              typeof entry?.whole_word_match === "boolean"
                ? entry.whole_word_match
                : true,
            appendable:
              typeof entry?.appendable === "boolean"
                ? entry.appendable
                : Boolean(entry?.metadata?.appendable)
          })
        }

        qc.invalidateQueries({ queryKey: ["tldw:listWorldBooks"] })
        notification.success({
          message: "Duplicated",
          description: `Created "${duplicateName}" with ${sourceEntries.length} copied entries.`
        })
      } catch (e: any) {
        notification.error({
          message: "Duplicate failed",
          description: e?.message || "Failed to duplicate world book"
        })
      } finally {
        setDuplicatingId(null)
      }
    },
    [data, duplicatingId, notification, qc]
  )

  const handleImportUpload = React.useCallback(
    async (file: File) => {
      const isJsonFile =
        file?.type === "application/json" || String(file?.name || "").toLowerCase().endsWith(".json")
      setImportFileName(file.name)
      setImportErrorDetailsOpen(false)
      setImportPreviewEntriesOpen(false)
      if (!isJsonFile) {
        setImportError("Please select a .json file.")
        setImportErrorDetails(
          `Selected file "${file.name}" does not look like JSON (MIME: ${file.type || "unknown"}).`
        )
        setImportPreview(null)
        setImportPayload(null)
        return false
      }
      try {
        const text = await file.text()
        const parsed = JSON.parse(text)
        const conversion = convertWorldBookImport(parsed)
        const validationError = validateWorldBookImportConversion(parsed, conversion)
        const conversionDetail = [
          `Detected format: ${getWorldBookImportFormatLabel(conversion.format)}`,
          conversion.error ? `Conversion detail: ${conversion.error}` : "",
          (conversion.warnings || []).length > 0
            ? `Warnings:\n- ${(conversion.warnings || []).join("\n- ")}`
            : ""
        ]
          .filter(Boolean)
          .join("\n")

        if (!conversion.payload) {
          setImportError(validationError || conversion.error || "Unsupported import format")
          setImportErrorDetails(conversionDetail || null)
          setImportErrorDetailsOpen(false)
          setImportPreview(null)
          setImportPayload(null)
          if (conversionDetail) {
            console.debug("[WorldBooks] Import conversion failed", conversionDetail)
          }
          return false
        }

        const payload = conversion.payload
        const name = payload?.world_book?.name
        const entries = Array.isArray(payload?.entries) ? payload.entries : []
        const entryCount = entries.length
        const conflict = !!(data || []).find((wb: any) => wb.name === name)
        const previewEntries = entries
          .slice(0, IMPORT_PREVIEW_ENTRY_LIMIT)
          .map((entry: any) => ({
            keywords: normalizeKeywordList(entry?.keywords),
            contentPreview: truncateImportPreviewContent(entry?.content)
          }))
        const worldBookSettings =
          payload?.world_book && typeof payload.world_book === "object"
            ? (payload.world_book as Record<string, unknown>)
            : {}
        setImportPreview({
          name,
          entryCount,
          conflict,
          format: conversion.format,
          warnings: conversion.warnings,
          settings: {
            scanDepth:
              typeof worldBookSettings?.scan_depth === "number"
                ? worldBookSettings.scan_depth
                : undefined,
            tokenBudget:
              typeof worldBookSettings?.token_budget === "number"
                ? worldBookSettings.token_budget
                : undefined,
            recursiveScanning:
              typeof worldBookSettings?.recursive_scanning === "boolean"
                ? worldBookSettings.recursive_scanning
                : undefined,
            enabled:
              typeof worldBookSettings?.enabled === "boolean"
                ? worldBookSettings.enabled
                : undefined
          },
          previewEntries
        })
        setImportPreviewEntriesOpen(false)
        if (validationError) {
          setImportError(validationError)
          setImportErrorDetails(conversionDetail || null)
          setImportErrorDetailsOpen(false)
          setImportPayload(null)
          if (conversionDetail) {
            console.debug("[WorldBooks] Import validation failed", conversionDetail)
          }
        } else {
          setImportError(null)
          setImportErrorDetails(null)
          setImportPayload(payload)
        }
      } catch (err: any) {
        const rawErrorDetails = String(err?.message || err || "").trim()
        setImportError(getWorldBookImportJsonErrorMessage(err))
        setImportErrorDetails(rawErrorDetails || null)
        setImportErrorDetailsOpen(false)
        setImportPreview(null)
        setImportPayload(null)
        if (rawErrorDetails) {
          console.debug("[WorldBooks] Import parse failed", rawErrorDetails)
        }
      }
      return false
    },
    [data]
  )

  const openImportModal = React.useCallback(() => {
    setImportFormatHelpOpen(false)
    setImportErrorDetailsOpen(false)
    setImportPreviewEntriesOpen(false)
    setOpenImport(true)
  }, [])

  const closeImportModal = React.useCallback(() => {
    setOpenImport(false)
    setImportFormatHelpOpen(false)
    setImportErrorDetailsOpen(false)
    setImportPreviewEntriesOpen(false)
    setImportPreview(null)
    setImportPayload(null)
    setImportError(null)
    setImportErrorDetails(null)
    setImportFileName(null)
  }, [])

  const resetImportAfterSuccess = React.useCallback(() => {
    setOpenImport(false)
    setImportFormatHelpOpen(false)
    setImportErrorDetailsOpen(false)
    setImportPreviewEntriesOpen(false)
    setImportPreview(null)
    setImportPayload(null)
    setImportError(null)
    setImportErrorDetails(null)
    setImportFileName(null)
  }, [])

  return {
    // Import state
    openImport,
    setOpenImport,
    importFormatHelpOpen,
    setImportFormatHelpOpen,
    importErrorDetailsOpen,
    setImportErrorDetailsOpen,
    importPreviewEntriesOpen,
    setImportPreviewEntriesOpen,
    mergeOnConflict,
    setMergeOnConflict,
    importPreview,
    importPayload,
    importError,
    importErrorDetails,
    importFileName,
    // Export state
    exportingId,
    bulkExportMode,
    duplicatingId,
    // callbacks
    exportJsonFile,
    exportSingleWorldBook,
    exportWorldBookBundle,
    duplicateWorldBook,
    handleImportUpload,
    openImportModal,
    closeImportModal,
    resetImportAfterSuccess,
  }
}
