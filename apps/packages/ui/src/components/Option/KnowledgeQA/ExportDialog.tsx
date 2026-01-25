/**
 * ExportDialog - Export conversations as markdown/PDF with citations
 */

import React, { useState, useCallback } from "react"
import {
  Download,
  FileText,
  FileDown,
  Book,
  X,
  Loader2,
  Check,
  Copy,
} from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import type { ExportFormat, ExportOptions } from "./types"
import type { RagCitationStyle } from "@/services/rag/unified-rag"

type ExportDialogProps = {
  open: boolean
  onClose: () => void
  className?: string
}

const DEFAULT_OPTIONS: ExportOptions = {
  format: "markdown",
  includeSettingsSnapshot: false,
  includeSourceExcerpts: true,
  citationStyle: "apa",
}

export function ExportDialog({ open, onClose, className }: ExportDialogProps) {
  const { messages, currentThreadId, results, answer, query } = useKnowledgeQA()
  const [options, setOptions] = useState<ExportOptions>(DEFAULT_OPTIONS)
  const [isExporting, setIsExporting] = useState(false)
  const [exportedContent, setExportedContent] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleExport = useCallback(async () => {
    setIsExporting(true)
    setExportedContent(null)

    try {
      let content = ""

      if (options.format === "markdown") {
        content = generateMarkdown(
          query,
          answer,
          results,
          messages,
          options
        )
        setExportedContent(content)
      } else if (options.format === "pdf") {
        // For PDF, generate markdown first then trigger print
        content = generateMarkdown(
          query,
          answer,
          results,
          messages,
          options
        )
        setExportedContent(content)
        // Trigger print after a short delay to allow content to render
        setTimeout(() => {
          window.print()
        }, 500)
      } else if (options.format === "chatbook") {
        // Call the chatbook export API
        if (currentThreadId) {
          const response = await fetch("/api/v1/chatbooks/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              conversation_ids: [currentThreadId],
              include_attachments: true,
            }),
          })
          if (response.ok) {
            const blob = await response.blob()
            downloadBlob(blob, `knowledge_qa_${Date.now()}.zip`)
            onClose()
            return
          }
        }
      }
    } catch (error) {
      console.error("Export failed:", error)
    } finally {
      setIsExporting(false)
    }
  }, [options, query, answer, results, messages, currentThreadId, onClose])

  const handleDownload = useCallback(() => {
    if (!exportedContent) return

    const blob = new Blob([exportedContent], { type: "text/markdown" })
    downloadBlob(blob, `knowledge_qa_${Date.now()}.md`)
  }, [exportedContent])

  const handleCopy = useCallback(async () => {
    if (!exportedContent) return

    try {
      await navigator.clipboard.writeText(exportedContent)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error("Copy failed:", error)
    }
  }, [exportedContent])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose} />

      {/* Dialog */}
      <div
        className={cn(
          "fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
          "w-full max-w-lg max-h-[90vh]",
          "bg-background rounded-xl shadow-xl border border-border",
          "flex flex-col z-50",
          className
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-primary" />
            <h2 className="font-semibold text-lg">Export Conversation</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Format selection */}
          <div className="space-y-3">
            <label className="text-sm font-medium">Export Format</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "markdown", label: "Markdown", icon: FileText },
                { value: "pdf", label: "PDF", icon: FileDown },
                { value: "chatbook", label: "Chatbook", icon: Book },
              ].map((fmt) => {
                const Icon = fmt.icon
                const isSelected = options.format === fmt.value
                return (
                  <button
                    key={fmt.value}
                    onClick={() =>
                      setOptions((prev) => ({
                        ...prev,
                        format: fmt.value as ExportFormat,
                      }))
                    }
                    className={cn(
                      "flex flex-col items-center gap-2 p-4 rounded-lg border transition-all",
                      isSelected
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "border-border hover:border-primary/30"
                    )}
                  >
                    <Icon
                      className={cn(
                        "w-6 h-6",
                        isSelected ? "text-primary" : "text-muted-foreground"
                      )}
                    />
                    <span className="text-sm font-medium">{fmt.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Options */}
          {options.format !== "chatbook" && (
            <>
              {/* Citation style */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Citation Style</label>
                <select
                  value={options.citationStyle}
                  onChange={(e) =>
                    setOptions((prev) => ({
                      ...prev,
                      citationStyle: e.target.value as RagCitationStyle,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="apa">APA</option>
                  <option value="mla">MLA</option>
                  <option value="chicago">Chicago</option>
                  <option value="harvard">Harvard</option>
                  <option value="ieee">IEEE</option>
                </select>
              </div>

              {/* Include options */}
              <div className="space-y-3">
                <label className="text-sm font-medium">Include</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={options.includeSourceExcerpts}
                      onChange={(e) =>
                        setOptions((prev) => ({
                          ...prev,
                          includeSourceExcerpts: e.target.checked,
                        }))
                      }
                      className="rounded"
                    />
                    <span className="text-sm">Source excerpts</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={options.includeSettingsSnapshot}
                      onChange={(e) =>
                        setOptions((prev) => ({
                          ...prev,
                          includeSettingsSnapshot: e.target.checked,
                        }))
                      }
                      className="rounded"
                    />
                    <span className="text-sm">Settings snapshot</span>
                  </label>
                </div>
              </div>
            </>
          )}

          {/* Preview / Result */}
          {exportedContent && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Preview</label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-muted transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        Copy
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleDownload}
                    className="flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-muted transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download
                  </button>
                </div>
              </div>
              <pre className="p-4 bg-muted rounded-lg text-xs overflow-auto max-h-60 font-mono">
                {exportedContent.slice(0, 2000)}
                {exportedContent.length > 2000 && "\n\n... (truncated)"}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md hover:bg-muted transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Export
              </>
            )}
          </button>
        </div>
      </div>
    </>
  )
}

// Helper function to download a blob
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Generate markdown content
function generateMarkdown(
  query: string,
  answer: string | null,
  results: Array<{
    id?: string
    content?: string
    text?: string
    metadata?: {
      title?: string
      source?: string
      url?: string
      page_number?: number
    }
    score?: number
  }>,
  messages: Array<{
    role: string
    content: string
    timestamp?: string
    ragContext?: {
      retrieved_documents?: Array<{
        title?: string
        excerpt?: string
        url?: string
      }>
    }
  }>,
  options: ExportOptions
): string {
  const lines: string[] = []

  // Header
  lines.push("# Knowledge QA Export")
  lines.push("")
  lines.push(`Generated: ${new Date().toLocaleString()}`)
  lines.push("")

  // Query
  lines.push("## Query")
  lines.push("")
  lines.push(`> ${query}`)
  lines.push("")

  // Answer
  if (answer) {
    lines.push("## Answer")
    lines.push("")
    lines.push(answer)
    lines.push("")
  }

  // Sources
  if (results.length > 0) {
    lines.push("## Sources")
    lines.push("")
    results.forEach((result, index) => {
      const title =
        result.metadata?.title || result.metadata?.source || `Source ${index + 1}`
      const url = result.metadata?.url
      const score = result.score
      const content = result.content || result.text || ""

      lines.push(`### [${index + 1}] ${title}`)
      lines.push("")
      if (url) {
        lines.push(`URL: ${url}`)
        lines.push("")
      }
      if (score !== undefined) {
        lines.push(`Relevance: ${Math.round(score * 100)}%`)
        lines.push("")
      }
      if (options.includeSourceExcerpts && content) {
        lines.push("**Excerpt:**")
        lines.push("")
        lines.push(`> ${content.slice(0, 500)}${content.length > 500 ? "..." : ""}`)
        lines.push("")
      }
    })
  }

  // Conversation history
  if (messages.length > 0) {
    lines.push("## Conversation History")
    lines.push("")
    messages.forEach((msg) => {
      const role = msg.role === "user" ? "User" : msg.role === "assistant" ? "Assistant" : msg.role
      lines.push(`**${role}:** ${msg.content}`)
      lines.push("")
    })
  }

  // Bibliography (formatted citations)
  if (results.length > 0) {
    lines.push("## Bibliography")
    lines.push("")
    results.forEach((result, index) => {
      const citation = formatCitation(result, index + 1, options.citationStyle)
      lines.push(citation)
      lines.push("")
    })
  }

  // Settings snapshot
  if (options.includeSettingsSnapshot) {
    lines.push("## Settings Used")
    lines.push("")
    lines.push("```json")
    lines.push(
      JSON.stringify(
        {
          format: options.format,
          citationStyle: options.citationStyle,
          exportDate: new Date().toISOString(),
        },
        null,
        2
      )
    )
    lines.push("```")
  }

  // Footer
  lines.push("")
  lines.push("---")
  lines.push("*Exported from Knowledge QA*")

  return lines.join("\n")
}

// Format a citation based on style
function formatCitation(
  result: {
    metadata?: {
      title?: string
      source?: string
      url?: string
      page_number?: number
    }
  },
  index: number,
  style: RagCitationStyle
): string {
  const title = result.metadata?.title || result.metadata?.source || "Untitled"
  const url = result.metadata?.url || ""
  const page = result.metadata?.page_number

  switch (style) {
    case "apa":
      return `[${index}] ${title}. ${url ? `Retrieved from ${url}` : ""}${page ? `, p. ${page}` : ""}`
    case "mla":
      return `[${index}] "${title}."${url ? ` Web. <${url}>.` : ""}${page ? ` ${page}.` : ""}`
    case "chicago":
      return `[${index}] ${title}.${url ? ` ${url}.` : ""}${page ? ` ${page}.` : ""}`
    case "harvard":
      return `[${index}] ${title}${url ? ` Available at: ${url}` : ""}${page ? ` (p. ${page})` : ""}`
    case "ieee":
      return `[${index}] ${title}${url ? `, [Online]. Available: ${url}` : ""}${page ? `, p. ${page}` : ""}.`
    default:
      return `[${index}] ${title}${url ? ` - ${url}` : ""}${page ? ` (p. ${page})` : ""}`
  }
}
