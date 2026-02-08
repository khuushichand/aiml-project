import React from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { SourceChunksList } from "../SourceChunksList"
import type { QADocument } from "../../hooks/useQASearch"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string, vars?: Record<string, unknown>) => {
      if (fallback && typeof vars?.count === "number") {
        return fallback.replace("{{count}}", String(vars.count))
      }
      return fallback ?? _key
    }
  })
}))

describe("SourceChunksList", () => {
  const documents: QADocument[] = [
    {
      content: "Beta content",
      score: 0.4,
      metadata: { title: "Beta Doc", source: "beta.pdf", type: "pdf" }
    },
    {
      content: "Alpha content",
      score: 0.95,
      metadata: { title: "Alpha Doc", source: "alpha.pdf", type: "pdf" }
    },
    {
      content: "Gamma content",
      score: 0.95,
      metadata: { title: "Gamma Doc", source: "gamma.pdf", type: "pdf" }
    }
  ]

  it("sorts deterministically by relevance by default and supports source sorting", () => {
    render(
      <SourceChunksList
        documents={documents}
        pinnedResults={[]}
        onCopy={vi.fn()}
        onInsert={vi.fn()}
        onPin={vi.fn()}
      />
    )

    const initialItems = screen.getAllByRole("listitem")
    expect(initialItems[0]).toHaveTextContent("Alpha Doc")
    expect(initialItems[1]).toHaveTextContent("Gamma Doc")
    expect(initialItems[2]).toHaveTextContent("Beta Doc")

    fireEvent.click(screen.getByRole("button", { name: "Source" }))

    const sourceSortedItems = screen.getAllByRole("listitem")
    expect(sourceSortedItems[0]).toHaveTextContent("Alpha Doc")
    expect(sourceSortedItems[1]).toHaveTextContent("Beta Doc")
    expect(sourceSortedItems[2]).toHaveTextContent("Gamma Doc")
  })

  it("keeps copy/insert/pin actions mapped to the correct document after sorting", () => {
    const onCopy = vi.fn()
    const onInsert = vi.fn()
    const onPin = vi.fn()

    render(
      <SourceChunksList
        documents={documents}
        pinnedResults={[]}
        onCopy={onCopy}
        onInsert={onInsert}
        onPin={onPin}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Source" }))

    const firstItem = screen.getAllByRole("listitem")[0]
    const firstItemScope = within(firstItem)
    fireEvent.click(firstItemScope.getByRole("button", { name: "Copy" }))
    fireEvent.click(firstItemScope.getByRole("button", { name: "Insert" }))
    fireEvent.click(firstItemScope.getByRole("button", { name: "Pin" }))

    expect(onCopy).toHaveBeenCalledTimes(1)
    expect(onInsert).toHaveBeenCalledTimes(1)
    expect(onPin).toHaveBeenCalledTimes(1)
    expect(onCopy).toHaveBeenCalledWith(
      expect.objectContaining({
        metadata: expect.objectContaining({ title: "Alpha Doc" })
      })
    )
    expect(onInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        metadata: expect.objectContaining({ title: "Alpha Doc" })
      })
    )
    expect(onPin).toHaveBeenCalledWith(
      expect.objectContaining({
        metadata: expect.objectContaining({ title: "Alpha Doc" })
      })
    )
  })
})
