import React from "react"
import { act, render } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { TutorialPrompt } from "../TutorialPrompt"

const infoMock = vi.fn()
const destroyMock = vi.fn()
const markPromptSeenMock = vi.fn()
const startTutorialMock = vi.fn()

const tutorialStoreState = {
  hasSeenPromptForPage: vi.fn(() => false),
  markPromptSeen: markPromptSeenMock,
  startTutorial: startTutorialMock,
  isHelpModalOpen: false,
  activeTutorialId: null as string | null
}

const hasTutorialsForRouteMock = vi.fn<(route: string) => boolean>(() => true)
const getPrimaryTutorialForRouteMock = vi.fn<
  (route: string) => {
    id: string
    labelKey: string
    labelFallback: string
  }
>(() => ({
  id: "playground-basics",
  labelKey: "tutorials:playground.basics.label",
  labelFallback: "Chat Basics"
}))

let capturedNavigate: ReturnType<typeof useNavigate> | null = null

const NavigatorBridge = () => {
  capturedNavigate = useNavigate()
  return null
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValueOrOptions?: unknown) => {
      if (typeof defaultValueOrOptions === "string") {
        return defaultValueOrOptions
      }
      if (
        defaultValueOrOptions &&
        typeof defaultValueOrOptions === "object" &&
        "defaultValue" in (defaultValueOrOptions as Record<string, unknown>)
      ) {
        return String(
          (defaultValueOrOptions as Record<string, unknown>).defaultValue ?? _key
        )
      }
      return _key
    }
  })
}))

vi.mock("antd", () => ({
  notification: {
    useNotification: () => [
      {
        info: infoMock,
        destroy: destroyMock
      },
      <div key="tutorial-prompt-holder" data-testid="tutorial-prompt-holder" />
    ]
  },
  Button: ({
    children,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

vi.mock("@/store/tutorials", () => ({
  useTutorialStore: (selector: (state: typeof tutorialStoreState) => unknown) =>
    selector(tutorialStoreState)
}))

vi.mock("@/tutorials", () => ({
  hasTutorialsForRoute: (route: string) => hasTutorialsForRouteMock(route),
  getPrimaryTutorialForRoute: (route: string) =>
    getPrimaryTutorialForRouteMock(route)
}))

describe("TutorialPrompt behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    tutorialStoreState.hasSeenPromptForPage.mockReturnValue(false)
    tutorialStoreState.isHelpModalOpen = false
    tutorialStoreState.activeTutorialId = null
    capturedNavigate = null
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("shows a prompt with a single global notification key", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <NavigatorBridge />
                <TutorialPrompt />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(infoMock).toHaveBeenCalledTimes(1)
    expect(infoMock.mock.calls[0][0]?.key).toBe("tutorial-prompt-global")
  })

  it("avoids rapid duplicate prompts across route changes", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <NavigatorBridge />
                <TutorialPrompt />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(infoMock).toHaveBeenCalledTimes(1)

    act(() => {
      capturedNavigate?.("/media")
    })

    expect(destroyMock).toHaveBeenCalledWith("tutorial-prompt-global")

    // Cooldown prevents immediate second prompt spam.
    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(infoMock).toHaveBeenCalledTimes(1)

    // After cooldown window, prompt may appear for the new route.
    act(() => {
      vi.advanceTimersByTime(10000)
    })
    expect(infoMock).toHaveBeenCalledTimes(2)
  })
})
