// @vitest-environment jsdom
import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PlaygroundChat } from "../PlaygroundChat"
import { DemoModeProvider } from "@/context/demo-mode"

type MockLinkedRun = {
  run_id: string
  query: string
  status: string
  phase: string
  control_state: string
  latest_checkpoint_id: string | null
  updated_at: string
}

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
  linkedRuns: [] as MockLinkedRun[],
  linkedRunsStatus: "success" as "success" | "error",
  errorUpdatedAt: 0,
  dataUpdatedAt: 1,
  capturedOptions: null as Record<string, any> | null
}))

const notificationMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn()
}))

const mockComponents = vi.hoisted(() => ({
  PlaygroundEmpty: () => <div data-testid="playground-empty" />
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
      queryState.capturedOptions = options
      return {
        data: { runs: queryState.linkedRuns },
        isSuccess: queryState.linkedRunsStatus === "success",
        isError: queryState.linkedRunsStatus === "error",
        status: queryState.linkedRunsStatus,
        errorUpdatedAt: queryState.errorUpdatedAt,
        dataUpdatedAt: queryState.dataUpdatedAt
      }
    }
    return { data: [], isSuccess: true, isError: false, status: "success", errorUpdatedAt: 0, dataUpdatedAt: 1 }
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
  useAntdNotification: () => notificationMocks
}))

vi.mock("@/components/Common/ChatGreetingPicker", () => ({
  ChatGreetingPicker: () => <div data-testid="chat-greeting-picker" />
}))

vi.mock("./PlaygroundEmpty", () => ({
  PlaygroundEmpty: mockComponents.PlaygroundEmpty
}))

vi.mock("../PlaygroundEmpty", () => ({
  PlaygroundEmpty: mockComponents.PlaygroundEmpty
}))

vi.mock("@/components/Common/Playground/Message", () => ({
  PlaygroundMessage: (props: { message: string }) => (
    <div data-testid="playground-message-mock">{props.message}</div>
  )
}))

const setLinkedRuns = (runs: MockLinkedRun[]) => {
  queryState.linkedRuns = runs
  queryState.linkedRunsStatus = "success"
  queryState.dataUpdatedAt += 1
}

const setLinkedRunError = () => {
  queryState.linkedRunsStatus = "error"
  queryState.errorUpdatedAt += 1
}

const renderChat = () =>
  render(
    <DemoModeProvider>
      <PlaygroundChat />
    </DemoModeProvider>
  )

const renderChatTree = () => (
  <DemoModeProvider>
    <PlaygroundChat />
  </DemoModeProvider>
)

describe("PlaygroundChat linked research status integration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useMessageOptionState.value.messages = []
    useMessageOptionState.value.temporaryChat = false
    useMessageOptionState.value.serverChatId = "chat-1"
    queryState.linkedRuns = []
    queryState.linkedRunsStatus = "success"
    queryState.errorUpdatedAt = 0
    queryState.dataUpdatedAt = 1
    queryState.capturedOptions = null
  })

  it("renders the linked research status block below empty scaffolding and above the transcript area", () => {
    setLinkedRuns([
      {
        run_id: "rs_wait",
        query: "Check original source",
        status: "waiting_human",
        phase: "awaiting_plan_review",
        control_state: "running",
        latest_checkpoint_id: "cp_1",
        updated_at: "2026-03-08T20:00:00+00:00"
      }
    ])

    renderChat()

    const emptyState = screen.getByTestId("playground-empty")
    const statusBlock = screen.getByTestId("research-run-status-stack")
    expect(statusBlock).toBeInTheDocument()
    expect(emptyState.compareDocumentPosition(statusBlock)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(screen.getByText("Needs review")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open in Research" })).toHaveAttribute(
      "href",
      "/research?run=rs_wait"
    )
  })

  it("renders multiple linked runs with distinct labels and stacked rows", () => {
    setLinkedRuns([
      {
        run_id: "rs_running",
        query: "Running query",
        status: "running",
        phase: "collecting",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:03:00+00:00"
      },
      {
        run_id: "rs_completed",
        query: "Completed query",
        status: "completed",
        phase: "completed",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:02:00+00:00"
      },
      {
        run_id: "rs_failed",
        query: "Failed query",
        status: "failed",
        phase: "failed",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:01:00+00:00"
      }
    ])

    renderChat()

    expect(screen.getAllByTestId("research-run-status-row")).toHaveLength(3)
    expect(screen.getByText("Running")).toBeInTheDocument()
    expect(screen.getByText("Completed")).toBeInTheDocument()
    expect(screen.getByText("Failed")).toBeInTheDocument()
  })

  it("does not render the status block for temporary chats or chats without a server id", () => {
    setLinkedRuns([
      {
        run_id: "rs_running",
        query: "Running query",
        status: "running",
        phase: "collecting",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:03:00+00:00"
      }
    ])
    useMessageOptionState.value.temporaryChat = true

    const { rerender } = renderChat()
    expect(screen.queryByTestId("research-run-status-stack")).not.toBeInTheDocument()

    useMessageOptionState.value.temporaryChat = false
    useMessageOptionState.value.serverChatId = null
    rerender(
      <DemoModeProvider>
        <PlaygroundChat />
      </DemoModeProvider>
    )

    expect(screen.queryByTestId("research-run-status-stack")).not.toBeInTheDocument()
  })

  it("uses active polling for nonterminal runs, slows for terminal runs, backs off after repeated errors, and resets after success", async () => {
    setLinkedRuns([
      {
        run_id: "rs_running",
        query: "Running query",
        status: "running",
        phase: "collecting",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:03:00+00:00"
      }
    ])

    const { rerender } = renderChat()
    expect(
      queryState.capturedOptions?.refetchInterval?.({
        state: { data: { runs: queryState.linkedRuns } }
      })
    ).toBe(5_000)

    setLinkedRuns([
      {
        run_id: "rs_completed",
        query: "Completed query",
        status: "completed",
        phase: "completed",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:03:00+00:00"
      }
    ])
    rerender(renderChatTree())
    expect(
      queryState.capturedOptions?.refetchInterval?.({
        state: { data: { runs: queryState.linkedRuns } }
      })
    ).toBe(30_000)

    setLinkedRunError()
    rerender(renderChatTree())
    await waitFor(() =>
      expect(
        queryState.capturedOptions?.refetchInterval?.({
          state: { data: { runs: [{ status: "completed" }] } }
        })
      ).toBe(30_000)
    )
    setLinkedRunError()
    rerender(renderChatTree())
    await waitFor(() =>
      expect(
        queryState.capturedOptions?.refetchInterval?.({
          state: { data: { runs: [{ status: "completed" }] } }
        })
      ).toBe(30_000)
    )
    setLinkedRunError()
    rerender(renderChatTree())
    await waitFor(() =>
      expect(
        queryState.capturedOptions?.refetchInterval?.({
          state: { data: { runs: [{ status: "completed" }] } }
        })
      ).toBe(60_000)
    )

    setLinkedRuns([
      {
        run_id: "rs_completed",
        query: "Completed query",
        status: "completed",
        phase: "completed",
        control_state: "running",
        latest_checkpoint_id: null,
        updated_at: "2026-03-08T20:03:00+00:00"
      }
    ])
    rerender(renderChatTree())
    await waitFor(() =>
      expect(
        queryState.capturedOptions?.refetchInterval?.({
          state: { data: { runs: queryState.linkedRuns } }
        })
      ).toBe(30_000)
    )
  })

  it("keeps linked-run query failures silent and non-blocking", () => {
    setLinkedRunError()

    renderChat()

    expect(screen.queryByTestId("research-run-status-stack")).not.toBeInTheDocument()
    expect(screen.getByTestId("playground-empty")).toBeInTheDocument()
    expect(notificationMocks.error).not.toHaveBeenCalled()
    expect(notificationMocks.warning).not.toHaveBeenCalled()
  })
})
