import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"

type UseDictionaryExportActionsParams = {
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
}

function hasAdvancedDictionaryEntryFields(entries: any[]): boolean {
  return entries.some((entry: any) => {
    const probability = typeof entry?.probability === "number" ? entry.probability : 1
    const caseSensitive =
      typeof entry?.case_sensitive === "boolean" ? entry.case_sensitive : undefined
    const maxReplacements =
      Number.isInteger(entry?.max_replacements) && entry.max_replacements > 0
    const timedEffects =
      entry?.timed_effects &&
      typeof entry.timed_effects === "object" &&
      ["sticky", "cooldown", "delay"].some((key) => {
        const value = Number((entry.timed_effects as any)?.[key])
        return Number.isFinite(value) && value > 0
      })
    return probability !== 1 || maxReplacements || timedEffects || caseSensitive === false
  })
}

export function useDictionaryExportActions({
  notification,
  confirmDanger,
  t,
}: UseDictionaryExportActionsParams) {
  const exportDictionaryAsJson = React.useCallback(
    async (record: any) => {
      try {
        const exp = await tldwClient.exportDictionaryJSON(record.id)
        const blob = new Blob([JSON.stringify(exp, null, 2)], {
          type: "application/json",
        })
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement("a")
        anchor.href = url
        anchor.download = `${record.name || "dictionary"}.json`
        anchor.click()
        URL.revokeObjectURL(url)
      } catch (error: any) {
        notification.error({
          message: "Export failed",
          description: error?.message,
        })
      }
    },
    [notification]
  )

  const exportDictionaryAsMarkdown = React.useCallback(
    async (record: any) => {
      try {
        const fullExport = await tldwClient.exportDictionaryJSON(record.id)
        const exportedEntries = Array.isArray(fullExport?.entries)
          ? fullExport.entries
          : []
        if (hasAdvancedDictionaryEntryFields(exportedEntries)) {
          const proceed = await confirmDanger({
            title: "Markdown export may lose advanced settings",
            content:
              "This dictionary includes advanced entry settings (for example probability, timed effects, or replacement limits). Export JSON for full fidelity.",
            okText: "Export Markdown anyway",
            cancelText: t("common:cancel", { defaultValue: "Cancel" }),
          })
          if (!proceed) return
        }

        const exp = await tldwClient.exportDictionaryMarkdown(record.id)
        const blob = new Blob([exp?.content || ""], { type: "text/markdown" })
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement("a")
        anchor.href = url
        anchor.download = `${record.name || "dictionary"}.md`
        anchor.click()
        URL.revokeObjectURL(url)
      } catch (error: any) {
        notification.error({
          message: "Export failed",
          description: error?.message,
        })
      }
    },
    [confirmDanger, notification, t]
  )

  return {
    exportDictionaryAsJson,
    exportDictionaryAsMarkdown,
  }
}
