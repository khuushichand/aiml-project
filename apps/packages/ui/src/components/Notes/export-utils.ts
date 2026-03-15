import DOMPurify from "dompurify"
import { marked } from "marked"

export type SingleNoteExportData = {
  id?: string | number | null
  title: string
  content: string
  keywords: string[]
}

export type SingleNoteCopyMode = "content" | "markdown"
export type SingleNoteExportFormat = "md" | "json" | "print"

const normalizeKeywords = (keywords: string[]) =>
  keywords
    .map((keyword) => String(keyword || "").trim())
    .filter((keyword) => keyword.length > 0)

const escapeYamlString = (value: string) =>
  String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/\r/g, "\\r")
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t")
    .replace(/"/g, '\\"')

export const buildSingleNoteMarkdown = (note: SingleNoteExportData): string => {
  const title = String(note.title || "").trim()
  const content = String(note.content || "")
  const keywords = normalizeKeywords(note.keywords || [])

  const heading = title ? `# ${title}\n\n` : ""
  if (keywords.length === 0) {
    return `${heading}${content}`.trimEnd()
  }

  const frontmatter = [
    "---",
    ...(title ? [`title: "${escapeYamlString(title)}"`] : []),
    "keywords:",
    ...keywords.map((keyword) => `  - "${escapeYamlString(keyword)}"`),
    "---",
    ""
  ].join("\n")

  return `${frontmatter}\n${heading}${content}`.trimEnd()
}

export const buildSingleNoteJson = (note: SingleNoteExportData): string =>
  JSON.stringify(
    {
      id: note.id ?? null,
      title: String(note.title || ""),
      content: String(note.content || ""),
      keywords: normalizeKeywords(note.keywords || [])
    },
    null,
    2
  )

export const buildSingleNoteCopyText = (
  note: SingleNoteExportData,
  mode: SingleNoteCopyMode
): string => {
  if (mode === "markdown") {
    return buildSingleNoteMarkdown(note)
  }
  return String(note.content || "")
}

const escapeHtml = (value: string) =>
  String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")

const renderPrintableMarkdownHtml = (markdown: string): string => {
  const rendered = marked.parse(markdown, {
    gfm: true,
    breaks: true
  })
  const html = typeof rendered === "string" ? rendered : String(markdown || "")
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true }
  })
}

export const SINGLE_NOTE_PRINT_STYLES = `
    body {
      margin: 0;
      font-family: "Helvetica Neue", Arial, sans-serif;
      color: #111827;
      background: #ffffff;
    }
    .print-shell {
      max-width: 860px;
      margin: 0 auto;
      padding: 24px;
    }
    .note-header {
      border-bottom: 1px solid #d1d5db;
      margin-bottom: 16px;
      padding-bottom: 12px;
    }
    .note-header h1 {
      margin: 0 0 8px 0;
      font-size: 28px;
      line-height: 1.2;
    }
    .meta-row {
      margin: 4px 0;
      color: #4b5563;
      font-size: 13px;
      line-height: 1.4;
    }
    .note-body {
      color: #111827;
      font-size: 15px;
      line-height: 1.65;
      word-break: break-word;
    }
    .note-body img {
      max-width: 100%;
      height: auto;
    }
    .note-body pre {
      overflow-x: auto;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      background: #f9fafb;
      padding: 10px;
    }
    .note-body blockquote {
      margin-left: 0;
      padding-left: 12px;
      border-left: 3px solid #d1d5db;
      color: #374151;
    }
    @media print {
      body {
        margin: 0;
      }
      .print-shell {
        max-width: none;
        padding: 12mm;
      }
      .note-header,
      .note-body pre,
      .note-body blockquote {
        break-inside: avoid;
        page-break-inside: avoid;
      }
      a {
        color: inherit;
        text-decoration: underline;
      }
    }
  `

export const buildSingleNotePrintableHtml = (
  note: SingleNoteExportData,
  options?: {
    generatedAtIso?: string
  }
): string => {
  const title = String(note.title || "").trim()
  const content = String(note.content || "")
  const keywords = normalizeKeywords(note.keywords || [])
  const printableTitle = title || "Untitled note"
  const generatedAtIso = String(options?.generatedAtIso || new Date().toISOString())

  const markdownSource = title
    ? `# ${title}\n\n${content}`
    : (content || "_(Empty note)_")
  const renderedContent = renderPrintableMarkdownHtml(markdownSource)
  const keywordsMarkup =
    keywords.length > 0
      ? `<p class="meta-row"><strong>Keywords:</strong> ${escapeHtml(keywords.join(", "))}</p>`
      : ""

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(printableTitle)} - Printable Note</title>
  <style>
  ${SINGLE_NOTE_PRINT_STYLES}
  </style>
</head>
<body>
  <div class="print-shell">
    <header class="note-header">
      <h1>${escapeHtml(printableTitle)}</h1>
      <p class="meta-row"><strong>Exported:</strong> ${escapeHtml(generatedAtIso)}</p>
      ${keywordsMarkup}
    </header>
    <main class="note-body">
      ${renderedContent}
    </main>
  </div>
</body>
</html>`
}
