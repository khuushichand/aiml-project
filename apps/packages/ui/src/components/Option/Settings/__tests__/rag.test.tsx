import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { RagSettings } from "../rag"

const {
  useStorageMock,
  useKnowledgeSettingsMock,
  applySettingsMock,
  discardChangesMock,
  setUseCurrentMessageMock,
  updateSettingMock,
  applyPresetMock,
  resetToBalancedMock,
  setAdvancedSearchMock,
  setChatWithWebsiteEmbeddingMock,
  setMaxWebsiteContextMock
} = vi.hoisted(() => ({
  useStorageMock: vi.fn(),
  useKnowledgeSettingsMock: vi.fn(),
  applySettingsMock: vi.fn(),
  discardChangesMock: vi.fn(),
  setUseCurrentMessageMock: vi.fn(),
  updateSettingMock: vi.fn(),
  applyPresetMock: vi.fn(),
  resetToBalancedMock: vi.fn(),
  setAdvancedSearchMock: vi.fn(),
  setChatWithWebsiteEmbeddingMock: vi.fn(),
  setMaxWebsiteContextMock: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: useStorageMock
}))

vi.mock("@/components/Knowledge/hooks", () => ({
  useKnowledgeSettings: useKnowledgeSettingsMock
}))

vi.mock("@/components/Knowledge/SettingsTab", () => ({
  SettingsTab: () => <div data-testid="mock-settings-tab" />
}))

const buildKnowledgeSettingsState = (overrides?: Record<string, unknown>) => ({
  preset: "balanced",
  draftSettings: {
    search_mode: "hybrid",
    top_k: 8,
    enable_generation: true,
    enable_citations: true,
    sources: ["media_db"]
  },
  advancedSearch: "",
  isDirty: true,
  useCurrentMessage: true,
  applySettings: applySettingsMock,
  discardChanges: discardChangesMock,
  setUseCurrentMessage: setUseCurrentMessageMock,
  setAdvancedSearch: setAdvancedSearchMock,
  updateSetting: updateSettingMock,
  applyPreset: applyPresetMock,
  resetToBalanced: resetToBalancedMock,
  ...overrides
})

const configureStorage = (options?: {
  chatWithWebsiteEmbedding?: boolean
  maxWebsiteContext?: number
}) => {
  const chatWithWebsiteEmbedding = options?.chatWithWebsiteEmbedding ?? false
  const maxWebsiteContext = options?.maxWebsiteContext ?? 7028

  useStorageMock.mockImplementation((key: string, defaultValue: unknown) => {
    if (key === "chatWithWebsiteEmbedding") {
      return [chatWithWebsiteEmbedding, setChatWithWebsiteEmbeddingMock]
    }
    if (key === "maxWebsiteContext") {
      return [maxWebsiteContext, setMaxWebsiteContextMock]
    }
    return [defaultValue, vi.fn()]
  })
}

describe("RagSettings", () => {
  beforeEach(() => {
    applySettingsMock.mockReset()
    discardChangesMock.mockReset()
    setUseCurrentMessageMock.mockReset()
    updateSettingMock.mockReset()
    applyPresetMock.mockReset()
    resetToBalancedMock.mockReset()
    setAdvancedSearchMock.mockReset()
    setChatWithWebsiteEmbeddingMock.mockReset()
    setMaxWebsiteContextMock.mockReset()

    configureStorage()
    useKnowledgeSettingsMock.mockReturnValue(buildKnowledgeSettingsState())
  })

  it("saves shared defaults when save button is clicked", () => {
    render(<RagSettings />)

    fireEvent.click(screen.getByRole("button", { name: "Save defaults" }))

    expect(applySettingsMock).toHaveBeenCalledTimes(1)
  })

  it("updates chat embedding toggle", () => {
    render(<RagSettings />)

    fireEvent.click(
      screen.getByRole("switch", { name: "Enable Embedding and Retrieval" })
    )

    expect(setChatWithWebsiteEmbeddingMock).toHaveBeenCalledWith(true)
  })

  it("resets website context size to default", () => {
    configureStorage({ maxWebsiteContext: 8192 })
    useKnowledgeSettingsMock.mockReturnValue(buildKnowledgeSettingsState())

    render(<RagSettings />)

    fireEvent.click(screen.getByRole("button", { name: "Reset" }))

    expect(setMaxWebsiteContextMock).toHaveBeenCalledWith(7028)
  })
})
