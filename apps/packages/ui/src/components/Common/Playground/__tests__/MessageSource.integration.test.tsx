// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { MessageSource } from "../MessageSource"

vi.mock("@/components/Option/Knowledge/KnowledgeIcon", () => ({
  KnowledgeIcon: ({ className }: { className?: string }) => (
    <span data-testid="knowledge-icon" className={className} />
  )
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

describe("MessageSource citation transparency integration", () => {
  it("shows why-this-source diagnostics and opens knowledge panel from citation card", async () => {
    const user = userEvent.setup()
    const onOpenKnowledgePanel = vi.fn()

    render(
      <MessageSource
        source={{
          name: "Doc A",
          content: "Quoted snippet",
          score: 0.91,
          metadata: {
            chunk_id: "chunk_2_of_9",
            retrieval_strategy: "hybrid",
            source_type: "media_db",
            reason: "High lexical overlap"
          }
        }}
        onOpenKnowledgePanel={onOpenKnowledgePanel}
      />
    )

    await user.click(screen.getByText("Doc A"))

    expect(screen.getByText("Why this source")).toBeInTheDocument()
    expect(screen.getByText("Relevance:")).toBeInTheDocument()
    expect(screen.getByText("91%")).toBeInTheDocument()
    expect(screen.getByText("Chunk:")).toBeInTheDocument()
    expect(screen.getByText("chunk_2_of_9")).toBeInTheDocument()

    await user.click(
      screen.getByRole("button", { name: "Open Search & Context" })
    )
    expect(onOpenKnowledgePanel).toHaveBeenCalledTimes(1)
  })
})
