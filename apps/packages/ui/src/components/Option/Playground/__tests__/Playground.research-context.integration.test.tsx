// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { Playground } from "../Playground"

const messageOptionState = vi.hoisted(() => ({
  value: {
    messages: [],
    history: [],
    historyId: "history-1",
    serverChatId: "chat-1",
    isLoading: false,
    setHistoryId: vi.fn(),
    setHistory: vi.fn(),
    setMessages: vi.fn(),
    setSelectedSystemPrompt: vi.fn(),
    setSelectedModel: vi.fn(),
    setServerChatId: vi.fn(),
    setContextFiles: vi.fn(),
    createChatBranch: vi.fn(),
    streaming: false,
    selectedCharacter: null,
    setSelectedCharacter: vi.fn(),
    compareMode: false,
    compareFeatureEnabled: false
  }
}))

const artifactsState = vi.hoisted(() => ({
  value: {
    isOpen: false,
    active: null,
    isPinned: false,
    history: [],
    unreadCount: 0,
    setOpen: vi.fn(),
    closeArtifact: vi.fn(),
    markRead: vi.fn()
  }
}))

const smartScrollState = vi.hoisted(() => ({
  value: {
    containerRef: { current: null } as React.MutableRefObject<HTMLDivElement | null>,
    isAutoScrollToBottom: true,
    autoScrollToBottom: vi.fn()
  }
}))

const mobileViewportState = vi.hoisted(() => ({
  value: false
}))

const storeOptionState = vi.hoisted(() => ({
  value: {
    compareParentByHistory: {} as Record<
      string,
      { parentHistoryId: string; clusterId?: string }
    >
  }
}))

const buildAttachedContext = (runId: string, query: string) => ({
  attached_at: "2026-03-08T20:00:00Z",
  run_id: runId,
  query,
  question: query,
  outline: [{ title: "Overview" }],
  key_claims: [{ text: "Claim one" }],
  unresolved_questions: ["Open question"],
  verification_summary: { unsupported_claim_count: 0 },
  source_trust_summary: { high_trust_count: 1 },
  research_url: `/research?run=${runId}`
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string, options?: Record<string, unknown>) => {
      const template = defaultValue || key
      if (!options) return template
      return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
        const value = options[token]
        return value == null ? "" : String(value)
      })
    }
  })
}))

vi.mock("@/components/Option/Playground/PlaygroundForm", () => ({
  PlaygroundForm: (props: {
    attachedResearchContext?: {
      run_id?: string
      query?: string
      question?: string
    } | null
    attachedResearchContextBaseline?: {
      run_id?: string
      query?: string
      question?: string
    } | null
    onApplyAttachedResearchContext?: (
      context: ReturnType<typeof buildAttachedContext>
    ) => void
    onResetAttachedResearchContext?: () => void
    onRemoveAttachedResearchContext?: () => void
  }) => (
    <div
      data-testid="playground-form"
      data-attached-run-id={props.attachedResearchContext?.run_id || ""}
      data-attached-query={props.attachedResearchContext?.query || ""}
      data-attached-question={props.attachedResearchContext?.question || ""}
      data-baseline-run-id={props.attachedResearchContextBaseline?.run_id || ""}
      data-baseline-question={props.attachedResearchContextBaseline?.question || ""}
    >
      {props.attachedResearchContext ? (
        <>
          <button
            type="button"
            onClick={() =>
              props.onApplyAttachedResearchContext?.({
                ...buildAttachedContext(
                  props.attachedResearchContext?.run_id || "run_edited",
                  props.attachedResearchContext?.query || "Edited query"
                ),
                question: "Edited attached question"
              })
            }
          >
            Edit attached research
          </button>
          <button
            type="button"
            onClick={() => props.onResetAttachedResearchContext?.()}
          >
            Reset attached research
          </button>
          <button
            type="button"
            onClick={() => props.onRemoveAttachedResearchContext?.()}
          >
            Remove attached research
          </button>
        </>
      ) : null}
    </div>
  )
}))

vi.mock("@/components/Option/Playground/PlaygroundChat", () => ({
  PlaygroundChat: (props: {
    onAttachResearchContext?: (context: ReturnType<typeof buildAttachedContext>) => void
  }) => (
    <div data-testid="playground-chat">
      <button
        type="button"
        onClick={() =>
          props.onAttachResearchContext?.(
            buildAttachedContext("run_1", "Battery recycling supply chain")
          )
        }
      >
        Attach run 1
      </button>
      <button
        type="button"
        onClick={() =>
          props.onAttachResearchContext?.(
            buildAttachedContext("run_2", "Grid-scale recycling economics")
          )
        }
      >
        Attach run 2
      </button>
    </div>
  )
}))

vi.mock("@/components/Sidepanel/Chat/ArtifactsPanel", () => ({
  ArtifactsPanel: () => <div data-testid="artifacts-panel" />
}))

vi.mock("@/hooks/useMessageOption", () => ({
  useMessageOption: () => messageOptionState.value
}))

vi.mock("@/hooks/usePlaygroundSessionPersistence", () => ({
  usePlaygroundSessionPersistence: () => ({
    restoreSession: vi.fn(async () => false),
    hasPersistedSession: false,
    persistedHistoryId: null,
    persistedServerChatId: null
  })
}))

vi.mock("@/hooks/playground-session-restore", () => ({
  shouldRestorePersistedPlaygroundSession: () => false
}))

vi.mock("@/services/app", () => ({
  webUIResumeLastChat: vi.fn(async () => false)
}))

vi.mock("@/db/dexie/helpers", () => ({
  formatToChatHistory: vi.fn(),
  formatToMessage: vi.fn(),
  getPromptById: vi.fn(async () => null),
  getRecentChatFromWebUI: vi.fn(async () => null)
}))

vi.mock("@/store/model", () => ({
  useStoreChatModelSettings: () => ({ setSystemPrompt: vi.fn() })
}))

vi.mock("@/hooks/useSmartScroll", () => ({
  useSmartScroll: () => smartScrollState.value
}))

vi.mock("@/services/settings/ui-settings", () => ({
  CHAT_BACKGROUND_IMAGE_SETTING: "chatBackgroundImage"
}))

vi.mock("../Knowledge/utils/unsupported-types", () => ({
  otherUnsupportedTypes: []
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (
    selector: (state: typeof storeOptionState.value) => unknown
  ) => selector(storeOptionState.value)
}))

vi.mock("@/store/artifacts", () => ({
  useArtifactsStore: (selector: (state: typeof artifactsState.value) => unknown) =>
    selector(artifactsState.value)
}))

vi.mock("@/hooks/useSetting", () => ({
  useSetting: () => [""]
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultValue: unknown) => [defaultValue]
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => mobileViewportState.value
}))

vi.mock("@/hooks/useLoadLocalConversation", () => ({
  useLoadLocalConversation: () => vi.fn(async () => {})
}))

vi.mock("../playground-shortcuts", () => ({
  resolvePlaygroundShortcutAction: () => null
}))

vi.mock("@/hooks/useCharacterGreeting", () => ({
  useCharacterGreeting: () => undefined
}))

describe("Playground research context integration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mobileViewportState.value = false
    artifactsState.value.isOpen = false
    storeOptionState.value.compareParentByHistory = {}
    messageOptionState.value.serverChatId = "chat-1"
    messageOptionState.value.historyId = "history-1"
  })

  it("replaces the attached research context and lets the form remove it", async () => {
    render(<Playground />)

    fireEvent.click(screen.getByRole("button", { name: "Attach run 1" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        "run_1"
      )
    )

    fireEvent.click(screen.getByRole("button", { name: "Attach run 2" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        "run_2"
      )
    )

    fireEvent.click(
      screen.getByRole("button", { name: "Remove attached research" })
    )
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        ""
      )
    )
  })

  it("tracks a run-derived baseline and lets preview edits update only the active attachment", async () => {
    render(<Playground />)

    fireEvent.click(screen.getByRole("button", { name: "Attach run 1" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        "run_1"
      )
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-attached-question",
      "Battery recycling supply chain"
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-baseline-run-id",
      "run_1"
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-baseline-question",
      "Battery recycling supply chain"
    )

    fireEvent.click(screen.getByRole("button", { name: "Edit attached research" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-question",
        "Edited attached question"
      )
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-baseline-question",
      "Battery recycling supply chain"
    )

    fireEvent.click(screen.getByRole("button", { name: "Reset attached research" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-question",
        "Battery recycling supply chain"
      )
    )
  })

  it("clears attached research context when the active thread changes", async () => {
    const view = render(<Playground />)

    fireEvent.click(screen.getByRole("button", { name: "Attach run 1" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        "run_1"
      )
    )

    messageOptionState.value.serverChatId = "chat-2"
    view.rerender(<Playground />)
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        ""
      )
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-baseline-run-id",
      ""
    )

    fireEvent.click(screen.getByRole("button", { name: "Attach run 2" }))
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        "run_2"
      )
    )

    messageOptionState.value.historyId = "history-2"
    view.rerender(<Playground />)
    await waitFor(() =>
      expect(screen.getByTestId("playground-form")).toHaveAttribute(
        "data-attached-run-id",
        ""
      )
    )
    expect(screen.getByTestId("playground-form")).toHaveAttribute(
      "data-baseline-run-id",
      ""
    )
  })
})
