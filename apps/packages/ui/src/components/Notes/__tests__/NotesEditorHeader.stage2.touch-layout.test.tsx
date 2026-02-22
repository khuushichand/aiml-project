import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import NotesEditorHeader from "../NotesEditorHeader"

const responsiveState = vi.hoisted(() => ({
  isMobile: false
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => responsiveState.isMobile
}))

const renderHeader = () =>
  render(
    <NotesEditorHeader
      title="Stage 2 note"
      selectedId="note-1"
      backlinkConversationId={null}
      backlinkConversationLabel={null}
      backlinkMessageId={null}
      sourceLinks={[]}
      editorDisabled={false}
      openingLinkedChat={false}
      editorMode="edit"
      hasContent
      canSave
      canGenerateFlashcards
      canExport
      isSaving={false}
      canDelete
      isDirty={false}
      onOpenLinkedConversation={() => undefined}
      onOpenSourceLink={() => undefined}
      onNewNote={() => undefined}
      onChangeEditorMode={() => undefined}
      onCopy={() => undefined}
      onGenerateFlashcards={() => undefined}
      onExport={() => undefined}
      onSave={() => undefined}
      onDelete={() => undefined}
    />
  )

describe("NotesEditorHeader stage 2 touch layout", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("uses wrapped toolbar layout and 44px touch targets on mobile", () => {
    responsiveState.isMobile = true
    renderHeader()

    const actions = screen.getByTestId("notes-header-actions")
    expect(actions.className).toContain("w-full")
    expect(actions.className).toContain("flex-wrap")

    const saveButton = screen.getByTestId("notes-save-button")
    const newButton = screen.getByTestId("notes-new-button")
    const deleteButton = screen.getByTestId("notes-delete-button")
    const copyButton = screen.getByTestId("notes-copy-button")

    expect(saveButton.className).toContain("ant-btn-lg")
    expect(saveButton.className).toContain("min-h-[44px]")
    expect(newButton.className).toContain("min-h-[44px]")
    expect(deleteButton.className).toContain("min-h-[44px]")
    expect(copyButton.className).toContain("min-h-[44px]")
    expect(copyButton.className).toContain("min-w-[44px]")
  })

  it("preserves compact desktop toolbar density", () => {
    responsiveState.isMobile = false
    renderHeader()

    const actions = screen.getByTestId("notes-header-actions")
    expect(actions.className).not.toContain("w-full")
    expect(actions.className).not.toContain("flex-wrap")

    const saveButton = screen.getByTestId("notes-save-button")
    const newButton = screen.getByTestId("notes-new-button")

    expect(saveButton.className).toContain("ant-btn-sm")
    expect(saveButton.className).not.toContain("min-h-[44px]")
    expect(newButton.className).not.toContain("min-h-[44px]")
  })
})
