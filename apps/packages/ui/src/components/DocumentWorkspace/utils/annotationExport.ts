import type { Annotation, DocumentType } from "../types"

/**
 * Export format options
 */
export type ExportFormat = "markdown" | "json" | "text"

/**
 * Format annotation location for display
 */
function formatLocation(
  annotation: Annotation,
  documentType: DocumentType | null
): string {
  if (documentType === "epub") {
    if (annotation.chapterTitle) {
      return annotation.chapterTitle
    }
    if (annotation.percentage !== undefined) {
      return `${Math.round(annotation.percentage)}%`
    }
    return "Location"
  }
  return `Page ${annotation.location}`
}

/**
 * Format date for export
 */
function formatDate(date: Date): string {
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  })
}

/**
 * Export annotations to Markdown format
 */
export function exportToMarkdown(
  annotations: Annotation[],
  docTitle: string,
  documentType: DocumentType | null
): string {
  let md = `# Annotations: ${docTitle}\n\n`
  md += `*Exported on ${formatDate(new Date())}*\n\n`
  md += `---\n\n`

  // Group by annotation type
  const highlights = annotations.filter((a) => a.annotationType !== "page_note")
  const notes = annotations.filter((a) => a.annotationType === "page_note")

  if (highlights.length > 0) {
    md += `## Highlights (${highlights.length})\n\n`
    highlights.forEach((ann) => {
      const location = formatLocation(ann, documentType)
      const colorEmoji = getColorEmoji(ann.color)

      md += `### ${colorEmoji} ${location}\n\n`
      md += `> ${ann.text}\n\n`

      if (ann.note) {
        md += `**Note:** ${ann.note}\n\n`
      }

      md += `*${formatDate(ann.createdAt)}*\n\n`
      md += `---\n\n`
    })
  }

  if (notes.length > 0) {
    md += `## Notes (${notes.length})\n\n`
    notes.forEach((ann) => {
      const location = formatLocation(ann, documentType)

      md += `### ${location}\n\n`
      md += `${ann.note || ann.text}\n\n`
      md += `*${formatDate(ann.createdAt)}*\n\n`
      md += `---\n\n`
    })
  }

  return md
}

/**
 * Export annotations to JSON format
 */
export function exportToJSON(
  annotations: Annotation[],
  docTitle: string,
  documentType: DocumentType | null
): string {
  const exportData = {
    title: docTitle,
    documentType,
    exportedAt: new Date().toISOString(),
    annotationCount: annotations.length,
    annotations: annotations.map((ann) => ({
      id: ann.id,
      type: ann.annotationType || "highlight",
      location: ann.location,
      locationLabel: formatLocation(ann, documentType),
      text: ann.text,
      note: ann.note || null,
      color: ann.color,
      chapterTitle: ann.chapterTitle || null,
      percentage: ann.percentage ?? null,
      createdAt: ann.createdAt,
      updatedAt: ann.updatedAt
    }))
  }

  return JSON.stringify(exportData, null, 2)
}

/**
 * Export annotations to plain text format
 */
export function exportToText(
  annotations: Annotation[],
  docTitle: string,
  documentType: DocumentType | null
): string {
  let text = `Annotations: ${docTitle}\n`
  text += `${"=".repeat(50)}\n`
  text += `Exported on ${formatDate(new Date())}\n\n`

  annotations.forEach((ann, index) => {
    const location = formatLocation(ann, documentType)
    const type = ann.annotationType === "page_note" ? "Note" : "Highlight"
    const color = ann.color.charAt(0).toUpperCase() + ann.color.slice(1)

    text += `${index + 1}. [${type}] [${color}] ${location}\n`
    text += `-`.repeat(40) + `\n`

    if (ann.annotationType !== "page_note") {
      text += `"${ann.text}"\n`
    }

    if (ann.note) {
      text += `Note: ${ann.note}\n`
    }

    text += `Created: ${formatDate(ann.createdAt)}\n`
    text += `\n`
  })

  return text
}

/**
 * Get emoji for annotation color
 */
function getColorEmoji(color: string): string {
  switch (color) {
    case "yellow":
      return "\uD83D\uDFE1"
    case "green":
      return "\uD83D\uDFE2"
    case "blue":
      return "\uD83D\uDD35"
    case "pink":
      return "\uD83D\uDFE3"
    default:
      return "\u2B24"
  }
}

/**
 * Get file extension for export format
 */
export function getFileExtension(format: ExportFormat): string {
  switch (format) {
    case "markdown":
      return "md"
    case "json":
      return "json"
    case "text":
      return "txt"
  }
}

/**
 * Get MIME type for export format
 */
export function getMimeType(format: ExportFormat): string {
  switch (format) {
    case "markdown":
      return "text/markdown"
    case "json":
      return "application/json"
    case "text":
      return "text/plain"
  }
}

/**
 * Export annotations to the specified format
 */
export function exportAnnotations(
  annotations: Annotation[],
  docTitle: string,
  documentType: DocumentType | null,
  format: ExportFormat
): string {
  switch (format) {
    case "markdown":
      return exportToMarkdown(annotations, docTitle, documentType)
    case "json":
      return exportToJSON(annotations, docTitle, documentType)
    case "text":
      return exportToText(annotations, docTitle, documentType)
  }
}

/**
 * Download annotations as a file
 */
export function downloadAnnotations(
  annotations: Annotation[],
  docTitle: string,
  documentType: DocumentType | null,
  format: ExportFormat
): void {
  const content = exportAnnotations(annotations, docTitle, documentType, format)
  const mimeType = getMimeType(format)
  const extension = getFileExtension(format)

  // Sanitize filename
  const safeTitle = docTitle
    .replace(/[^a-z0-9]/gi, "_")
    .replace(/_+/g, "_")
    .substring(0, 50)

  const filename = `annotations_${safeTitle}.${extension}`

  // Create and trigger download
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
