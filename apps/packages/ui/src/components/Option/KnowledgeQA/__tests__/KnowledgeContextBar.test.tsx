import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { KnowledgeContextBar } from "../context/KnowledgeContextBar"

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    listMedia: vi.fn().mockResolvedValue({ items: [] }),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}))

describe("KnowledgeContextBar", () => {
  it("shows inline preset descriptions for active mode", () => {
    const { rerender } = render(
      <KnowledgeContextBar
        preset="fast"
        onPresetChange={vi.fn()}
        sources={["media_db"]}
        onSourcesChange={vi.fn()}
        includeMediaIds={[]}
        onIncludeMediaIdsChange={vi.fn()}
        includeNoteIds={[]}
        onIncludeNoteIdsChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    expect(
      screen.getByText(
        "Quick lookup with minimal retrieval and rerank depth. Speed: Fastest. Coverage: Lower. Best for: Fact checks and quick lookups."
      )
    ).toBeInTheDocument()

    rerender(
      <KnowledgeContextBar
        preset="thorough"
        onPresetChange={vi.fn()}
        sources={["media_db"]}
        onSourcesChange={vi.fn()}
        includeMediaIds={[]}
        onIncludeMediaIdsChange={vi.fn()}
        includeNoteIds={[]}
        onIncludeNoteIdsChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    expect(
      screen.getByText(
        "Exhaustive retrieval plus extra verification steps. Speed: Slowest. Coverage: Highest. Best for: High-confidence synthesis."
      )
    ).toBeInTheDocument()
  })

  it("lets users update source scope from the dropdown", () => {
    const onSourcesChange = vi.fn()
    render(
      <KnowledgeContextBar
        preset="balanced"
        onPresetChange={vi.fn()}
        sources={[]}
        onSourcesChange={onSourcesChange}
        includeMediaIds={[]}
        onIncludeMediaIdsChange={vi.fn()}
        includeNoteIds={[]}
        onIncludeNoteIdsChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Sources:/i }))
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Docs & Media" }))

    expect(onSourcesChange).toHaveBeenCalledWith(["media_db"])
  })

  it("lets users select granular media sources", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValueOnce({
      items: [{ id: 42, title: "Quarterly Planning Doc", type: "pdf" }],
    })
    vi.mocked(tldwClient.listNotes).mockResolvedValueOnce({ items: [] })

    const onIncludeMediaIdsChange = vi.fn()
    render(
      <KnowledgeContextBar
        preset="balanced"
        onPresetChange={vi.fn()}
        sources={["media_db", "notes"]}
        onSourcesChange={vi.fn()}
        includeMediaIds={[]}
        onIncludeMediaIdsChange={onIncludeMediaIdsChange}
        includeNoteIds={[]}
        onIncludeNoteIdsChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Specific:/i }))
    expect(await screen.findByText("Quarterly Planning Doc")).toBeInTheDocument()

    fireEvent.click(screen.getByText("Quarterly Planning Doc"))

    expect(onIncludeMediaIdsChange).toHaveBeenCalledWith([42])
  })
})
