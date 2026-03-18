import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { Modal } from "antd"
import { StudioPane } from "../StudioPane"

const {
  mockAddArtifact,
  mockUpdateArtifactStatus,
  mockRemoveArtifact,
  mockSetIsGeneratingOutput,
  mockSetAudioSettings,
  mockMessageSuccess,
  mockMessageError,
  mockMessageInfo,
  mockGenerateFlashcardsService,
  mockRagSearch,
  mockSynthesizeSpeech,
  mockGenerateSlidesFromMedia,
  mockDownloadOutput,
  mockCreateChatCompletion,
  mockGetMediaDetails,
  mockGetChatModels,
  messageOptionStoreState,
  chatModelSettingsStoreState,
  baseAudioSettings,
  workspaceStoreState
} = vi.hoisted(() => {
  const addArtifact = vi.fn()
  const updateArtifactStatus = vi.fn()
  const removeArtifact = vi.fn()
  const restoreArtifact = vi.fn()
  const setIsGeneratingOutput = vi.fn()
  const setAudioSettings = vi.fn()
  const messageSuccess = vi.fn()
  const messageError = vi.fn()
  const messageInfo = vi.fn()
  const generateFlashcardsService = vi.fn()
  const ragSearch = vi.fn()
  const synthesizeSpeech = vi.fn()
  const generateSlidesFromMedia = vi.fn()
  const downloadOutput = vi.fn()
  const createChatCompletion = vi.fn()
  const getMediaDetails = vi.fn()
  const getChatModels = vi.fn()
  const defaultAudioSettings = {
    provider: "browser" as const,
    model: "kokoro",
    voice: "af_heart",
    speed: 1,
    format: "mp3" as const
  }
  const defaultSources = [
    {
      id: "source-1",
      mediaId: 101,
      title: "DSPy Prompting Talk",
      type: "video" as const,
      status: "ready" as const,
      addedAt: new Date("2026-02-18T00:00:00.000Z")
    }
  ]
  const storeState = {
    selectedSourceIds: ["source-1"],
    selectedSourceFolderIds: [] as string[],
    sources: defaultSources,
    getSelectedMediaIds: () => [101],
    getEffectiveSelectedSources: () =>
      storeState.sources.filter((source: { id: string }) =>
        storeState.selectedSourceIds.includes(source.id)
      ),
    getEffectiveSelectedMediaIds: () =>
      storeState
        .getEffectiveSelectedSources()
        .map((source: { mediaId: number }) => source.mediaId),
    generatedArtifacts: [] as Array<any>,
    isGeneratingOutput: false,
    generatingOutputType: null as any,
    workspaceTag: "workspace:test",
    audioSettings: { ...defaultAudioSettings },
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
    setSelectedModel: vi.fn(),
    ragSearchMode: "hybrid" as "hybrid" | "vector" | "fts",
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
  const chatModelSettingsState = {
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
    mockAddArtifact: addArtifact,
    mockUpdateArtifactStatus: updateArtifactStatus,
    mockRemoveArtifact: removeArtifact,
    mockSetIsGeneratingOutput: setIsGeneratingOutput,
    mockSetAudioSettings: setAudioSettings,
    mockMessageSuccess: messageSuccess,
    mockMessageError: messageError,
    mockMessageInfo: messageInfo,
    mockGenerateFlashcardsService: generateFlashcardsService,
    mockRagSearch: ragSearch,
    mockSynthesizeSpeech: synthesizeSpeech,
    mockGenerateSlidesFromMedia: generateSlidesFromMedia,
    mockDownloadOutput: downloadOutput,
    mockCreateChatCompletion: createChatCompletion,
    mockGetMediaDetails: getMediaDetails,
    mockGetChatModels: getChatModels,
    messageOptionStoreState: messageOptionState,
    chatModelSettingsStoreState: chatModelSettingsState,
    baseAudioSettings: defaultAudioSettings,
    workspaceStoreState: storeState
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
  QuickNotesSection: ({ onCollapse }: { onCollapse: () => void }) => (
    <button type="button" onClick={onCollapse}>
      Collapse notes
    </button>
  )
}))

vi.mock("../source-location-copy", () => ({
  getWorkspaceStudioNoSourcesHint: () => "Select sources to start generating outputs"
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
  generateFlashcards: mockGenerateFlashcardsService,
  listDecks: vi.fn().mockResolvedValue([]),
  createDeck: vi.fn().mockResolvedValue({ id: 1, name: "Workspace Flashcards" }),
  createFlashcard: vi.fn().mockResolvedValue({ uuid: "card-1" })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    ragSearch: mockRagSearch,
    synthesizeSpeech: mockSynthesizeSpeech,
    generateSlidesFromMedia: mockGenerateSlidesFromMedia,
    createChatCompletion: mockCreateChatCompletion,
    getMediaDetails: mockGetMediaDetails,
    exportPresentation: vi.fn(),
    downloadOutput: mockDownloadOutput
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
          success: mockMessageSuccess,
          error: mockMessageError,
          info: mockMessageInfo
        },
        <></>
      ]
    }
  }
})

const createAbortError = () => {
  const error = new Error("Aborted")
  error.name = "AbortError"
  return error
}

if (!(globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver) {
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

const expandOutputTypesSection = () => {
  const toggle = screen.getByRole("button", { name: /Output Types/i })
  if (toggle.getAttribute("aria-expanded") === "false") {
    fireEvent.click(toggle)
  }
}

const expandGeneratedOutputsSection = () => {
  const toggle = screen.getByRole("button", { name: /Generated Outputs/i })
  if (toggle.getAttribute("aria-expanded") === "false") {
    fireEvent.click(toggle)
  }
}

const createChatCompletionResponse = (
  content: string,
  usage?: Record<string, unknown>
) =>
  new Response(
    JSON.stringify({
      choices: [
        {
          message: {
            content
          }
        }
      ],
      usage
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" }
    }
  )

const renderStudioPane = () => {
  const renderResult = render(<StudioPane />)
  expandOutputTypesSection()
  expandGeneratedOutputsSection()
  return renderResult
}

describe("StudioPane Stage 1 generation lifecycle control", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem("tldw:workspace-playground:recent-output-types:v1")

    workspaceStoreState.selectedSourceIds = ["source-1"]
    workspaceStoreState.selectedSourceFolderIds = []
    workspaceStoreState.sources = [
      {
        id: "source-1",
        mediaId: 101,
        title: "DSPy Prompting Talk",
        type: "video",
        status: "ready",
        addedAt: new Date("2026-02-18T00:00:00.000Z")
      }
    ]
    workspaceStoreState.getSelectedMediaIds = () => [101]
    workspaceStoreState.generatedArtifacts = []
    workspaceStoreState.isGeneratingOutput = false
    workspaceStoreState.generatingOutputType = null
    workspaceStoreState.noteFocusTarget = null
    workspaceStoreState.audioSettings = { ...baseAudioSettings }

    let artifactCounter = 0

    mockAddArtifact.mockImplementation((artifactData: any) => {
      artifactCounter += 1
      const artifact = {
        ...artifactData,
        id: `artifact-${artifactCounter}`,
        createdAt: new Date("2026-02-18T00:00:00.000Z")
      }
      workspaceStoreState.generatedArtifacts = [
        artifact,
        ...workspaceStoreState.generatedArtifacts
      ]
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

    mockRemoveArtifact.mockImplementation((id: string) => {
      workspaceStoreState.generatedArtifacts = workspaceStoreState.generatedArtifacts.filter(
        (artifact) => artifact.id !== id
      )
    })

    mockSetIsGeneratingOutput.mockImplementation(
      (isGenerating: boolean, outputType: string | null = null) => {
        workspaceStoreState.isGeneratingOutput = isGenerating
        workspaceStoreState.generatingOutputType = isGenerating ? outputType : null
      }
    )

    messageOptionStoreState.selectedModel = "gpt-4o-mini"
    messageOptionStoreState.ragAdvancedOptions = {
      min_score: 0.2,
      enable_reranking: true
    }
    chatModelSettingsStoreState.apiProvider = undefined
    mockRagSearch.mockResolvedValue({ generation: "Generated summary" })
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse("Generated summary")
    )
    mockGetMediaDetails.mockResolvedValue({
      source: { title: "DSPy Prompting Talk" },
      content: {
        text: "DSPy helps optimize prompts and compound AI pipelines."
      }
    })
    mockGenerateFlashcardsService.mockResolvedValue({
      flashcards: [{ front: "Term", back: "Definition" }],
      count: 1
    })
    mockSynthesizeSpeech.mockResolvedValue(new ArrayBuffer(8))
    mockGenerateSlidesFromMedia.mockResolvedValue({
      id: "presentation-1",
      title: "Generated Slides",
      theme: "default",
      slides: [],
      version: 1,
      created_at: "2026-02-18T00:00:00.000Z"
    })
    mockGetChatModels.mockResolvedValue([])
  })

  it("shows cancel control during generation and aborts active run", async () => {
    mockCreateChatCompletion.mockImplementation(
      (_request: unknown, options?: { signal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          const abortError = createAbortError()
          const signal = options?.signal
          if (signal?.aborted) {
            reject(abortError)
            return
          }
          signal?.addEventListener(
            "abort",
            () => {
              reject(abortError)
            },
            { once: true }
          )
        })
    )

    const { rerender } = renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))
    rerender(<StudioPane />)
    expandOutputTypesSection()

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

    await waitFor(() => {
      expect(mockSetIsGeneratingOutput).toHaveBeenLastCalledWith(false)
    })

    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "failed",
      expect.objectContaining({
        errorMessage: "Generation canceled before completion."
      })
    )
    expect(mockMessageInfo).toHaveBeenCalledWith("Generation canceled")
  })

  it("treats non-abort cancellation wording as generation failure", async () => {
    mockCreateChatCompletion.mockRejectedValue(
      new Error("Generation cancelled by upstream worker")
    )

    const { rerender } = renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))
    rerender(<StudioPane />)
    expandOutputTypesSection()

    await waitFor(() => {
      expect(mockSetIsGeneratingOutput).toHaveBeenLastCalledWith(false)
    })

    expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
      "artifact-1",
      "failed",
      expect.objectContaining({
        errorMessage: "Generation cancelled by upstream worker"
      })
    )
    expect(mockMessageError).toHaveBeenCalledWith(
      expect.stringContaining("Failed to generate")
    )
    expect(mockMessageInfo).not.toHaveBeenCalledWith("Generation canceled")
  })

  it("marks summary artifacts failed when chat completion returns no usable content", async () => {
    mockCreateChatCompletion.mockResolvedValue(createChatCompletionResponse(""))

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("usable summary")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()
  })

  it("marks summary artifacts failed when chat completion returns the local failure sentinel", async () => {
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse("Summary generation failed")
    )

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("usable summary")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()
  })

  it("marks summary artifacts failed when chat completion returns a backend error string", async () => {
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse(
        "Sorry, I encountered an error. Please try again."
      )
    )

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("usable summary")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()
  })

  it("marks summary artifacts failed when chat completion returns a voice assistant backend error string", async () => {
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse(
        "I'm sorry, I encountered an error processing your request."
      )
    )

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("usable summary")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()
  })

  it("still completes valid summary artifacts", async () => {
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse("Generated summary")
    )

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "completed",
        expect.objectContaining({
          content: "Generated summary"
        })
      )
    })

    expect(mockMessageSuccess).toHaveBeenCalledWith(
      expect.stringContaining("generated successfully")
    )
  })

  it("preserves summary usage metrics from chat completion responses", async () => {
    mockCreateChatCompletion.mockResolvedValue(
      createChatCompletionResponse("Generated summary", {
        total_tokens: 321,
        total_cost_usd: 0.0123
      })
    )

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "completed",
        expect.objectContaining({
          content: "Generated summary",
          totalTokens: 321,
          totalCostUsd: 0.0123
        })
      )
    })
  })

  it("uses the workspace generation_prompt and selected source content for summary generation", async () => {
    messageOptionStoreState.ragAdvancedOptions = {
      min_score: 0.2,
      enable_reranking: true,
      generation_prompt:
        "Write an executive summary focused on failures, tradeoffs, and next steps."
    }
    chatModelSettingsStoreState.apiProvider = "openai"
    mockGetMediaDetails.mockResolvedValue({
      source: { title: "DSPy Prompting Talk" },
      content: {
        text: "The talk covers DSPy, prompt optimization, and compound AI pipeline tradeoffs."
      }
    })

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockCreateChatCompletion).toHaveBeenCalled()
    })

    const summaryRequest = mockCreateChatCompletion.mock.calls[0]?.[0]
    expect(summaryRequest).toMatchObject({
      model: "gpt-4o-mini",
      api_provider: "openai"
    })
    expect(summaryRequest.messages?.[0]).toMatchObject({
      role: "system"
    })
    expect(summaryRequest.messages?.[0]?.content).toContain(
      "Summarize only the provided source content"
    )
    expect(summaryRequest.messages?.[1]).toMatchObject({
      role: "user"
    })
    expect(summaryRequest.messages?.[1]?.content).toContain(
      "Write an executive summary focused on failures, tradeoffs, and next steps."
    )
    expect(summaryRequest.messages?.[1]?.content).toContain("DSPy Prompting Talk")
    expect(summaryRequest.messages?.[1]?.content).toContain(
      "compound AI pipeline tradeoffs"
    )
    expect(mockRagSearch).not.toHaveBeenCalled()
  })

  it("falls back to the default summary instruction when no custom prompt is set", async () => {
    messageOptionStoreState.ragAdvancedOptions = {
      min_score: 0.2,
      enable_reranking: true,
      generation_prompt: "   "
    }

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockCreateChatCompletion).toHaveBeenCalled()
    })

    const summaryRequest = mockCreateChatCompletion.mock.calls[0]?.[0]
    expect(summaryRequest.messages?.[1]).toMatchObject({
      role: "user"
    })
    expect(summaryRequest.messages?.[1]?.content).toContain(
      "Provide a comprehensive summary of the key points and main ideas."
    )
    expect(mockRagSearch).not.toHaveBeenCalled()
  })

  it("fails summary generation when no model is available", async () => {
    messageOptionStoreState.selectedModel = null
    mockGetChatModels.mockResolvedValue([])

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining(
            "No model available for summary generation"
          )
        })
      )
    })

    expect(mockCreateChatCompletion).not.toHaveBeenCalled()
  })

  it("passes the selected model runtime through to slides generation", async () => {
    messageOptionStoreState.selectedModel = "llama-3.1-8b"
    chatModelSettingsStoreState.apiProvider = "ollama"

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Slides" }))

    await waitFor(() => {
      expect(mockGenerateSlidesFromMedia).toHaveBeenCalledWith(
        101,
        expect.objectContaining({
          model: "llama-3.1-8b",
          provider: "ollama",
          temperature: 0.7
        })
      )
    })
  })

  it("downloads quiz artifacts locally instead of calling outputs download", async () => {
    mockDownloadOutput.mockResolvedValue(new Blob(["server download"]))

    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:quiz")
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {})
    const anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {})

    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-quiz",
        type: "quiz",
        title: "Quiz",
        status: "completed",
        serverId: 42,
        content: "Question 1\nA. One\nB. Two",
        data: {
          questions: [
            {
              question: "Question 1",
              options: ["One", "Two"],
              answer: "One"
            }
          ]
        },
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Download" }))

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalled()
    })

    expect(mockDownloadOutput).not.toHaveBeenCalled()
    expect(anchorClickSpy).toHaveBeenCalled()
    expect(revokeObjectUrlSpy).toHaveBeenCalled()

    createObjectUrlSpy.mockRestore()
    revokeObjectUrlSpy.mockRestore()
    anchorClickSpy.mockRestore()
  })

  it("fails non-browser audio overview generation when TTS does not return audio", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {})

    workspaceStoreState.audioSettings = {
      ...baseAudioSettings,
      provider: "tldw",
      model: "kokoro"
    }
    mockRagSearch.mockResolvedValue({ generation: "Audio script" })
    mockSynthesizeSpeech.mockRejectedValue(new Error("TTS service unavailable"))

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Audio Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("audio")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()

    consoleErrorSpy.mockRestore()
  })

  it("fails non-browser audio overview generation when the script is an error response", async () => {
    workspaceStoreState.audioSettings = {
      ...baseAudioSettings,
      provider: "tldw",
      model: "kokoro"
    }
    mockRagSearch.mockResolvedValue({
      generation: "Sorry, I encountered an error. Please try again."
    })
    mockSynthesizeSpeech.mockResolvedValue(new ArrayBuffer(8))

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Audio Summary" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-1",
        "failed",
        expect.objectContaining({
          errorMessage: expect.stringContaining("usable audio")
        })
      )
    })

    expect(mockMessageSuccess).not.toHaveBeenCalled()
  })

  it("passes extended timeout to report generation RAG request", async () => {
    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Report" }))

    await waitFor(() => {
      expect(mockRagSearch).toHaveBeenCalled()
    })

    expect(mockRagSearch).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        timeoutMs: 120000
      })
    )
  })

  it("uses structured flashcard generation instead of the RAG text path", async () => {
    mockGetMediaDetails.mockResolvedValue({
      content: "ATP powers cellular respiration in cells."
    })

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Flashcards" }))

    await waitFor(() => {
      expect(mockGenerateFlashcardsService).toHaveBeenCalledWith(
        expect.objectContaining({
          text: expect.stringContaining("DSPy Prompting Talk")
        })
      )
    })

    expect(mockRagSearch).not.toHaveBeenCalled()
  })

  it("confirms before deleting a generated artifact", () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-existing",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Summary text",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    const confirmSpy = vi
      .spyOn(Modal, "confirm")
      .mockImplementation((config) => {
        config.onOk?.()
        return {
          destroy: vi.fn(),
          update: vi.fn()
        } as any
      })

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Delete" }))

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(mockRemoveArtifact).toHaveBeenCalledWith("artifact-existing")
  })

  it("uses failed status x icon to delete failed generated output", () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-failed",
        type: "summary",
        title: "Failed output",
        status: "failed",
        errorMessage: "Generation failed",
        content: "",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    const confirmSpy = vi
      .spyOn(Modal, "confirm")
      .mockImplementation((config) => {
        config.onOk?.()
        return {
          destroy: vi.fn(),
          update: vi.fn()
        } as any
      })

    renderStudioPane()

    fireEvent.click(screen.getByLabelText("Delete failed output"))

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(mockRemoveArtifact).toHaveBeenCalledWith("artifact-failed")
  })

  it("regenerates in replace mode without creating a new artifact", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-existing",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Summary text",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Regenerate options" }))
    fireEvent.click(await screen.findByText("Replace existing"))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-existing",
        "generating",
        expect.objectContaining({
          errorMessage: undefined
        })
      )
    })
    expect(mockAddArtifact).not.toHaveBeenCalled()
  })

  it("regenerates in new-version mode by creating a new artifact", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-existing",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Summary text",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    renderStudioPane()

    fireEvent.click(screen.getByRole("button", { name: "Regenerate options" }))
    fireEvent.click(await screen.findByText("Create new version"))

    await waitFor(() => {
      expect(mockAddArtifact).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "summary",
          status: "generating",
          previousVersionId: "artifact-existing"
        })
      )
    })
  })
})
