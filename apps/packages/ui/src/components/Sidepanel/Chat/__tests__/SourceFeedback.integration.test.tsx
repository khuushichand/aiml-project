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

vi.mock("@/components/Common/Playground/MessageSource", () => ({
  MessageSource: ({
    source,
    onSourceClick,
    onOpenKnowledgePanel
  }: {
    source: any
    onSourceClick?: (payload: any) => void
    onOpenKnowledgePanel?: () => void
  }) => (
    <div>
      <button type="button" onClick={() => onSourceClick?.(source)}>
        Open source
      </button>
      <button type="button" onClick={() => onOpenKnowledgePanel?.()}>
        Open Search & Context
      </button>
    </div>
  )
}))

describe("SourceFeedback citation workflow integration", () => {
  it("shows pinned usage badge and wires ask/open actions", async () => {
    const user = userEvent.setup()
    const onAskWithSource = vi.fn()
    const onOpenKnowledgePanel = vi.fn()
    const onSourceClick = vi.fn()

    render(
      <SourceFeedback
        source={{
          name: "Source A",
          content: "Evidence snippet"
        }}
        sourceKey="source-a"
        pinnedState="active"
        onAskWithSource={onAskWithSource}
        onOpenKnowledgePanel={onOpenKnowledgePanel}
        onSourceClick={onSourceClick}
      />
    )

    expect(screen.getByText("Pinned: used")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Ask with this source" }))
    await user.click(screen.getByRole("button", { name: "Open Search & Context" }))
    await user.click(screen.getByRole("button", { name: "Open source" }))

    expect(onAskWithSource).toHaveBeenCalledTimes(1)
    expect(onOpenKnowledgePanel).toHaveBeenCalledTimes(1)
    expect(onSourceClick).toHaveBeenCalledTimes(1)
  })
})
