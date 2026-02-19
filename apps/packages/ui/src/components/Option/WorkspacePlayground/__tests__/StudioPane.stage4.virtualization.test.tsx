import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { Modal } from "antd"
import { StudioPane } from "../StudioPane"

const {
  mockRemoveArtifact,
  mockSetIsGeneratingOutput,
  mockSetAudioSettings,
  mockCaptureToCurrentNote,
  mockMessageSuccess,
  mockMessageError,
  mockMessageInfo,
  workspaceStoreState
} = vi.hoisted(() => {
  const removeArtifact = vi.fn()
  const restoreArtifact = vi.fn()
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
    addArtifact: vi.fn(),
    updateArtifactStatus: vi.fn(),
    removeArtifact,
    restoreArtifact,
    setIsGeneratingOutput,
    setAudioSettings,
    captureToCurrentNote,
    noteFocusTarget: null as { field: "title" | "content"; token: number } | null
  }

  return {
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
  useMobile: () => false
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
  generateQuiz: vi.fn()
}))

vi.mock("@/services/flashcards", () => ({
  listDecks: vi.fn().mockResolvedValue([]),
  createDeck: vi.fn(),
  createFlashcard: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    ragSearch: vi.fn(),
    synthesizeSpeech: vi.fn(),
    generateSlidesFromMedia: vi.fn(),
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
          warning: vi.fn(),
          open: vi.fn(),
          destroy: vi.fn()
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

const buildArtifacts = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `artifact-${index}`,
    type: "summary",
    title: `Artifact ${index}`,
    status: "completed",
    content: `Content ${index}`,
    createdAt: new Date("2026-02-18T00:00:00.000Z")
  }))

describe("StudioPane Stage 4 outputs virtualization", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workspaceStoreState.generatedArtifacts = buildArtifacts(120)
    workspaceStoreState.isGeneratingOutput = false
    workspaceStoreState.generatingOutputType = null
    workspaceStoreState.noteFocusTarget = null
  })

  it("activates virtualization when artifact history is large", () => {
    render(<StudioPane />)

    const listContainer = screen.getByTestId("generated-outputs-virtualized")
    expect(listContainer).toHaveAttribute("data-virtualized", "true")
    expect(screen.getByText("Artifact 0")).toBeInTheDocument()
    expect(screen.queryByText("Artifact 90")).not.toBeInTheDocument()
  })

  it("keeps row actions functional after scrolling a virtualized list", async () => {
    const confirmSpy = vi
      .spyOn(Modal, "confirm")
      .mockImplementation((config: any) => {
        if (typeof config?.onOk === "function") {
          config.onOk()
        }
        return { destroy: vi.fn(), update: vi.fn() } as any
      })

    render(<StudioPane />)

    const listContainer = screen.getByTestId("generated-outputs-virtualized")
    fireEvent.scroll(listContainer, { target: { scrollTop: 4_500 } })

    await waitFor(() => {
      expect(screen.getByText("Artifact 30")).toBeInTheDocument()
    })

    const row = screen.getByText("Artifact 30").closest("div.group")
    expect(row).toBeTruthy()
    if (row) {
      expect(
        within(row).getByLabelText("Regenerate options")
      ).toBeInTheDocument()
      fireEvent.click(within(row).getByLabelText("Delete"))
    }

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(mockRemoveArtifact).toHaveBeenCalledWith("artifact-30")
  })
})

