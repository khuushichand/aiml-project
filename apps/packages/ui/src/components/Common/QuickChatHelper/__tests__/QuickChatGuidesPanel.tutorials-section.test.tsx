import React from "react"
import { describe, expect, it, beforeEach, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { QUICK_CHAT_WORKFLOW_GUIDES } from "../workflow-guides"
import { QuickChatGuidesPanel } from "../QuickChatGuidesPanel"

const useStorageMock = vi.fn()
const startTutorialMock = vi.fn()
const tutorialStoreSelectorMock = vi.fn()

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (...args: unknown[]) => useStorageMock(...args)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        if ("defaultValue" in fallbackOrOptions && fallbackOrOptions.defaultValue) {
          return fallbackOrOptions.defaultValue
        }
      }
      if (key === "tutorials:steps") {
        return "5 steps"
      }
      if (key.endsWith(".label")) {
        return key
      }
      return key
    }
  })
}))

vi.mock("../../../store/tutorials", () => ({
  useTutorialStore: (selector: (state: unknown) => unknown) =>
    tutorialStoreSelectorMock(selector)
}))

describe("QuickChatGuidesPanel tutorials section", () => {
  beforeEach(() => {
    useStorageMock.mockReset()
    tutorialStoreSelectorMock.mockReset()
    startTutorialMock.mockReset()

    useStorageMock.mockReturnValue([QUICK_CHAT_WORKFLOW_GUIDES])
    tutorialStoreSelectorMock.mockImplementation((selector: (state: unknown) => unknown) =>
      selector({
        completedTutorials: [],
        startTutorial: startTutorialMock
      })
    )
  })

  it("renders Tutorials section above workflow guide browser", () => {
    render(
      <QuickChatGuidesPanel
        onAskGuide={vi.fn()}
        onOpenRoute={vi.fn()}
        currentRoute="/prompts"
      />
    )

    const tutorialsTitle = screen.getByText("Tutorials for this page")
    const guidesTitle = screen.getByText("Workflow guide browser")
    const position = tutorialsTitle.compareDocumentPosition(guidesTitle)

    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText("Prompts Basics")).toBeInTheDocument()
  })

  it("starts selected tutorial from tutorials section", () => {
    const onStartTutorial = vi.fn()
    render(
      <QuickChatGuidesPanel
        onAskGuide={vi.fn()}
        onOpenRoute={vi.fn()}
        currentRoute="/prompts"
        onStartTutorial={onStartTutorial}
      />
    )

    const tutorialRow = screen
      .getByText("Prompts Basics")
      .closest("div")
    expect(tutorialRow).toBeTruthy()
    if (!tutorialRow) return

    const startButton = within(tutorialRow.parentElement as HTMLElement).getByRole(
      "button",
      { name: "Start" }
    )
    fireEvent.click(startButton)
    expect(onStartTutorial).toHaveBeenCalledWith("prompts-basics")
    expect(startTutorialMock).not.toHaveBeenCalled()
  })

  it("shows tutorials empty state while workflow cards remain visible when route has no tutorials", () => {
    render(
      <QuickChatGuidesPanel
        onAskGuide={vi.fn()}
        onOpenRoute={vi.fn()}
        currentRoute="/settings/health"
      />
    )

    expect(
      screen.getByText("No tutorials are available for this page yet.")
    ).toBeInTheDocument()
    expect(screen.getByText("Workflow guide browser")).toBeInTheDocument()
    expect(screen.getByText("Ingest + summarize a source")).toBeInTheDocument()
  })
})
