import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SourceCitations } from "../SourceCitations"

describe("SourceCitations", () => {
  it("renders media deep links using citation metadata", () => {
    render(
      <SourceCitations
        citations={[
          {
            label: "Transcript snippet",
            quote: "Cells use ATP as energy.",
            media_id: 42,
            chunk_id: "chunk-7",
            timestamp_seconds: 61.9
          }
        ]}
      />
    )

    const link = screen.getByRole("link", { name: "Transcript snippet" })
    expect(link).toHaveAttribute("href", "/media?id=42&chunk_id=chunk-7&t=61")
    expect(screen.getByText(/Cells use ATP as energy\./)).toBeInTheDocument()
  })

  it("uses direct source_url when safe", () => {
    render(
      <SourceCitations
        citations={[
          {
            label: "Article",
            source_url: "https://example.com/source"
          }
        ]}
      />
    )

    expect(screen.getByRole("link", { name: "Article" })).toHaveAttribute(
      "href",
      "https://example.com/source"
    )
  })

  it("rejects unsafe source_url schemes and falls back to media link", () => {
    render(
      <SourceCitations
        fallbackMediaId={88}
        citations={[
          {
            label: "Unsafe URL",
            source_url: "javascript:alert(1)"
          }
        ]}
      />
    )

    expect(screen.getByRole("link", { name: "Unsafe URL" })).toHaveAttribute(
      "href",
      "/media?id=88"
    )
  })

  it("renders plain text when no resolvable link is available", () => {
    render(
      <SourceCitations
        citations={[
          {
            label: "No link citation"
          }
        ]}
      />
    )

    expect(screen.getByText("No link citation")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "No link citation" })).not.toBeInTheDocument()
  })
})
