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
  mockRagSearch,
  mockSynthesizeSpeech,
  mockGenerateSlidesFromMedia,
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
  const ragSearch = vi.fn()
  const synthesizeSpeech = vi.fn()
  const generateSlidesFromMedia = vi.fn()
  const defaultAudioSettings = {
    provider: "browser" as const,
    model: "kokoro",
    voice: "af_heart",
    speed: 1,
    format: "mp3" as const
  }
  const storeState = {
    selectedSourceIds: ["source-1"],
    getSelectedMediaIds: () => [101],
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
  return {
    mockAddArtifact: addArtifact,
    mockUpdateArtifactStatus: updateArtifactStatus,
    mockRemoveArtifact: removeArtifact,
    mockSetIsGeneratingOutput: setIsGeneratingOutput,
    mockSetAudioSettings: setAudioSettings,
    mockMessageSuccess: messageSuccess,
    mockMessageError: messageError,
    mockMessageInfo: messageInfo,
    mockRagSearch: ragSearch,
    mockSynthesizeSpeech: synthesizeSpeech,
    mockGenerateSlidesFromMedia: generateSlidesFromMedia,
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
  listDecks: vi.fn(),
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

describe("StudioPane Stage 1 generation lifecycle control", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    workspaceStoreState.selectedSourceIds = ["source-1"]
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

    mockRagSearch.mockResolvedValue({ generation: "Generated summary" })
    mockSynthesizeSpeech.mockResolvedValue(new ArrayBuffer(8))
    mockGenerateSlidesFromMedia.mockResolvedValue({
      id: "presentation-1",
      title: "Generated Slides",
      theme: "default",
      slides: [],
      version: 1,
      created_at: "2026-02-18T00:00:00.000Z"
    })
  })

  it("shows cancel control during generation and aborts active run", async () => {
    mockRagSearch.mockImplementation(
      (_query: string, options?: { signal?: AbortSignal }) =>
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

    const { rerender } = render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Summary" }))
    rerender(<StudioPane />)

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

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Delete" }))

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(mockRemoveArtifact).toHaveBeenCalledWith("artifact-existing")
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

    render(<StudioPane />)

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

    render(<StudioPane />)

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
