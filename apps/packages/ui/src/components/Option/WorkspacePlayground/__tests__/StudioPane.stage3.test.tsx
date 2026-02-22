import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { StudioPane, estimateGenerationSeconds } from "../StudioPane"

const {
  mockRagSearch,
  mockSynthesizeSpeech,
  mockGenerateSlidesFromMedia,
  mockAddArtifact,
  mockUpdateArtifactStatus,
  mockRemoveArtifact,
  mockSetIsGeneratingOutput,
  mockSetAudioSettings,
  mockListDecks,
  mockGetChatModels,
  mockSetSelectedModel,
  mockSetRagSearchMode,
  mockSetRagTopK,
  mockSetRagEnableGeneration,
  mockSetRagEnableCitations,
  mockSetRagAdvancedOptions,
  mockSetApiProvider,
  mockSetTemperature,
  mockSetTopP,
  mockSetNumPredict,
  mockUpdateModelSetting,
  messageOptionStoreState,
  chatModelSettingsStoreState,
  mockMessageSuccess,
  mockMessageError,
  mockMessageInfo,
  workspaceStoreState
} = vi.hoisted(() => {
  const ragSearch = vi.fn()
  const synthesizeSpeech = vi.fn()
  const generateSlidesFromMedia = vi.fn()
  const addArtifact = vi.fn()
  const updateArtifactStatus = vi.fn()
  const removeArtifact = vi.fn()
  const restoreArtifact = vi.fn()
  const setIsGeneratingOutput = vi.fn()
  const setAudioSettings = vi.fn()
  const listDecks = vi.fn()
  const getChatModels = vi.fn()
  const messageSuccess = vi.fn()
  const messageError = vi.fn()
  const messageInfo = vi.fn()
  const setSelectedModel = vi.fn()
  const setRagSearchMode = vi.fn()
  const setRagTopK = vi.fn()
  const setRagEnableGeneration = vi.fn()
  const setRagEnableCitations = vi.fn()
  const setRagAdvancedOptions = vi.fn()
  const setApiProvider = vi.fn()
  const setTemperature = vi.fn()
  const setTopP = vi.fn()
  const setNumPredict = vi.fn()
  const updateModelSetting = vi.fn()

  const state = {
    selectedSourceIds: ["source-1"],
    getSelectedMediaIds: () => [101],
    generatedArtifacts: [] as Array<any>,
    isGeneratingOutput: false,
    generatingOutputType: null as any,
    workspaceTag: "workspace:test",
    audioSettings: {
      provider: "tldw" as const,
      model: "kokoro",
      voice: "af_heart",
      speed: 1,
      format: "mp3" as const
    },
    addArtifact,
    updateArtifactStatus,
    removeArtifact,
    restoreArtifact,
    setIsGeneratingOutput,
    setAudioSettings,
    noteFocusTarget: null as { field: "title" | "content"; token: number } | null
  }

  const messageOptionState = {
    selectedModel: "gpt-4o-mini",
    setSelectedModel,
    ragSearchMode: "hybrid" as "hybrid" | "vector" | "fts",
    setRagSearchMode,
    ragTopK: 8,
    setRagTopK,
    ragEnableGeneration: true,
    setRagEnableGeneration,
    ragEnableCitations: true,
    setRagEnableCitations,
    ragAdvancedOptions: {
      min_score: 0.2,
      enable_reranking: true
    } as Record<string, unknown>,
    setRagAdvancedOptions
  }

  const chatModelSettingsState = {
    apiProvider: undefined as string | undefined,
    temperature: 0.7,
    topP: 1,
    numPredict: 800,
    setApiProvider,
    setTemperature,
    setTopP,
    setNumPredict,
    updateSetting: updateModelSetting
  }

  setSelectedModel.mockImplementation((nextModel: string) => {
    messageOptionState.selectedModel = nextModel
  })
  setRagSearchMode.mockImplementation((nextMode: "hybrid" | "vector" | "fts") => {
    messageOptionState.ragSearchMode = nextMode
  })
  setRagTopK.mockImplementation((nextTopK: number | null) => {
    messageOptionState.ragTopK = nextTopK
  })
  setRagEnableGeneration.mockImplementation((enabled: boolean) => {
    messageOptionState.ragEnableGeneration = enabled
  })
  setRagEnableCitations.mockImplementation((enabled: boolean) => {
    messageOptionState.ragEnableCitations = enabled
  })
  setRagAdvancedOptions.mockImplementation((nextOptions: Record<string, unknown>) => {
    messageOptionState.ragAdvancedOptions = nextOptions
  })
  setApiProvider.mockImplementation((provider: string) => {
    chatModelSettingsState.apiProvider = provider
  })
  setTemperature.mockImplementation((nextTemperature: number) => {
    chatModelSettingsState.temperature = nextTemperature
  })
  setTopP.mockImplementation((nextTopP: number) => {
    chatModelSettingsState.topP = nextTopP
  })
  setNumPredict.mockImplementation((nextNumPredict: number | undefined) => {
    chatModelSettingsState.numPredict = nextNumPredict
  })
  updateModelSetting.mockImplementation(
    (key: keyof typeof chatModelSettingsState, value: unknown) => {
      ;(chatModelSettingsState as Record<string, unknown>)[key] = value
    }
  )

  return {
    mockRagSearch: ragSearch,
    mockSynthesizeSpeech: synthesizeSpeech,
    mockGenerateSlidesFromMedia: generateSlidesFromMedia,
    mockAddArtifact: addArtifact,
    mockUpdateArtifactStatus: updateArtifactStatus,
    mockRemoveArtifact: removeArtifact,
    mockSetIsGeneratingOutput: setIsGeneratingOutput,
    mockSetAudioSettings: setAudioSettings,
    mockListDecks: listDecks,
    mockGetChatModels: getChatModels,
    mockSetSelectedModel: setSelectedModel,
    mockSetRagSearchMode: setRagSearchMode,
    mockSetRagTopK: setRagTopK,
    mockSetRagEnableGeneration: setRagEnableGeneration,
    mockSetRagEnableCitations: setRagEnableCitations,
    mockSetRagAdvancedOptions: setRagAdvancedOptions,
    mockSetApiProvider: setApiProvider,
    mockSetTemperature: setTemperature,
    mockSetTopP: setTopP,
    mockSetNumPredict: setNumPredict,
    mockUpdateModelSetting: updateModelSetting,
    messageOptionStoreState: messageOptionState,
    chatModelSettingsStoreState: chatModelSettingsState,
    mockMessageSuccess: messageSuccess,
    mockMessageError: messageError,
    mockMessageInfo: messageInfo,
    workspaceStoreState: state
  }
})
let isMobile = false

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?: string | { defaultValue?: string },
      interpolationOptions?: Record<string, unknown>
    ) => {
      if (typeof defaultValueOrOptions === "string") {
        if (!interpolationOptions) return defaultValueOrOptions
        return defaultValueOrOptions.replace(
          /\{\{(\w+)\}\}/g,
          (_match, token) => String(interpolationOptions[token] ?? "")
        )
      }
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => isMobile
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
  inferTldwProviderFromModel: vi.fn().mockReturnValue("kokoro")
}))

vi.mock("@/services/quizzes", () => ({
  generateQuiz: vi.fn()
}))

vi.mock("@/services/flashcards", () => ({
  listDecks: mockListDecks,
  createDeck: vi.fn(),
  createFlashcard: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    ragSearch: mockRagSearch,
    synthesizeSpeech: mockSynthesizeSpeech,
    generateSlidesFromMedia: mockGenerateSlidesFromMedia,
    exportPresentation: vi.fn(),
    downloadOutput: vi.fn()
  }
}))

vi.mock("@/services/tldw", () => ({
  tldwModels: {
    getChatModels: mockGetChatModels,
    getProviderDisplayName: (provider: string) => provider.toUpperCase()
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
          success: mockMessageSuccess,
          error: mockMessageError,
          info: mockMessageInfo,
          warning: vi.fn()
        },
        <></>
      ]
    }
  }
})

if (!(globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver) {
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("StudioPane Stage 3 information architecture and UX polish", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    isMobile = false
    workspaceStoreState.selectedSourceIds = ["source-1"]
    workspaceStoreState.getSelectedMediaIds = () => [101]
    workspaceStoreState.generatedArtifacts = []
    workspaceStoreState.isGeneratingOutput = false
    workspaceStoreState.generatingOutputType = null
    workspaceStoreState.noteFocusTarget = null
    messageOptionStoreState.selectedModel = "gpt-4o-mini"
    messageOptionStoreState.ragSearchMode = "hybrid"
    messageOptionStoreState.ragTopK = 8
    messageOptionStoreState.ragEnableGeneration = true
    messageOptionStoreState.ragEnableCitations = true
    messageOptionStoreState.ragAdvancedOptions = {
      min_score: 0.2,
      enable_reranking: true
    }
    chatModelSettingsStoreState.apiProvider = undefined
    chatModelSettingsStoreState.temperature = 0.7
    chatModelSettingsStoreState.topP = 1
    chatModelSettingsStoreState.numPredict = 800

    let artifactCounter = 0
    mockAddArtifact.mockImplementation((artifactData: any) => {
      artifactCounter += 1
      const artifact = {
        ...artifactData,
        id: `artifact-${artifactCounter}`,
        createdAt: new Date("2026-02-18T00:00:00.000Z")
      }
      workspaceStoreState.generatedArtifacts = [artifact, ...workspaceStoreState.generatedArtifacts]
      return artifact
    })

    mockUpdateArtifactStatus.mockImplementation(
      (id: string, status: string, updates: Record<string, unknown> = {}) => {
        workspaceStoreState.generatedArtifacts = workspaceStoreState.generatedArtifacts.map(
          (artifact) =>
            artifact.id === id
              ? {
                  ...artifact,
                  status,
                  ...updates
                }
              : artifact
        )
      }
    )

    mockSetIsGeneratingOutput.mockImplementation(
      (isGenerating: boolean, outputType: string | null = null) => {
        workspaceStoreState.isGeneratingOutput = isGenerating
        workspaceStoreState.generatingOutputType = isGenerating ? outputType : null
      }
    )

    mockListDecks.mockResolvedValue([])
    mockGetChatModels.mockResolvedValue([
      { id: "gpt-4o-mini", name: "GPT-4o Mini", provider: "openai", type: "chat" },
      { id: "llama-3.1-8b", name: "Llama 3.1 8B", provider: "ollama", type: "chat" }
    ])
    mockRagSearch.mockResolvedValue({ generation: "summary" })
    mockSynthesizeSpeech.mockResolvedValue(new ArrayBuffer(8))
    mockGenerateSlidesFromMedia.mockResolvedValue({
      id: "presentation-1",
      title: "Slides",
      theme: "default",
      slides: [],
      version: 1,
      created_at: "2026-02-18T00:00:00.000Z"
    })
  })

  it("groups output buttons by category and surfaces description tooltips", async () => {
    render(<StudioPane />)

    expect(screen.getByText("Study Aids")).toBeInTheDocument()
    expect(screen.getByText("Analysis")).toBeInTheDocument()
    expect(screen.getByText("Creative")).toBeInTheDocument()

    fireEvent.mouseEnter(screen.getByRole("button", { name: "Summary" }))
    expect(
      await screen.findByText("Create a concise summary of key points")
    ).toBeInTheDocument()
  })

  it("shows contextual audio settings when audio overview is selected", async () => {
    render(<StudioPane />)

    expect(
      screen.getByText("Select Audio Overview to configure TTS voice and speed.")
    ).toBeInTheDocument()
    expect(screen.queryByText("TTS Provider")).not.toBeInTheDocument()

    fireEvent.mouseEnter(screen.getByRole("button", { name: "Audio Overview" }))

    expect(await screen.findByText("TTS Provider")).toBeInTheDocument()
  })

  it("shows dynamic ETA text while generation is running", async () => {
    mockRagSearch.mockImplementation(
      (_query: string, options?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          const abortError = new Error("Aborted")
          abortError.name = "AbortError"
          const signal = options?.signal
          signal?.addEventListener(
            "abort",
            () => {
              reject(abortError)
            },
            { once: true }
          )
        })
    )

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(
        screen.getByText("~8s for 1 source")
      ).toBeInTheDocument()
    })
  })

  it("uses adaptive output container sizing and stable ETA heuristic", () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-summary",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Summary text",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    const { container } = render(<StudioPane />)
    const paneRoot = container.firstElementChild as HTMLElement | null
    expect(paneRoot).not.toBeNull()
    expect(paneRoot?.className).toContain("overflow-y-auto")
    const outputContainer = container.querySelector(".custom-scrollbar")
    expect(outputContainer).toHaveStyle({ maxHeight: "40vh" })

    expect(estimateGenerationSeconds("summary", 1)).toBe(8)
    expect(estimateGenerationSeconds("audio_overview", 3)).toBe(34)
    expect(estimateGenerationSeconds("audio_overview", 3)).toBeGreaterThan(
      estimateGenerationSeconds("summary", 3)
    )
  })

  it("uses larger touch controls for audio settings on mobile", async () => {
    isMobile = true

    const { container } = render(<StudioPane />)
    fireEvent.click(screen.getByRole("button", { name: "Audio Settings" }))

    expect(await screen.findByText("TTS Provider")).toBeInTheDocument()
    const selectElements = container.querySelectorAll(".ant-select")
    expect(selectElements.length).toBeGreaterThan(0)
    expect(
      Array.from(selectElements).every((select) =>
        select.classList.contains("ant-select-lg")
      )
    ).toBe(true)

    const speedLabel = screen.getByText("Speed: 1.0x")
    const speedSlider = speedLabel.parentElement?.querySelector(
      ".ant-slider"
    ) as HTMLElement | null
    expect(speedSlider).toBeTruthy()
    expect(speedSlider?.className).toContain("[&_.ant-slider-rail]:!h-2")
    expect(speedSlider?.className).toContain("[&_.ant-slider-track]:!h-2")
    expect(speedSlider?.className).toContain("[&_.ant-slider-handle]:!h-5")
  })

  it("exposes aria-expanded metadata for collapsible studio sections", () => {
    const { container } = render(<StudioPane />)

    const studioOptionsToggle = screen.getByRole("button", {
      name: /Studio Options/
    })
    expect(studioOptionsToggle).toHaveAttribute("aria-expanded", "true")
    expect(studioOptionsToggle).toHaveAttribute(
      "aria-controls",
      "studio-options-section"
    )

    const outputTypesToggle = screen.getByRole("button", {
      name: /Output Types/
    })
    expect(outputTypesToggle).toHaveAttribute("aria-expanded", "true")
    expect(outputTypesToggle).toHaveAttribute(
      "aria-controls",
      "studio-output-types-section"
    )

    const outputsToggle = screen.getByRole("button", {
      name: /Generated Outputs/
    })
    expect(outputsToggle).toHaveAttribute("aria-expanded", "true")
    expect(outputsToggle).toHaveAttribute(
      "aria-controls",
      "studio-generated-outputs-section"
    )

    fireEvent.click(outputsToggle)
    expect(outputsToggle).toHaveAttribute("aria-expanded", "false")
    expect(
      container.querySelector("#studio-generated-outputs-section")
    ).toHaveAttribute("hidden")

    fireEvent.click(studioOptionsToggle)
    expect(studioOptionsToggle).toHaveAttribute("aria-expanded", "false")
    expect(container.querySelector("#studio-options-section")).toHaveAttribute(
      "hidden"
    )

    const audioSettingsToggle = screen.getByRole("button", {
      name: /Audio Settings/
    })
    expect(audioSettingsToggle).toHaveAttribute("aria-expanded", "false")
    expect(audioSettingsToggle).toHaveAttribute(
      "aria-controls",
      "studio-audio-settings-panel"
    )
  })

  it("renders audio settings as a connected accordion container", () => {
    render(<StudioPane />)

    const accordion = screen.getByTestId("studio-audio-settings-accordion")
    const audioSettingsToggle = screen.getByRole("button", {
      name: /Audio Settings/
    })

    expect(accordion).toContainElement(audioSettingsToggle)
    expect(screen.queryByText("TTS Provider")).not.toBeInTheDocument()

    fireEvent.click(audioSettingsToggle)

    expect(audioSettingsToggle).toHaveAttribute("aria-expanded", "true")
    expect(audioSettingsToggle.className).toContain("border-b")
    expect(screen.getByText("TTS Provider")).toBeInTheDocument()
    expect(accordion).toContainElement(
      screen.getByText("TTS Provider")
    )
  })

  it("wires Studio Options controls to model and RAG stores", async () => {
    const { container } = render(<StudioPane />)

    await waitFor(() => {
      expect(mockGetChatModels).toHaveBeenCalled()
    })

    expect(screen.getByText("API Provider")).toBeInTheDocument()
    expect(screen.getByText("Model Runtime")).toBeInTheDocument()
    expect(screen.getByText("RAG Settings")).toBeInTheDocument()

    const maxTokensLabel = screen.getByText("Max Tokens")
    const maxTokensInput = maxTokensLabel.parentElement?.querySelector(
      "input"
    ) as HTMLInputElement | null
    expect(maxTokensInput).toBeTruthy()
    if (maxTokensInput) {
      fireEvent.change(maxTokensInput, { target: { value: "1234" } })
    }
    expect(mockSetNumPredict).toHaveBeenCalledWith(1234)

    const enableCitationsRow = screen.getByText("Enable citations").closest("div")
    const citationsSwitch = enableCitationsRow?.querySelector(
      "button[role='switch']"
    ) as HTMLButtonElement | null
    expect(citationsSwitch).toBeTruthy()
    if (citationsSwitch) {
      fireEvent.click(citationsSwitch)
    }
    expect(mockSetRagEnableCitations).toHaveBeenCalledWith(false)

    const rerankingRow = screen.getByText("Enable reranking").closest("div")
    const rerankingSwitch = rerankingRow?.querySelector(
      "button[role='switch']"
    ) as HTMLButtonElement | null
    expect(rerankingSwitch).toBeTruthy()
    if (rerankingSwitch) {
      fireEvent.click(rerankingSwitch)
    }
    expect(mockSetRagAdvancedOptions).toHaveBeenCalledWith(
      expect.objectContaining({ enable_reranking: false })
    )

    expect(container.querySelector("[data-testid='studio-options-accordion']")).toBeTruthy()
  })

  it("ensures icon-only action buttons include aria-labels", () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-summary-a11y",
        type: "summary",
        title: "A11y Summary",
        status: "completed",
        content: "A11y text",
        createdAt: new Date("2026-02-18T08:00:00.000Z")
      }
    ]

    const { container } = render(<StudioPane />)

    const iconOnlyButtons = Array.from(
      container.querySelectorAll("button")
    ).filter((button) => {
      const hasIcon = Boolean(button.querySelector("svg"))
      const hasText = (button.textContent || "").trim().length > 0
      return hasIcon && !hasText
    })

    expect(iconOnlyButtons.length).toBeGreaterThan(0)
    iconOnlyButtons.forEach((button) => {
      expect(button).toHaveAttribute("aria-label")
      expect(button.getAttribute("aria-label")?.trim().length).toBeGreaterThan(0)
    })
  })
})
