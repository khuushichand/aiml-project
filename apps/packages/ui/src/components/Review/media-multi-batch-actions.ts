export type MediaMultiBatchExportFormat = "json" | "markdown" | "text"

export type MediaMultiBatchExportItem = {
  id: string | number
  title: string
  snippet: string
  type: string | null
  created_at: string | null
  keywords: string[]
  content: string
  analysis: string
}

export const parseBatchKeywords = (draft: string): string[] => {
  const seen = new Set<string>()
  const next: string[] = []
  for (const token of String(draft || "").split(/[\n,]/g)) {
    const trimmed = token.trim()
    if (!trimmed) continue
    const key = trimmed.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    next.push(trimmed)
  }
  return next
}

export const buildBatchExportArtifact = (
  items: MediaMultiBatchExportItem[],
  format: MediaMultiBatchExportFormat
): { content: string; extension: "json" | "md" | "txt"; mimeType: string } => {
  const exportedAt = new Date().toISOString()

  if (format === "markdown") {
    const lines: string[] = [
      "# Media Multi Export",
      "",
      `Exported at: ${exportedAt}`,
      `Items: ${items.length}`,
      ""
    ]
    for (const item of items) {
      lines.push(`## ${item.title}`)
      lines.push(`- ID: ${item.id}`)
      if (item.type) lines.push(`- Type: ${item.type}`)
      if (item.created_at) lines.push(`- Created: ${item.created_at}`)
      if (item.keywords.length > 0) lines.push(`- Keywords: ${item.keywords.join(", ")}`)
      if (item.snippet) {
        lines.push("", "### Snippet", item.snippet)
      }
      if (item.content) {
        lines.push("", "### Content", item.content)
      }
      if (item.analysis) {
        lines.push("", "### Analysis", item.analysis)
      }
      lines.push("")
    }
    return {
      content: lines.join("\n"),
      extension: "md",
      mimeType: "text/markdown"
    }
  }

  if (format === "text") {
    const lines: string[] = [
      "Media Multi Export",
      `Exported at: ${exportedAt}`,
      `Items: ${items.length}`,
      ""
    ]
    for (const item of items) {
      lines.push(`${item.title} [#${item.id}]`)
      if (item.type) lines.push(`Type: ${item.type}`)
      if (item.created_at) lines.push(`Created: ${item.created_at}`)
      if (item.keywords.length > 0) lines.push(`Keywords: ${item.keywords.join(", ")}`)
      if (item.snippet) lines.push(`Snippet: ${item.snippet}`)
      if (item.content) lines.push(`Content: ${item.content}`)
      if (item.analysis) lines.push(`Analysis: ${item.analysis}`)
      lines.push("")
    }
    return {
      content: lines.join("\n"),
      extension: "txt",
      mimeType: "text/plain"
    }
  }

  return {
    content: JSON.stringify(
      {
        exported_at: exportedAt,
        item_count: items.length,
        items
      },
      null,
      2
    ),
    extension: "json",
    mimeType: "application/json"
  }
}
