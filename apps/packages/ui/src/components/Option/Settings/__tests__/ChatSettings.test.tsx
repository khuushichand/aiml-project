import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ChatSettings } from "../ChatSettings"

const {
  useChatSettingsMock,
  useSettingMock,
  setChatBackgroundImageMock,
  notificationErrorMock,
  toBase64Mock
} = vi.hoisted(() => ({
  useChatSettingsMock: vi.fn(),
  useSettingMock: vi.fn(),
  setChatBackgroundImageMock: vi.fn(),
  notificationErrorMock: vi.fn(),
  toBase64Mock: vi.fn()
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

vi.mock("@/hooks/useChatSettings", () => ({
  useChatSettings: useChatSettingsMock
}))

vi.mock("@/hooks/useSetting", () => ({
  useSetting: useSettingMock
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    error: notificationErrorMock
  })
}))

vi.mock("@/libs/to-base64", () => ({
  toBase64: toBase64Mock
}))

vi.mock("../DiscoSkillsSettings", () => ({
  DiscoSkillsSettings: () => <div>Disco Skills</div>
}))

const buildChatSettingsState = () => ({
  copilotResumeLastChat: false,
  setCopilotResumeLastChat: vi.fn(),
  defaultChatWithWebsite: false,
  setDefaultChatWithWebsite: vi.fn(),
  webUIResumeLastChat: false,
  setWebUIResumeLastChat: vi.fn(),
  hideCurrentChatModelSettings: false,
  setHideCurrentChatModelSettings: vi.fn(),
  hideQuickChatHelper: false,
  setHideQuickChatHelper: vi.fn(),
  restoreLastChatModel: false,
  setRestoreLastChatModel: vi.fn(),
  generateTitle: false,
  setGenerateTitle: vi.fn(),
  checkWideMode: false,
  setCheckWideMode: vi.fn(),
  stickyChatInput: false,
  setStickyChatInput: vi.fn(),
  menuDensity: "comfortable" as const,
  setMenuDensity: vi.fn(),
  openReasoning: false,
  setOpenReasoning: vi.fn(),
  userChatBubble: true,
  setUserChatBubble: vi.fn(),
  autoCopyResponseToClipboard: false,
  setAutoCopyResponseToClipboard: vi.fn(),
  useMarkdownForUserMessage: false,
  setUseMarkdownForUserMessage: vi.fn(),
  copyAsFormattedText: false,
  setCopyAsFormattedText: vi.fn(),
  allowExternalImages: false,
  setAllowExternalImages: vi.fn(),
  tabMentionsEnabled: false,
  setTabMentionsEnabled: vi.fn(),
  pasteLargeTextAsFile: false,
  setPasteLargeTextAsFile: vi.fn(),
  sidepanelTemporaryChat: false,
  setSidepanelTemporaryChat: vi.fn(),
  removeReasoningTagFromCopy: false,
  setRemoveReasoningTagFromCopy: vi.fn(),
  promptSearchIncludeServer: false,
  setPromptSearchIncludeServer: vi.fn(),
  userTextColor: "default" as const,
  setUserTextColor: vi.fn(),
  assistantTextColor: "default" as const,
  setAssistantTextColor: vi.fn(),
  userTextFont: "default" as const,
  setUserTextFont: vi.fn(),
  assistantTextFont: "default" as const,
  setAssistantTextFont: vi.fn(),
  userTextSize: "md" as const,
  setUserTextSize: vi.fn(),
  assistantTextSize: "md" as const,
  setAssistantTextSize: vi.fn()
})

describe("ChatSettings background image controls", () => {
  beforeEach(() => {
    useChatSettingsMock.mockReturnValue(buildChatSettingsState())
    useSettingMock.mockReturnValue([
      undefined,
      setChatBackgroundImageMock,
      { isLoading: false }
    ])
    setChatBackgroundImageMock.mockReset()
    setChatBackgroundImageMock.mockResolvedValue(undefined)
    notificationErrorMock.mockReset()
    toBase64Mock.mockReset()
    toBase64Mock.mockResolvedValue("data:image/png;base64,abc123")
  })

  it("rejects non-image uploads", async () => {
    const { container } = render(<ChatSettings />)
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null
    expect(fileInput).not.toBeNull()

    const invalidFile = new File(["not image"], "notes.txt", {
      type: "text/plain"
    })
    fireEvent.change(fileInput as HTMLInputElement, {
      target: { files: [invalidFile] }
    })

    await waitFor(() => {
      expect(notificationErrorMock).toHaveBeenCalled()
    })
    expect(toBase64Mock).not.toHaveBeenCalled()
    expect(setChatBackgroundImageMock).not.toHaveBeenCalled()
  })

  it("uploads valid images and persists the setting", async () => {
    const { container } = render(<ChatSettings />)
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null
    expect(fileInput).not.toBeNull()

    const imageFile = new File(["fake image"], "chat-bg.png", {
      type: "image/png"
    })
    fireEvent.change(fileInput as HTMLInputElement, {
      target: { files: [imageFile] }
    })

    await waitFor(() => {
      expect(toBase64Mock).toHaveBeenCalledWith(imageFile)
      expect(setChatBackgroundImageMock).toHaveBeenCalledWith(
        "data:image/png;base64,abc123"
      )
    })
  })

  it("shows and handles remove button when a background is set", async () => {
    useSettingMock.mockReturnValue([
      "data:image/png;base64,existing",
      setChatBackgroundImageMock,
      { isLoading: false }
    ])

    render(<ChatSettings />)
    fireEvent.click(
      screen.getByRole("button", { name: "Remove background image" })
    )

    await waitFor(() => {
      expect(setChatBackgroundImageMock).toHaveBeenCalledWith(undefined)
    })
  })
})
