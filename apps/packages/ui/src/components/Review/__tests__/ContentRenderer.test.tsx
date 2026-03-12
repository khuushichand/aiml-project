import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ContentRenderer, detectContentType } from "../ContentRenderer"

vi.mock("@/components/Common/Markdown", () => ({
  Markdown: ({ message, searchQuery }: { message: string; searchQuery?: string }) => (
    <div data-testid="mock-markdown" data-search={searchQuery}>
      {message}
    </div>
  )
}))

vi.mock("@/utils/media-transcript-display", () => ({
  hasLeadingTranscriptTimings: (content: string) =>
    /^\s*\[\d{1,2}:\d{2}(:\d{2})?\]/.test(content),
  stripLeadingTranscriptTimings: (content: string) =>
    content.replace(/^\s*\[\d{1,2}:\d{2}(:\d{2})?\]\s*/gm, "")
}))

describe("detectContentType", () => {
  it("returns 'plain' for empty content", () => {
    expect(detectContentType("")).toBe("plain")
    expect(detectContentType("  ")).toBe("plain")
  })

  it("detects markdown with headings and bold", () => {
    const md = "# Title\n\nSome **bold** text\n\n- list item"
    expect(detectContentType(md)).toBe("markdown")
  })

  it("detects transcript content", () => {
    const transcript = "[00:00:05] Hello world\n[00:01:30] Next segment"
    expect(detectContentType(transcript)).toBe("transcript")
  })

  it("detects code content", () => {
    const code = "import React from 'react'\nconst x = 1;\nif (x) {\n  return x\n}"
    expect(detectContentType(code)).toBe("code")
  })

  it("returns 'plain' for simple text", () => {
    expect(detectContentType("Just some plain text here.")).toBe("plain")
  })
})

describe("ContentRenderer", () => {
  it("renders plain text with whitespace-pre-wrap", () => {
    render(<ContentRenderer content="Hello world" />)
    expect(screen.getByTestId("content-renderer-plain")).toHaveTextContent("Hello world")
  })

  it("renders markdown via Markdown component", () => {
    render(<ContentRenderer content="# Heading\n\n**Bold** and [link](url)" />)
    expect(screen.getByTestId("content-renderer-markdown")).toBeInTheDocument()
    expect(screen.getByTestId("mock-markdown")).toBeInTheDocument()
  })

  it("renders code wrapped in code fence", () => {
    render(<ContentRenderer content="import foo from 'bar'\nconst x = 1;\nif (x) {\n  return\n}" />)
    expect(screen.getByTestId("content-renderer-code")).toBeInTheDocument()
  })

  it("passes searchQuery to Markdown component", () => {
    render(<ContentRenderer content="# Hello\n\n**world**" searchQuery="world" />)
    const md = screen.getByTestId("mock-markdown")
    expect(md).toHaveAttribute("data-search", "world")
  })

  it("respects explicit contentType override", () => {
    render(<ContentRenderer content="plain text" contentType="markdown" />)
    expect(screen.getByTestId("content-renderer-markdown")).toBeInTheDocument()
  })

  it("strips transcript timings when hideTranscriptTimings is true", () => {
    render(
      <ContentRenderer
        content="[00:00:05] Hello world"
        hideTranscriptTimings={true}
      />
    )
    // Content type is still transcript, rendered via Markdown but with timings stripped
    const el = screen.getByTestId("content-renderer-transcript")
    const md = screen.getByTestId("mock-markdown")
    expect(md.textContent).not.toContain("[00:00:05]")
    expect(md.textContent).toContain("Hello world")
  })
})
