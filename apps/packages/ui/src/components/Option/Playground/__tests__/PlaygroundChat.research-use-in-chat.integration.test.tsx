// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PlaygroundChat } from "../PlaygroundChat"
import { DemoModeProvider } from "@/context/demo-mode"

const useMessageOptionState = vi.hoisted(() => ({
  value: {
    messages: [] as any[],
    setMessages: vi.fn(),
    streaming: false,
    isProcessing: false,
    regenerateLastMessage: vi.fn(),
    isSearchingInternet: false,
    editMessage: vi.fn(),
    deleteMessage: vi.fn(),
    toggleMessagePinned: vi.fn(),
    ttsEnabled: false,
    onSubmit: vi.fn(),
    actionInfo: null,
    messageSteeringMode: "none",
    setMessageSteeringMode: vi.fn(),
    messageSteeringForceNarrate: false,
    setMessageSteeringForceNarrate: vi.fn(),
    clearMessageSteering: vi.fn(),
    createChatBranch: vi.fn(),
    createCompareBranch: vi.fn(),
    temporaryChat: false,
    serverChatId: "chat-1",
    serverChatCharacterId: null,
    stopStreamingRequest: vi.fn(),
    isEmbedding: false,
    compareMode: false,
    compareFeatureEnabled: false,
    compareSelectionByCluster: {},
    setCompareSelectionForCluster: vi.fn(),
    compareActiveModelsByCluster: {},
    setCompareActiveModelsForCluster: vi.fn(),
    setCompareSelectedModels: vi.fn(),
    historyId: "history-1",
    setSelectedModel: vi.fn(),
    setCompareMode: vi.fn(),
    sendPerModelReply: vi.fn(),
    compareCanonicalByCluster: {},
    setCompareCanonicalForCluster: vi.fn(),
    compareContinuationModeByCluster: {},
    setCompareContinuationModeForCluster: vi.fn(),
    setCompareParentForHistory: vi.fn(),
    compareSplitChats: {},
    setCompareSplitChat: vi.fn(),
    compareMaxModels: 3
  }
}))

const queryState = vi.hoisted(() => ({
  linkedRuns: [] as any[]
}))

const clientMocks = vi.hoisted(() => ({
  initialize: vi.fn().mockResolvedValue(undefined),
  getResearchBundle: vi.fn().mockResolvedValue({
    question: "What changed in the battery recycling market?",
    outline: { sections: [{ title: "Overview" }] },
    claims: [{ text: "Claim one" }],
    unresolved_questions: ["What changed in Europe?"],
    verification_summary: { unsupported_claim_count: 0 },
    source_trust: [{ source_id: "src_1", trust_tier: "high" }]
  })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string) => defaultValue || key
  })
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: Record<string, any>) => {
    const key = Array.isArray(options.queryKey) ? options.queryKey[0] : null
    if (key === "playground:chat-linked-research-runs") {
      return {
        data: { runs: queryState.linkedRuns },
        isSuccess: true,
        isError: false,
        status: "success",
        errorUpdatedAt: 0,
        dataUpdatedAt: 1
      }
    }
    return {
      data: [],
      isSuccess: true,
      isError: false,
      status: "success",
      errorUpdatedAt: 0,
      dataUpdatedAt: 1
    }
  }
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: () => [false]
}))

vi.mock("@/hooks/useMessageOption", () => ({
  useMessageOption: () => useMessageOptionState.value
}))

vi.mock("@/hooks/useSelectedCharacter", () => ({
  useSelectedCharacter: () => [null]
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn()
  })
}))

vi.mock("@/components/Common/ChatGreetingPicker", () => ({
  ChatGreetingPicker: () => null
}))

vi.mock("./PlaygroundEmpty", () => ({
  PlaygroundEmpty: () => null
}))

vi.mock("../PlaygroundEmpty", () => ({
  PlaygroundEmpty: () => null
}))

vi.mock("@/components/Common/Playground/Message", () => ({
  PlaygroundMessage: (props: {
    message: string
    onUseInChat?: () => void
    onFollowUp?: () => void
  }) => (
    <div data-testid="playground-message-mock">
      <div>{props.message}</div>
      {props.onUseInChat && (
        <button type="button" onClick={() => props.onUseInChat?.()}>
          Use in Chat
        </button>
      )}
      {props.onFollowUp && (
        <button type="button" onClick={() => props.onFollowUp?.()}>
          Follow up
        </button>
      )}
    </div>
  )
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: clientMocks
}))

const renderChat = (extraProps?: Record<string, unknown>) =>
  render(
    <DemoModeProvider>
      <PlaygroundChat {...(extraProps as any)} />
    </DemoModeProvider>
  )

describe("PlaygroundChat research use-in-chat message integration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryState.linkedRuns = []
    useMessageOptionState.value.messages = []
    useMessageOptionState.value.serverChatId = "chat-1"
    useMessageOptionState.value.historyId = "history-1"
  })

  it("shows Use in Chat for completion handoff messages and not for unrelated assistant messages", async () => {
    useMessageOptionState.value.messages = [
      {
        isBot: true,
        role: "assistant",
        name: "Assistant",
        message: "Deep research finished.",
        sources: [],
        metadataExtra: {
          deep_research_completion: {
            run_id: "run_msg",
            query: "Battery recycling supply chain",
            kind: "completion_handoff"
          }
        }
      },
      {
        isBot: true,
        role: "assistant",
        name: "Assistant",
        message: "Ordinary assistant reply.",
        sources: [],
        metadataExtra: {}
      }
    ]

    const attachSpy = vi.fn()
    renderChat({ onAttachResearchContext: attachSpy })

    const buttons = screen.getAllByRole("button", { name: "Use in Chat" })
    expect(buttons).toHaveLength(1)

    fireEvent.click(buttons[0])

    await waitFor(() => expect(clientMocks.getResearchBundle).toHaveBeenCalledWith("run_msg"))
    await waitFor(() =>
      expect(attachSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          run_id: "run_msg",
          query: "Battery recycling supply chain",
          research_url: "/research?run=run_msg"
        })
      )
    )
  })

  it("shows Follow up for completion handoff messages and not for unrelated assistant messages", async () => {
    useMessageOptionState.value.messages = [
      {
        isBot: true,
        role: "assistant",
        name: "Assistant",
        message: "Deep research finished.",
        sources: [],
        metadataExtra: {
          deep_research_completion: {
            run_id: "run_msg",
            query: "Battery recycling supply chain",
            kind: "completion_handoff"
          }
        }
      },
      {
        isBot: true,
        role: "assistant",
        name: "Assistant",
        message: "Ordinary assistant reply.",
        sources: [],
        metadataExtra: {}
      }
    ]

    const followUpSpy = vi.fn()
    renderChat({ onPrepareResearchFollowUp: followUpSpy })

    const buttons = screen.getAllByRole("button", { name: "Follow up" })
    expect(buttons).toHaveLength(1)

    fireEvent.click(buttons[0])

    await waitFor(() =>
      expect(followUpSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          run_id: "run_msg",
          query: "Battery recycling supply chain"
        })
      )
    )
  })
})
