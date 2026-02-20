import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { KnowledgeContextBar } from "../context/KnowledgeContextBar"

describe("KnowledgeContextBar", () => {
  it("shows inline preset descriptions for active mode", () => {
    const { rerender } = render(
      <KnowledgeContextBar
        preset="fast"
        onPresetChange={vi.fn()}
        sources={["media_db"]}
        onSourcesChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    expect(
      screen.getByText("Fast: Quick lookup with fewer retrieval steps.")
    ).toBeInTheDocument()

    rerender(
      <KnowledgeContextBar
        preset="thorough"
        onPresetChange={vi.fn()}
        sources={["media_db"]}
        onSourcesChange={vi.fn()}
        webEnabled={true}
        onToggleWeb={vi.fn()}
        contextChangedSinceLastRun={false}
        onOpenSettings={vi.fn()}
      />
    )

    expect(
      screen.getByText(
        "Deep: Exhaustive retrieval and verification, slower runtime."
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
})
