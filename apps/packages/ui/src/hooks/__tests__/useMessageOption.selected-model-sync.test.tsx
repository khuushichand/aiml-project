import React from "react"
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  storeState,
  storageBacking,
  storageSetCalls,
  lastUseChatActionsArgs,
  defaultRagSettings
} = vi.hoisted(() => {
  const setSelectedModelSpy = vi.fn((next: string | null) => {
    state.selectedModel = next
  })

  const state: Record<string, any> = {
    selectedModel: null,
    setSelectedModel: setSelectedModelSpy,
    webSearch: false,
    setWebSearch: vi.fn(),
    toolChoice: "none",
    setToolChoice: vi.fn(),
    isSearchingInternet: false,
    setIsSearchingInternet: vi.fn(),
    queuedMessages: [],
    addQueuedMessage: vi.fn(),
    setQueuedMessages: vi.fn(),
    clearQueuedMessages: vi.fn(),
    selectedKnowledge: null,
    setSelectedKnowledge: vi.fn(),
    temporaryChat: false,
    setTemporaryChat: vi.fn(),
    documentContext: null,
    setDocumentContext: vi.fn(),
    uploadedFiles: [],
    setUploadedFiles: vi.fn(),
    contextFiles: [],
    setContextFiles: vi.fn(),
    actionInfo: null,
    setActionInfo: vi.fn(),
    fileRetrievalEnabled: false,
    setFileRetrievalEnabled: vi.fn(),
    ragMediaIds: null,
    setRagMediaIds: vi.fn(),
    ragSearchMode: "hybrid",
    setRagSearchMode: vi.fn(),
    ragTopK: 8,
    setRagTopK: vi.fn(),
    ragEnableGeneration: true,
    setRagEnableGeneration: vi.fn(),
    ragEnableCitations: true,
    setRagEnableCitations: vi.fn(),
    ragSources: [],
    setRagSources: vi.fn(),
    ragAdvancedOptions: {},
    setRagAdvancedOptions: vi.fn(),
    ragPinnedResults: [],
    setRagPinnedResults: vi.fn(),
    serverChatId: null,
    setServerChatId: vi.fn(),
    serverChatTitle: null,
    setServerChatTitle: vi.fn(),
    serverChatCharacterId: null,
    setServerChatCharacterId: vi.fn(),
    serverChatMetaLoaded: false,
    setServerChatMetaLoaded: vi.fn(),
    serverChatState: null,
    setServerChatState: vi.fn(),
    serverChatVersion: null,
    setServerChatVersion: vi.fn(),
    serverChatTopic: null,
    setServerChatTopic: vi.fn(),
    serverChatClusterId: null,
    setServerChatClusterId: vi.fn(),
    serverChatSource: null,
    setServerChatSource: vi.fn(),
    serverChatExternalRef: null,
    setServerChatExternalRef: vi.fn(),
    messageSteeringMode: "none",
    setMessageSteeringMode: vi.fn(),
    messageSteeringForceNarrate: false,
    setMessageSteeringForceNarrate: vi.fn(),
    clearMessageSteering: vi.fn(),
    replyTarget: null,
    clearReplyTarget: vi.fn()
  }

  return {
    storeState: state,
    storageBacking: new Map<string, any>(),
    storageSetCalls: [] as Array<{ key: string; value: unknown }>,
    lastUseChatActionsArgs: { value: null as Record<string, unknown> | null },
    defaultRagSettings: {
      top_k: 8,
      min_score: 0.2,
      enable_reranking: true
    }
  }
})

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: vi.fn()
  })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

vi.mock("@/context", () => ({
  usePageAssist: () => ({
    controller: null,
    setController: vi.fn()
  })
}))

vi.mock("@/store/webui", () => ({
  useWebUI: () => ({
    ttsEnabled: false
  })
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    success: vi.fn()
  })
}))

vi.mock("@/hooks/chat/useChatBaseState", () => ({
  useChatBaseState: () => ({
    messages: [],
    setMessages: vi.fn(),
    history: [],
    setHistory: vi.fn(),
    streaming: false,
    setStreaming: vi.fn(),
    isFirstMessage: true,
    setIsFirstMessage: vi.fn(),
    historyId: null,
    setHistoryId: vi.fn(),
    isLoading: false,
    setIsLoading: vi.fn(),
    isProcessing: false,
    setIsProcessing: vi.fn(),
    chatMode: "normal",
    setChatMode: vi.fn(),
    isEmbedding: false,
    setIsEmbedding: vi.fn(),
    selectedQuickPrompt: null,
    setSelectedQuickPrompt: vi.fn(),
    selectedSystemPrompt: null,
    setSelectedSystemPrompt: vi.fn(),
    useOCR: false,
    setUseOCR: vi.fn()
  })
}))

vi.mock("@/hooks/chat/useSelectServerChat", () => ({
  useSelectServerChat: () => vi.fn()
}))

vi.mock("@/hooks/chat/useServerChatHistoryId", () => ({
  useServerChatHistoryId: () => ({
    ensureServerChatHistoryId: vi.fn()
  })
}))

vi.mock("@/hooks/chat/useServerChatLoader", () => ({
  useServerChatLoader: vi.fn()
}))

vi.mock("@/hooks/chat/useClearChat", () => ({
  useClearChat: () => vi.fn()
}))

vi.mock("@/hooks/chat/useCompareMode", () => ({
  useCompareMode: () => ({
    compareMode: false,
    setCompareMode: vi.fn(),
    compareFeatureEnabled: false,
    setCompareFeatureEnabled: vi.fn(),
    compareSelectedModels: [],
    setCompareSelectedModels: vi.fn(),
    compareSelectionByCluster: {},
    setCompareSelectionForCluster: vi.fn(),
    compareActiveModelsByCluster: {},
    setCompareActiveModelsForCluster: vi.fn(),
    compareParentByHistory: {},
    setCompareParentForHistory: vi.fn(),
    compareCanonicalByCluster: {},
    setCompareCanonicalForCluster: vi.fn(),
    compareSplitChats: {},
    setCompareSplitChat: vi.fn(),
    compareMaxModels: 4,
    setCompareMaxModels: vi.fn(),
    compareModeActive: false,
    markCompareHistoryCreated: vi.fn()
  })
}))

vi.mock("@/hooks/chat/useChatActions", () => ({
  useChatActions: (args: Record<string, unknown>) => {
    lastUseChatActionsArgs.value = args
    return {
      onSubmit: vi.fn(),
      sendPerModelReply: vi.fn(),
      regenerateLastMessage: vi.fn(),
      stopStreamingRequest: vi.fn(),
      editMessage: vi.fn(),
      deleteMessage: vi.fn(),
      toggleMessagePinned: vi.fn(),
      createChatBranch: vi.fn(),
      createCompareBranch: vi.fn()
    }
  }
}))

vi.mock("@/hooks/useSelectedCharacter", () => ({
  useSelectedCharacter: () => [null, vi.fn()]
}))

vi.mock("@/hooks/useSetting", () => ({
  useSetting: () => [25]
}))

vi.mock("@/services/rag/unified-rag", () => ({
  DEFAULT_RAG_SETTINGS: defaultRagSettings,
  toRagAdvancedOptions: vi.fn((value) => value || {})
}))

vi.mock("@/store/model", () => ({
  useStoreChatModelSettings: () => ({ apiProvider: undefined })
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (selector?: (state: Record<string, unknown>) => unknown) =>
    selector ? selector(storeState) : storeState
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    const initialValue = storageBacking.has(key)
      ? storageBacking.get(key)
      : defaultValue
    const [value, setValue] = React.useState(initialValue)
    const setter = (next: unknown) => {
      const resolved =
        typeof next === "function"
          ? (next as (current: unknown) => unknown)(value)
          : next
      storageBacking.set(key, resolved)
      storageSetCalls.push({ key, value: resolved })
      setValue(resolved)
    }
    return [value, setter, { isLoading: false }] as const
  }
}))

import { useMessageOption } from "@/hooks/useMessageOption"

describe("useMessageOption selected model sync", () => {
  beforeEach(() => {
    storageBacking.clear()
    storageSetCalls.length = 0
    lastUseChatActionsArgs.value = null
    storeState.selectedModel = null
  })

  it("prefers store-selected model over stale storage-selected model", async () => {
    storeState.selectedModel = "deepseek/deepseek-r1"
    storageBacking.set("selectedModel", "z-ai/glm-4.6")

    const { result } = renderHook(() => useMessageOption())

    expect(result.current.selectedModel).toBe("deepseek/deepseek-r1")
    expect(lastUseChatActionsArgs.value?.selectedModel).toBe(
      "deepseek/deepseek-r1"
    )

    await waitFor(() => {
      expect(
        storageSetCalls.some(
          (entry) =>
            entry.key === "selectedModel" &&
            entry.value === "deepseek/deepseek-r1"
        )
      ).toBe(true)
    })
  })

  it("hydrates store-selected model from storage when store is empty", async () => {
    storageBacking.set("selectedModel", "z-ai/glm-4.6")

    const { result } = renderHook(() => useMessageOption())

    expect(result.current.selectedModel).toBe("z-ai/glm-4.6")
    await waitFor(() => {
      expect(storeState.selectedModel).toBe("z-ai/glm-4.6")
    })
  })
})
