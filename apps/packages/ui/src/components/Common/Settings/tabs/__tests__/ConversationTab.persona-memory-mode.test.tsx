import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery } from "@tanstack/react-query"

import { ConversationTab } from "../ConversationTab"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: any) => {
      if (typeof defaultValue === "string") return defaultValue
      if (defaultValue && typeof defaultValue.defaultValue === "string") {
        return defaultValue.defaultValue
      }
      return _key
    }
  })
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    error: vi.fn(),
    success: vi.fn()
  })
}))

vi.mock("@/components/Common/Settings/PromptAssemblyPreview", () => ({
  PromptAssemblyPreview: () => null
}))

vi.mock("@/components/Common/Settings/LorebookDebugPanel", () => ({
  LorebookDebugPanel: () => null
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn().mockResolvedValue(undefined),
    listCharacters: vi.fn().mockResolvedValue([]),
    listChatMessages: vi.fn().mockResolvedValue([]),
    updateChat: vi.fn().mockResolvedValue({ version: 1 })
  }
}))

vi.mock("@/hooks/chat/useChatSettingsRecord", () => ({
  useChatSettingsRecord: vi.fn()
}))

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual("@tanstack/react-query")
  return {
    ...actual,
    useQuery: vi.fn(),
    useQueryClient: vi.fn().mockReturnValue({
      invalidateQueries: vi.fn(),
      setQueryData: vi.fn()
    })
  }
})

vi.mock("antd", () => {
  return import("../../../../__tests__/mocks/antd").then((mod) =>
    mod.createFormSelectInputNumberAntdMock()
  )
})

const buildQueryResult = (overrides: Record<string, unknown> = {}) =>
  ({
    data: [],
    isLoading: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
    ...overrides
  }) as any

describe("ConversationTab persona memory mode controls", () => {
  const updateSettings = vi.fn().mockResolvedValue(undefined)
  const onVersionChange = vi.fn()
  const onPersonaMemoryModeChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useQuery).mockReturnValue(buildQueryResult())
    vi.mocked(useChatSettingsRecord).mockReturnValue({
      settings: {},
      updateSettings,
      chatKey: "chat:test"
    } as any)
  })

  const renderConversationTab = (
    overrides: Partial<React.ComponentProps<typeof ConversationTab>> = {}
  ) =>
    render(
      <ConversationTab
        historyId="history-1"
        selectedSystemPrompt={null}
        onSystemPromptChange={() => {}}
        uploadedFiles={[]}
        onRemoveFile={() => {}}
        serverChatId="chat-1"
        serverChatState="in-progress"
        onStateChange={vi.fn()}
        serverChatTopic={null}
        onTopicChange={() => {}}
        onVersionChange={onVersionChange}
        onPersonaMemoryModeChange={onPersonaMemoryModeChange}
        {...overrides}
      />
    )

  it("shows persona memory mode controls only for persona-backed chats", () => {
    renderConversationTab({
      serverChatAssistantKind: "persona",
      serverChatPersonaMemoryMode: "read_only"
    })

    expect(screen.getByText("Persona memory mode")).toBeInTheDocument()

    renderConversationTab({
      serverChatAssistantKind: "character",
      serverChatPersonaMemoryMode: null
    })

    expect(screen.queryAllByText("Persona memory mode")).toHaveLength(1)
  })

  it("persists read_write mode when the user opts in", async () => {
    vi.mocked(tldwClient.updateChat).mockResolvedValueOnce({ version: 4 } as any)

    renderConversationTab({
      serverChatAssistantKind: "persona",
      serverChatPersonaMemoryMode: "read_only"
    })

    fireEvent.change(screen.getByTestId("persona-memory-mode-select"), {
      target: { value: "read_write" }
    })

    await waitFor(() => {
      expect(onPersonaMemoryModeChange).toHaveBeenCalledWith("read_write")
      expect(tldwClient.updateChat).toHaveBeenCalledWith("chat-1", {
        persona_memory_mode: "read_write"
      })
      expect(onVersionChange).toHaveBeenCalledWith(4)
    })
  })
})
