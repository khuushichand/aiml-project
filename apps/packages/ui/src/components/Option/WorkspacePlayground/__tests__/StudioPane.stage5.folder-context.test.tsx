import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { StudioPane } from "../StudioPane"

const {
  mockRagSearch,
  mockGetChatModels,
  mockAddArtifact,
  mockUpdateArtifactStatus,
  mockSetIsGeneratingOutput,
  workspaceStoreState,
  messageOptionStoreState,
  chatModelSettingsStoreState
} = vi.hoisted(() => {
  const ragSearch = vi.fn()
  const getChatModels = vi.fn()
  const addArtifact = vi.fn()
  const updateArtifactStatus = vi.fn()
  const setIsGeneratingOutput = vi.fn()

  const workspaceState = {
    selectedSourceIds: [] as string[],
    selectedSourceFolderIds: [] as string[],
    getSelectedMediaIds: () => [] as number[],
    getEffectiveSelectedMediaIds: () => [] as number[],
    generatedArtifacts: [] as Array<any>,
    isGeneratingOutput: false,
    generatingOutputType: null as any,
    workspaceTag: "workspace:test",
    audioSettings: {
      provider: "browser" as const,
      model: "kokoro",
      voice: "af_heart",
      speed: 1,
      format: "mp3" as const
    },
    addArtifact,
    updateArtifactStatus,
    removeArtifact: vi.fn(),
    restoreArtifact: vi.fn(),
    setIsGeneratingOutput,
    setAudioSettings: vi.fn(),
    noteFocusTarget: null as { field: "title" | "content"; token: number } | null
  }

  const optionState = {
    selectedModel: "gpt-4o-mini",
    setSelectedModel: vi.fn(),
    ragSearchMode: "hybrid" as const,
    setRagSearchMode: vi.fn(),
    ragTopK: 8,
    setRagTopK: vi.fn(),
    ragEnableGeneration: true,
    setRagEnableGeneration: vi.fn(),
    ragEnableCitations: true,
    setRagEnableCitations: vi.fn(),
    ragAdvancedOptions: { min_score: 0.2, enable_reranking: true } as Record<
      string,
      unknown
    >,
    setRagAdvancedOptions: vi.fn()
  }

  const modelSettingsState = {
    apiProvider: undefined as string | undefined,
    temperature: 0.7,
    topP: 1,
    numPredict: 800,
    setApiProvider: vi.fn(),
    setTemperature: vi.fn(),
    setTopP: vi.fn(),
    setNumPredict: vi.fn(),
    updateSetting: vi.fn()
  }

  return {
    mockRagSearch: ragSearch,
    mockGetChatModels: getChatModels,
    mockAddArtifact: addArtifact,
    mockUpdateArtifactStatus: updateArtifactStatus,
    mockSetIsGeneratingOutput: setIsGeneratingOutput,
    workspaceStoreState: workspaceState,
    messageOptionStoreState: optionState,
    chatModelSettingsStoreState: modelSettingsState
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => false
}))

vi.mock("../StudioPane/QuickNotesSection", () => ({
  QuickNotesSection: () => <div data-testid="quick-notes" />
}))

vi.mock("../source-location-copy", () => ({
  getWorkspaceStudioNoSourcesHint: () => "Select sources first"
}))

vi.mock("@/types/workspace", () => ({
  OUTPUT_TYPES: []
}))

vi.mock("@/services/tldw/audio-voices", () => ({
  fetchTldwVoiceCatalog: vi.fn().mockResolvedValue([])
}))

vi.mock("@/services/tts-provider", () => ({
  inferTldwProviderFromModel: vi.fn().mockReturnValue(null)
}))

vi.mock("@/services/quizzes", () => ({
  generateQuiz: vi.fn()
}))

vi.mock("@/services/flashcards", () => ({
  listDecks: vi.fn().mockResolvedValue([]),
  createDeck: vi.fn(),
  createFlashcard: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    ragSearch: mockRagSearch,
    synthesizeSpeech: vi.fn(),
    generateSlidesFromMedia: vi.fn(),
    exportPresentation: vi.fn(),
    downloadOutput: vi.fn()
  }
}))

vi.mock("@/services/tldw", () => ({
  tldwModels: {
    getChatModels: mockGetChatModels,
    getProviderDisplayName: (provider: string) => provider
  }
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (
    selector: (state: typeof messageOptionStoreState) => unknown
  ) => selector(messageOptionStoreState)
}))

vi.mock("@/store/model", () => ({
  useStoreChatModelSettings: (
    selector: (state: typeof chatModelSettingsStoreState) => unknown
  ) => selector(chatModelSettingsStoreState)
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof workspaceStoreState) => unknown
  ) => selector(workspaceStoreState)
}))

vi.mock("@/components/Common/Mermaid", () => ({
  default: ({ code }: { code: string }) => <div data-testid="mermaid">{code}</div>
}))

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd")
  return {
    ...actual,
    message: {
      useMessage: () => [
        {
          open: vi.fn(),
          warning: vi.fn(),
          destroy: vi.fn(),
          success: vi.fn(),
          error: vi.fn(),
          info: vi.fn()
        },
        <></>
      ]
    }
  }
})

const expandOutputTypesSection = () => {
  const toggle = screen.getByRole("button", { name: /Output Types/i })
  if (toggle.getAttribute("aria-expanded") === "false") {
    fireEvent.click(toggle)
  }
}

describe("StudioPane Stage 5 folder-derived context", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem("tldw:workspace-playground:recent-output-types:v1")

    workspaceStoreState.selectedSourceIds = []
    workspaceStoreState.selectedSourceFolderIds = ["folder-1"]
    workspaceStoreState.getSelectedMediaIds = () => []
    workspaceStoreState.getEffectiveSelectedMediaIds = () => [101]
    workspaceStoreState.generatedArtifacts = []
    workspaceStoreState.isGeneratingOutput = false
    workspaceStoreState.generatingOutputType = null

    let artifactCounter = 0
    mockAddArtifact.mockImplementation((artifactData: any) => {
      artifactCounter += 1
      return {
        ...artifactData,
        id: `artifact-${artifactCounter}`,
        createdAt: new Date("2026-02-18T00:00:00.000Z")
      }
    })
    mockUpdateArtifactStatus.mockImplementation(() => {})

    mockGetChatModels.mockResolvedValue([])
    mockRagSearch.mockResolvedValue({
      answer: "Folder-derived summary",
      total_tokens: 32,
      prompt_tokens: 24,
      completion_tokens: 8
    })
  })

  it("enables generation and uses folder-derived media ids", async () => {
    render(<StudioPane />)
    expandOutputTypesSection()

    const summaryButton = screen.getByRole("button", { name: "Summary" })
    expect(summaryButton).not.toBeDisabled()

    fireEvent.click(summaryButton)

    await waitFor(() => {
      expect(mockRagSearch).toHaveBeenCalledWith(
        expect.stringContaining("summary"),
        expect.objectContaining({
          media_ids: [101]
        })
      )
    })

    expect(mockSetIsGeneratingOutput).toHaveBeenCalled()
  })
})
