import { describe, expect, it } from "vitest"
import {
  buildSingleNoteCopyText,
  buildSingleNoteJson,
  buildSingleNoteMarkdown,
  buildSingleNotePrintableHtml,
  SINGLE_NOTE_PRINT_STYLES
} from "../export-utils"

describe("notes export utils", () => {
  it("builds markdown with keyword frontmatter when keywords are present", () => {
    const markdown = buildSingleNoteMarkdown({
      id: 7,
      title: "Research Note",
      content: "Body text",
      keywords: ["research", "ml"]
    })

    expect(markdown).toContain("---")
    expect(markdown).toContain('keywords:\n  - "research"\n  - "ml"')
    expect(markdown).toContain("# Research Note")
    expect(markdown).toContain("Body text")
  })

  it("escapes backslashes and control characters in YAML frontmatter values", () => {
    const markdown = buildSingleNoteMarkdown({
      id: 8,
      title: 'Path "C:\\notes\\today"\nline',
      content: "Body",
      keywords: ['team\\alpha', 'line\nbreak']
    })

    expect(markdown).toContain('title: "Path \\"C:\\\\notes\\\\today\\"\\nline"')
    expect(markdown).toContain('  - "team\\\\alpha"')
    expect(markdown).toContain('  - "line\\nbreak"')
  })

  it("builds normalized single-note JSON payload", () => {
    const payload = buildSingleNoteJson({
      id: "n-1",
      title: "Json note",
      content: "Some content",
      keywords: ["alpha", " beta "]
    })
    expect(payload).toContain('"id": "n-1"')
    expect(payload).toContain('"title": "Json note"')
    expect(payload).toContain('"keywords": [\n    "alpha",\n    "beta"\n  ]')
  })

  it("supports content-only and markdown copy modes", () => {
    const note = {
      id: 9,
      title: "Copy note",
      content: "Copy content",
      keywords: ["tag"]
    }
    expect(buildSingleNoteCopyText(note, "content")).toBe("Copy content")
    expect(buildSingleNoteCopyText(note, "markdown")).toContain("# Copy note")
  })

  it("builds printable html with sanitized markdown content and metadata", () => {
    const html = buildSingleNotePrintableHtml(
      {
        id: 11,
        title: "Printable <Note>",
        content: "Paragraph with **bold** and <script>alert('x')</script>",
        keywords: ["research", "summary"]
      },
      {
        generatedAtIso: "2026-02-18T00:00:00.000Z"
      }
    )

    expect(html).toContain("Printable &lt;Note&gt;")
    expect(html).toContain("<strong>bold</strong>")
    expect(html).toContain("Keywords:</strong> research, summary")
    expect(html).toContain("2026-02-18T00:00:00.000Z")
    expect(html).not.toContain("<script>")
  })

  it("ships a dedicated print stylesheet for note exports", () => {
    expect(SINGLE_NOTE_PRINT_STYLES).toMatchInlineSnapshot(`
      "
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
        "
    `)
  })
})
