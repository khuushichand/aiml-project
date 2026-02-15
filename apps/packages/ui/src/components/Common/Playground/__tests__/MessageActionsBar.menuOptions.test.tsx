import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MessageActionsBar } from "../MessageActionsBar"

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Popover: ({
    children,
    content
  }: {
    children: React.ReactNode
    content?: React.ReactNode
  }) => (
    <>
      {children}
      {content}
    </>
  )
}))

const baseProps = () =>
  ({
    t: ((key: string, fallback?: string) => fallback || key) as any,
    isProMode: false,
    isBot: true,
    showVariantPager: false,
    resolvedVariantIndex: 0,
    variantCount: 1,
    canSwipePrev: false,
    canSwipeNext: false,
    overflowChipVisibility: "hidden",
    actionRowVisibility: "flex",
    isTtsEnabled: false,
    isSpeaking: false,
    onToggleTts: vi.fn(),
    copyPressed: false,
    onCopy: vi.fn(),
    canReply: false,
    onReply: vi.fn(),
    canSaveToNotes: false,
    canSaveToFlashcards: false,
    canGenerateDocument: false,
    onGenerateDocument: vi.fn(),
    onSaveKnowledge: vi.fn(),
    savingKnowledge: null,
    isLastMessage: true,
    onRegenerate: vi.fn(),
    onEdit: vi.fn(),
    editMode: false,
    showFeedbackControls: false,
    feedbackDisabled: false,
    feedbackDisabledReason: "",
    isFeedbackSubmitting: false,
    showThanks: false,
    onThumbUp: vi.fn(),
    onThumbDown: vi.fn(),
    onOpenDetails: vi.fn()
  }) satisfies React.ComponentProps<typeof MessageActionsBar>

describe("MessageActionsBar menu options", () => {
  it("keeps New Branch available even when temporary chat is enabled", () => {
    render(
      <MessageActionsBar
        {...baseProps()}
        temporaryChat
        onNewBranch={vi.fn()}
      />
    )

    expect(screen.getByText("New Branch")).toBeInTheDocument()
  })

  it("keeps Generate document available when enabled in bot menu", () => {
    render(
      <MessageActionsBar
        {...baseProps()}
        temporaryChat
        canGenerateDocument
      />
    )

    expect(screen.getByText("Generate document")).toBeInTheDocument()
  })
})
