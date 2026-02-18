import React from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Typography
} from "antd"
import { useTranslation } from "react-i18next"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import { processInChunks } from "@/utils/chunk-processing"
import {
  useDecksQuery,
  useImportFlashcardsMutation,
  useImportLimitsQuery
} from "../hooks"
import { FileDropZone } from "../components"
import {
  deleteFlashcard,
  getFlashcard,
  type FlashcardsImportError
} from "@/services/flashcards"

const { Text } = Typography

interface ImportResultSummary {
  imported: number
  skipped: number
  errors: FlashcardsImportError[]
}

interface ImportedCardReference {
  uuid: string
}

const IMPORT_UNDO_SECONDS = 30
const IMPORT_UNDO_CHUNK_SIZE = 50

const normalizeImportErrors = (value: unknown): FlashcardsImportError[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null
      const row = entry as Record<string, unknown>
      const rawError = row.error
      if (typeof rawError !== "string" || rawError.trim().length === 0) {
        return null
      }
      const line = typeof row.line === "number" ? row.line : null
      const index = typeof row.index === "number" ? row.index : null
      return {
        error: rawError,
        line,
        index
      }
    })
    .filter((item): item is FlashcardsImportError => item !== null)
}

const normalizeImportedItems = (value: unknown): ImportedCardReference[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null
      const row = entry as Record<string, unknown>
      const uuid = row.uuid
      if (typeof uuid !== "string" || uuid.trim().length === 0) return null
      return {
        uuid
      }
    })
    .filter((item): item is ImportedCardReference => item !== null)
}

/**
 * Import panel for CSV/TSV flashcard import.
 */
const ImportPanel: React.FC = () => {
  const qc = useQueryClient()
  const message = useAntdMessage()
  const { showUndoNotification } = useUndoNotification()
  const { t } = useTranslation(["option", "common"])
  const limitsQuery = useImportLimitsQuery()
  const importMutation = useImportFlashcardsMutation()

  const [content, setContent] = React.useState("")
  const [delimiter, setDelimiter] = React.useState<string>("\t")
  const [hasHeader, setHasHeader] = React.useState<boolean>(true)
  const [lastResult, setLastResult] = React.useState<ImportResultSummary | null>(null)

  const invalidateFlashcardQueries = React.useCallback(async () => {
    await qc.invalidateQueries({
      predicate: (query) =>
        Array.isArray(query.queryKey) &&
        typeof query.queryKey[0] === "string" &&
        query.queryKey[0].startsWith("flashcards:")
    })
  }, [qc])

  const handleImport = async () => {
    try {
      const result = await importMutation.mutateAsync({
        content,
        delimiter,
        hasHeader
      })
      const importedItems = normalizeImportedItems(result.items)
      const imported =
        typeof result.imported === "number"
          ? result.imported
          : importedItems.length
      const errors = normalizeImportErrors(result.errors)
      const skipped = errors.length

      setLastResult({
        imported,
        skipped,
        errors
      })

      if (errors.length > 0) {
        message.warning(
          t("option:flashcards.importResultWithErrors", {
            defaultValue: "Imported {{imported}} cards, skipped {{skipped}} rows ({{errorCount}} errors).",
            imported,
            skipped,
            errorCount: errors.length
          })
        )
      } else {
        message.success(
          t("option:flashcards.importResultSuccess", {
            defaultValue: "Imported {{count}} cards.",
            count: imported
          })
        )
        setContent("")
      }

      if (importedItems.length > 0) {
        showUndoNotification({
          title:
            errors.length > 0
              ? t("option:flashcards.importUndoTitlePartial", {
                  defaultValue: "Partial import completed"
                })
              : t("option:flashcards.importUndoTitle", {
                  defaultValue: "Import completed"
                }),
          description: t("option:flashcards.importUndoHint", {
            defaultValue:
              "Undo within {{seconds}}s to remove {{count}} imported cards.",
            seconds: IMPORT_UNDO_SECONDS,
            count: importedItems.length
          }),
          duration: IMPORT_UNDO_SECONDS,
          onUndo: async () => {
            let failedRollbacks = 0
            await processInChunks(importedItems, IMPORT_UNDO_CHUNK_SIZE, async (chunk) => {
              const results = await Promise.allSettled(
                chunk.map(async (item) => {
                  const latest = await getFlashcard(item.uuid)
                  await deleteFlashcard(item.uuid, latest.version)
                })
              )
              failedRollbacks += results.filter((result) => result.status === "rejected").length
            })
            await invalidateFlashcardQueries()
            if (failedRollbacks > 0) {
              throw new Error(
                t("option:flashcards.importUndoPartialFailure", {
                  defaultValue: "Some imported cards could not be rolled back."
                })
              )
            }
          }
        })
      }
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : "Import failed"
      message.error(errorMessage)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <Text type="secondary">
          {t("option:flashcards.importHelp", {
            defaultValue: "Paste TSV/CSV lines: Deck, Front, Back, Tags, Notes"
          })}
        </Text>
        <pre className="mt-1 rounded bg-surface2 p-2 text-xs text-text">
          Deck	Front	Back	Tags	Notes
          My deck	What is a closure?	A function with preserved outer scope.	javascript; fundamentals	Lecture 3
        </pre>
      </div>

      {/* File drop zone */}
      <FileDropZone
        onFileContent={setContent}
        onError={(error) => message.error(error)}
      />

      <Text type="secondary" className="text-center text-xs">
        {t("option:flashcards.orPasteBelow", {
          defaultValue: "or paste content below"
        })}
      </Text>

      <Input.TextArea
        rows={8}
        placeholder={t("option:flashcards.pasteContent", {
          defaultValue: "Paste content here..."
        })}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        data-testid="flashcards-import-textarea"
      />
      <Space>
        <Select
          value={delimiter}
          onChange={setDelimiter}
          data-testid="flashcards-import-delimiter"
          options={[
            {
              label: t("option:flashcards.tab", { defaultValue: "Tab" }),
              value: "\t"
            },
            {
              label: t("option:flashcards.comma", { defaultValue: ", (Comma)" }),
              value: ","
            },
            {
              label: t("option:flashcards.semicolon", {
                defaultValue: "; (Semicolon)"
              }),
              value: ";"
            },
            {
              label: t("option:flashcards.pipe", { defaultValue: "| (Pipe)" }),
              value: "|"
            }
          ]}
        />
        <Space>
          <Text>
            {t("option:flashcards.hasHeader", { defaultValue: "Has header" })}
          </Text>
          <Switch
            checked={hasHeader}
            onChange={setHasHeader}
            data-testid="flashcards-import-has-header"
          />
        </Space>
      </Space>
      {limitsQuery.data && (
        <Text type="secondary" className="text-xs">
          {t("option:flashcards.importLimits", {
            defaultValue:
              "Limits: max {{maxCards}} cards, {{maxSize}} bytes per import",
            maxCards: limitsQuery.data.max_cards_per_import,
            maxSize: limitsQuery.data.max_content_size_bytes
          })}
        </Text>
      )}
      <Button
        type="primary"
        onClick={handleImport}
        loading={importMutation.isPending}
        disabled={!content.trim()}
        data-testid="flashcards-import-button"
      >
        {t("option:flashcards.importButton", { defaultValue: "Import" })}
      </Button>

      {lastResult && (
        <Alert
          showIcon
          type={lastResult.errors.length > 0 ? "warning" : "success"}
          title={
            lastResult.errors.length > 0
              ? t("option:flashcards.lastImportPartial", {
                  defaultValue: "Last import: {{imported}} imported, {{skipped}} skipped",
                  imported: lastResult.imported,
                  skipped: lastResult.skipped
                })
              : t("option:flashcards.lastImportSuccess", {
                  defaultValue: "Last import: {{imported}} cards imported",
                  imported: lastResult.imported
                })
          }
          description={
            lastResult.errors.length > 0 && (
              <div className="mt-1 space-y-1 text-xs">
                {lastResult.errors.slice(0, 6).map((err, idx) => {
                  const location =
                    typeof err.line === "number"
                      ? t("option:flashcards.importErrorLine", {
                          defaultValue: "Line {{line}}",
                          line: err.line
                        })
                      : typeof err.index === "number"
                        ? t("option:flashcards.importErrorItem", {
                            defaultValue: "Item {{index}}",
                            index: err.index
                          })
                        : t("option:flashcards.importErrorRowUnknown", {
                            defaultValue: "Unknown row"
                          })
                  return (
                    <div key={`${location}-${idx}`}>
                      <Text code>{location}</Text>
                      <Text className="ml-2">{err.error}</Text>
                    </div>
                  )
                })}
                {lastResult.errors.length > 6 && (
                  <Text type="secondary">
                    {t("option:flashcards.importErrorsMore", {
                      defaultValue: "+{{count}} more errors",
                      count: lastResult.errors.length - 6
                    })}
                  </Text>
                )}
              </div>
            )
          }
        />
      )}
    </div>
  )
}

/**
 * Export panel for CSV/APKG export.
 */
const ExportPanel: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const message = useAntdMessage()
  const decksQuery = useDecksQuery()
  const [exportDeckId, setExportDeckId] = React.useState<number | null>(null)
  const [exportFormat, setExportFormat] = React.useState<"csv" | "apkg">("csv")
  const [isExporting, setIsExporting] = React.useState(false)

  const handleExport = async () => {
    setIsExporting(true)
    try {
      const { exportFlashcardsFile, exportFlashcards } = await import(
        "@/services/flashcards"
      )
      let blob: Blob
      if (exportFormat === "apkg") {
        blob = await exportFlashcardsFile({
          deck_id: exportDeckId ?? undefined,
          format: "apkg"
        })
      } else {
        const text = await exportFlashcards({
          deck_id: exportDeckId ?? undefined,
          format: "csv"
        })
        blob = new Blob([text], { type: "text/csv;charset=utf-8" })
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = exportFormat === "apkg" ? "flashcards.apkg" : "flashcards.csv"
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : "Export failed"
      message.error(errorMessage)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <Text type="secondary">
          {t("option:flashcards.exportHelp", {
            defaultValue:
              "Export your flashcards to CSV or Anki-compatible APKG format."
          })}
        </Text>
      </div>
      <Form.Item
        label={t("option:flashcards.deck", { defaultValue: "Deck" })}
        className="!mb-2"
      >
        <Select
          placeholder={t("option:flashcards.allDecks", {
            defaultValue: "All decks"
          })}
          allowClear
          loading={decksQuery.isLoading}
          value={exportDeckId ?? undefined}
          onChange={setExportDeckId}
          data-testid="flashcards-export-deck"
          options={(decksQuery.data || []).map((d) => ({
            label: d.name,
            value: d.id
          }))}
        />
      </Form.Item>
      <Form.Item
        label={t("option:flashcards.exportFormat", { defaultValue: "Format" })}
        className="!mb-2"
      >
        <Select
          value={exportFormat}
          onChange={setExportFormat}
          data-testid="flashcards-export-format"
          options={[
            { label: "CSV", value: "csv" },
            { label: "APKG (Anki)", value: "apkg" }
          ]}
        />
      </Form.Item>
      <Button
        type="primary"
        onClick={handleExport}
        loading={isExporting}
        data-testid="flashcards-export-button"
      >
        {t("option:flashcards.exportButton", { defaultValue: "Export" })}
      </Button>
    </div>
  )
}

/**
 * Import/Export tab for flashcards.
 */
export const ImportExportTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])

  return (
    <div className="grid gap-4 grid-cols-1 lg:grid-cols-2">
      <Card
        title={t("option:flashcards.importTitle", {
          defaultValue: "Import Flashcards"
        })}
      >
        <ImportPanel />
      </Card>
      <Card
        title={t("option:flashcards.exportTitle", {
          defaultValue: "Export Flashcards"
        })}
      >
        <ExportPanel />
      </Card>
    </div>
  )
}

export default ImportExportTab
