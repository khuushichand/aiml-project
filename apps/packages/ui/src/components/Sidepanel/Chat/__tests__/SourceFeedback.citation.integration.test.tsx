// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { SourceFeedback } from "../SourceFeedback"

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

describe("SourceFeedback citation-card integration", () => {
  it("keeps citation transparency details and workflow actions wired", async () => {
    const user = userEvent.setup()
    const onSourceClick = vi.fn()
    const onTrackClick = vi.fn()
    const onRate = vi.fn()
    const onAskWithSource = vi.fn()
    const onOpenKnowledgePanel = vi.fn()

    render(
      <SourceFeedback
        source={{
          name: "Policy Note A",
          content: "Evidence excerpt used in the response",
          score: 0.84,
          metadata: {
            chunk_id: "chunk_1_of_4",
            retrieval_strategy: "hybrid",
            source_type: "notes",
            reason: "High lexical overlap with user question"
          }
        }}
        sourceKey="policy-note-a"
        pinnedState="active"
        onRate={onRate}
        onSourceClick={onSourceClick}
        onTrackClick={onTrackClick}
        onAskWithSource={onAskWithSource}
        onOpenKnowledgePanel={onOpenKnowledgePanel}
      />
    )

    expect(screen.getByText("Pinned: used")).toBeInTheDocument()

    await user.click(screen.getByText("Policy Note A"))
    expect(onSourceClick).toHaveBeenCalledTimes(1)
    expect(onTrackClick).toHaveBeenCalledTimes(1)
    expect(screen.getByText("Why this source")).toBeInTheDocument()
    expect(screen.getByText("Relevance:")).toBeInTheDocument()
    expect(screen.getByText("84%")).toBeInTheDocument()
    expect(screen.getByText("chunk_1_of_4")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Ask with this source" }))
    await user.click(
      screen.getByRole("button", { name: "Open Search & Context" })
    )
    await user.click(screen.getByRole("button", { name: "Helpful source" }))

    expect(onAskWithSource).toHaveBeenCalledTimes(1)
    expect(onOpenKnowledgePanel).toHaveBeenCalledTimes(1)
    expect(onRate).toHaveBeenCalledWith(
      "policy-note-a",
      expect.any(Object),
      "up"
    )
  })
})
