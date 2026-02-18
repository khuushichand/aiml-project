import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { Modal } from "antd"
import { StudioPane } from "../StudioPane"

const {
  mockGenerateQuiz,
  mockListDecks,
  mockCreateDeck,
  mockCreateFlashcard,
  mockRagSearch,
  mockSynthesizeSpeech,
  mockGenerateSlidesFromMedia,
  mockAddArtifact,
  mockUpdateArtifactStatus,
  mockRemoveArtifact,
  mockSetIsGeneratingOutput,
  mockSetAudioSettings,
  mockCaptureToCurrentNote,
  mockMessageSuccess,
  mockMessageError,
  mockMessageInfo,
  workspaceStoreState
} = vi.hoisted(() => {
  const generateQuiz = vi.fn()
  const listDecks = vi.fn()
  const createDeck = vi.fn()
  const createFlashcard = vi.fn()
  const ragSearch = vi.fn()
  const synthesizeSpeech = vi.fn()
  const generateSlidesFromMedia = vi.fn()

  const addArtifact = vi.fn()
  const updateArtifactStatus = vi.fn()
  const removeArtifact = vi.fn()
  const setIsGeneratingOutput = vi.fn()
  const setAudioSettings = vi.fn()
  const captureToCurrentNote = vi.fn()

  const messageSuccess = vi.fn()
  const messageError = vi.fn()
  const messageInfo = vi.fn()

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
    setIsGeneratingOutput,
    setAudioSettings,
    captureToCurrentNote,
    noteFocusTarget: null as { field: "title" | "content"; token: number } | null
  }

  return {
    mockGenerateQuiz: generateQuiz,
    mockListDecks: listDecks,
    mockCreateDeck: createDeck,
    mockCreateFlashcard: createFlashcard,
    mockRagSearch: ragSearch,
    mockSynthesizeSpeech: synthesizeSpeech,
    mockGenerateSlidesFromMedia: generateSlidesFromMedia,
    mockAddArtifact: addArtifact,
    mockUpdateArtifactStatus: updateArtifactStatus,
    mockRemoveArtifact: removeArtifact,
    mockSetIsGeneratingOutput: setIsGeneratingOutput,
    mockSetAudioSettings: setAudioSettings,
    mockCaptureToCurrentNote: captureToCurrentNote,
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
      defaultValueOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
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

vi.mock("@/services/tldw/audio-voices", () => ({
  fetchTldwVoiceCatalog: vi.fn().mockResolvedValue([])
}))

vi.mock("@/services/tts-provider", () => ({
  inferTldwProviderFromModel: vi.fn().mockReturnValue("kokoro")
}))

vi.mock("@/services/quizzes", () => ({
  generateQuiz: mockGenerateQuiz
}))

vi.mock("@/services/flashcards", () => ({
  listDecks: mockListDecks,
  createDeck: mockCreateDeck,
  createFlashcard: mockCreateFlashcard
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

Object.defineProperty(HTMLMediaElement.prototype, "play", {
  configurable: true,
  value: vi.fn().mockResolvedValue(undefined)
})

Object.defineProperty(HTMLMediaElement.prototype, "pause", {
  configurable: true,
  value: vi.fn()
})

describe("StudioPane Stage 2 workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    isMobile = false

    workspaceStoreState.selectedSourceIds = ["source-1"]
    workspaceStoreState.getSelectedMediaIds = () => [101]
    workspaceStoreState.generatedArtifacts = []
    workspaceStoreState.isGeneratingOutput = false
    workspaceStoreState.generatingOutputType = null
    workspaceStoreState.noteFocusTarget = null
    mockCaptureToCurrentNote.mockReset()

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

    mockSetIsGeneratingOutput.mockImplementation((isGenerating: boolean, outputType: string | null = null) => {
      workspaceStoreState.isGeneratingOutput = isGenerating
      workspaceStoreState.generatingOutputType = isGenerating ? outputType : null
    })

    mockListDecks.mockResolvedValue([])
    mockCreateDeck.mockResolvedValue({ id: 1, name: "Workspace Flashcards" })
    mockCreateFlashcard.mockResolvedValue({ uuid: "card-1" })
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
    mockGenerateQuiz.mockResolvedValue({
      quiz: { id: 11, name: "Quiz", description: "" },
      questions: [
        {
          question_text: "Q",
          options: ["A", "B"],
          correct_answer: "A",
          explanation: "Because"
        }
      ]
    })
  })

  it("dispatches discuss event for completed artifacts", () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-discuss",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Discuss this summary",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    const dispatchSpy = vi.spyOn(window, "dispatchEvent")

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Discuss in chat" }))

    expect(dispatchSpy).toHaveBeenCalledTimes(1)
    const dispatchedEvent = dispatchSpy.mock.calls[0]?.[0] as CustomEvent<any>
    expect(dispatchedEvent.type).toBe("workspace-playground:discuss-artifact")
    expect(dispatchedEvent.detail).toEqual(
      expect.objectContaining({
        artifactId: "artifact-discuss",
        artifactType: "summary",
        title: "Summary",
        content: "Discuss this summary"
      })
    )
  })

  it("saves artifact content to note draft with append and replace modes", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-note",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Artifact content for notes",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Save to notes" }))
    fireEvent.click(await screen.findByText("Append to notes"))

    expect(mockCaptureToCurrentNote).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Summary",
        content: "Artifact content for notes",
        mode: "append"
      })
    )

    fireEvent.click(screen.getByRole("button", { name: "Save to notes" }))
    fireEvent.click(await screen.findByText("Replace note draft"))

    expect(mockCaptureToCurrentNote).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Summary",
        content: "Artifact content for notes",
        mode: "replace"
      })
    )
  })

  it("generates quiz content across all selected media", async () => {
    workspaceStoreState.selectedSourceIds = ["source-1", "source-2"]
    workspaceStoreState.getSelectedMediaIds = () => [101, 202]

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Quiz" }))

    await waitFor(() => {
      expect(mockGenerateQuiz).toHaveBeenCalledTimes(2)
    })

    expect(mockGenerateQuiz).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ media_id: 101 }),
      expect.any(Object)
    )
    expect(mockGenerateQuiz).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ media_id: 202 }),
      expect.any(Object)
    )
  })

  it("renders mind map diagrams from fenced mermaid content", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-mindmap",
        type: "mindmap",
        title: "Mind Map",
        status: "completed",
        content:
          "```mermaid\nmindmap\n  root((Workspace))\n    Findings\n```",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "View" }))

    expect(await screen.findByTestId("mermaid")).toHaveTextContent(
      /mindmap\s+root\(\(Workspace\)\)\s+Findings/
    )
    expect(
      await screen.findByRole("button", { name: "Export SVG" })
    ).toBeInTheDocument()
  })

  it("falls back to raw content for non-mermaid mind map output", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-mindmap-raw",
        type: "mindmap",
        title: "Mind Map",
        status: "completed",
        content: "This output could not be converted into Mermaid markup.",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "View" }))

    expect(
      await screen.findByText(/Unable to render this mind map as a diagram/)
    ).toBeInTheDocument()
    expect(
      await screen.findByText("This output could not be converted into Mermaid markup.")
    ).toBeInTheDocument()
  })

  it("parses markdown tables and exports CSV", async () => {
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:table")
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {})
    const anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {})

    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-table",
        type: "data_table",
        title: "Data Table",
        status: "completed",
        content:
          "| Name | Score |\n|---|---|\n| Alice | 89 |\n| Bob | 95 |",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)
    fireEvent.click(screen.getByRole("button", { name: "View" }))

    fireEvent.change(await screen.findByPlaceholderText("Filter table rows"), {
      target: { value: "Bob" }
    })

    expect(screen.getByText("Bob")).toBeInTheDocument()
    expect(screen.queryByText("Alice")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }))

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalled()
    })
    expect(anchorClickSpy).toHaveBeenCalled()
    expect(revokeObjectUrlSpy).toHaveBeenCalled()

    const csvBlob = createObjectUrlSpy.mock.calls.at(-1)?.[0] as Blob & {
      type?: string
    }
    expect(csvBlob).toBeTruthy()
    expect(csvBlob.type).toContain("text/csv")

    createObjectUrlSpy.mockRestore()
    revokeObjectUrlSpy.mockRestore()
    anchorClickSpy.mockRestore()
  })

  it("saves flashcard edits back into artifact content and structured data", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-flashcards",
        type: "flashcards",
        title: "Flashcards",
        status: "completed",
        content: "Front: Old front\nBack: Old back",
        data: {
          flashcards: [{ front: "Old front", back: "Old back" }]
        },
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)
    fireEvent.click(screen.getByRole("button", { name: "Edit" }))

    fireEvent.change(await screen.findByPlaceholderText("Front (question or term)"), {
      target: { value: "Updated front" }
    })
    fireEvent.change(await screen.findByPlaceholderText("Back (answer or definition)"), {
      target: { value: "Updated back" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-flashcards",
        "completed",
        expect.objectContaining({
          content: "Front: Updated front\nBack: Updated back",
          data: expect.objectContaining({
            flashcards: [{ front: "Updated front", back: "Updated back" }]
          })
        })
      )
    })
  })

  it("saves quiz edits back into artifact content and structured data", async () => {
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-quiz",
        type: "quiz",
        title: "Quiz",
        status: "completed",
        content:
          "Quiz: Quiz\nTotal Questions: 1\n\nQ1: Old question\n  A. Old option\nAnswer: Old answer\nExplanation: Old explanation\n",
        data: {
          questions: [
            {
              question: "Old question",
              options: ["Old option"],
              answer: "Old answer",
              explanation: "Old explanation"
            }
          ]
        },
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    render(<StudioPane />)
    fireEvent.click(screen.getByRole("button", { name: "Edit" }))

    fireEvent.change(await screen.findByPlaceholderText("Question prompt"), {
      target: { value: "Updated question" }
    })
    fireEvent.change(await screen.findByPlaceholderText("Options (one per line)"), {
      target: { value: "Option A\nOption B" }
    })
    fireEvent.change(await screen.findByPlaceholderText("Correct answer"), {
      target: { value: "Option A" }
    })
    fireEvent.change(await screen.findByPlaceholderText("Explanation (optional)"), {
      target: { value: "Updated explanation" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => {
      expect(mockUpdateArtifactStatus).toHaveBeenCalledWith(
        "artifact-quiz",
        "completed",
        expect.objectContaining({
          content: expect.stringContaining("Q1: Updated question"),
          data: expect.objectContaining({
            questions: [
              {
                question: "Updated question",
                options: ["Option A", "Option B"],
                answer: "Option A",
                explanation: "Updated explanation"
              }
            ]
          })
        })
      )
    })
  })

  it("uses selected flashcard deck when generating flashcards", async () => {
    mockListDecks.mockResolvedValue([
      { id: 4, name: "Biology Deck", card_count: 0, created_at: null, updated_at: null }
    ])
    mockRagSearch.mockResolvedValue({
      generation: "Front: ATP\nBack: Cellular energy"
    })

    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Audio Settings" }))
    const autoDeckLabel = await screen.findByText("Auto (first deck or create new)")
    fireEvent.mouseDown(autoDeckLabel.closest(".ant-select-selector") || autoDeckLabel)
    fireEvent.click(await screen.findByText("Biology Deck"))

    fireEvent.click(screen.getByRole("button", { name: "Flashcards" }))

    await waitFor(() => {
      expect(mockCreateFlashcard).toHaveBeenCalled()
    })

    expect(mockCreateFlashcard).toHaveBeenCalledWith(
      expect.objectContaining({
        deck_id: 4,
        front: "ATP",
        back: "Cellular energy",
        source_ref_id: "101"
      }),
      expect.any(Object)
    )
  })

  it("requests voice preview audio from TTS provider", async () => {
    render(<StudioPane />)

    fireEvent.click(screen.getByRole("button", { name: "Audio Settings" }))
    fireEvent.click(screen.getByRole("button", { name: "Preview" }))

    await waitFor(() => {
      expect(mockSynthesizeSpeech).toHaveBeenCalledWith(
        "This is a quick voice preview from your current audio settings.",
        expect.objectContaining({
          model: "kokoro",
          voice: "af_heart",
          responseFormat: "mp3",
          speed: 1
        })
      )
    })
  })

  it("uses fullscreen modal sizing when viewing outputs on mobile", () => {
    isMobile = true
    workspaceStoreState.generatedArtifacts = [
      {
        id: "artifact-summary-mobile",
        type: "summary",
        title: "Summary",
        status: "completed",
        content: "Mobile view content",
        createdAt: new Date("2026-02-18T10:00:00.000Z")
      }
    ]

    const modalInfoSpy = vi
      .spyOn(Modal, "info")
      .mockImplementation(
        () =>
          ({
            destroy: vi.fn(),
            update: vi.fn()
          }) as any
      )

    render(<StudioPane />)
    fireEvent.click(screen.getByRole("button", { name: "View" }))

    expect(modalInfoSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        width: "100%",
        style: expect.objectContaining({ top: 0, paddingBottom: 0 }),
        styles: expect.objectContaining({
          body: expect.objectContaining({
            maxHeight: "calc(100dvh - 96px)",
            overflowY: "auto"
          })
        })
      })
    )

    modalInfoSpy.mockRestore()
  })
})
