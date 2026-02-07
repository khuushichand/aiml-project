import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { HighlightCard } from "../HighlightCard"
import type { Highlight } from "@/types/collections"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

const baseHighlight: Highlight = {
  id: "1",
  item_id: "10",
  item_title: "Example article",
  quote: "Selected quote",
  note: "Example note",
  color: "yellow",
  state: "active",
  anchor_strategy: "fuzzy_quote",
  created_at: "2026-01-01T00:00:00Z"
}

describe("HighlightCard", () => {
  it("shows stale badge when highlight state is stale", () => {
    render(
      <HighlightCard
        highlight={{ ...baseHighlight, state: "stale" }}
        onDelete={vi.fn()}
      />
    )

    expect(screen.getByText("Stale")).toBeInTheDocument()
  })

  it("fires edit and delete actions", () => {
    const onDelete = vi.fn()
    const onEdit = vi.fn()
    render(
      <HighlightCard
        highlight={baseHighlight}
        onDelete={onDelete}
        onEdit={onEdit}
      />
    )

    fireEvent.click(screen.getByLabelText("Edit"))
    fireEvent.click(screen.getByLabelText("Delete"))

    expect(onEdit).toHaveBeenCalledWith(baseHighlight)
    expect(onDelete).toHaveBeenCalledWith("1")
  })
})
