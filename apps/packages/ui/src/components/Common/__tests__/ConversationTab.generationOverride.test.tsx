import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ConversationTab } from "../Settings/tabs/ConversationTab"
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

vi.mock("antd", () => {
  const FormItem = ({ label, help, children }: any) => (
    <div>
      {label ? <label>{label}</label> : null}
      {children}
      {help ? <div>{help}</div> : null}
    </div>
  )
  const Form = ({ children }: any) => <div>{children}</div>
  Form.Item = FormItem

  const Select = ({ value, options = [], onChange, mode, ...rest }: any) => (
    <select
      data-testid={rest["data-testid"] || "ant-select"}
      multiple={mode === "multiple"}
      value={value ?? (mode === "multiple" ? [] : "")}
      onChange={(event) => {
        if (mode === "multiple") {
          const values = Array.from(event.currentTarget.selectedOptions).map(
            (option) => option.value
          )
          onChange?.(values)
          return
        }
        onChange?.(event.currentTarget.value)
      }}
    >
      {(options || []).map((option: any) => (
        <option key={String(option.value)} value={String(option.value)}>
          {String(option.label)}
        </option>
      ))}
    </select>
  )

  const Input = ({ value, onChange, onBlur, placeholder }: any) => (
    <input
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(event) => onChange?.(event)}
      onBlur={onBlur}
    />
  )
  Input.TextArea = ({ value, onChange, onBlur, placeholder, disabled }: any) => (
    <textarea
      value={value ?? ""}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(event) => onChange?.(event)}
      onBlur={onBlur}
    />
  )

  const InputNumber = ({ value, onChange, onBlur, disabled, ...rest }: any) => (
    <input
      type="number"
      data-testid={rest["data-testid"] || "ant-input-number"}
      value={value ?? ""}
      disabled={disabled}
      onChange={(event) => {
        const raw = event.currentTarget.value
        onChange?.(raw === "" ? null : Number(raw))
      }}
      onBlur={onBlur}
    />
  )

  return { Form, Select, Input, InputNumber }
})

describe("ConversationTab generation override controls", () => {
  const updateSettings = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useChatSettingsRecord).mockReturnValue({
      settings: {
        chatGenerationOverride: {
          enabled: false
        }
      },
      updateSettings,
      chatKey: "chat:test"
    } as any)
  })

  const renderConversationTab = () =>
    render(
      <ConversationTab
        historyId="history-1"
        selectedSystemPrompt={null}
        onSystemPromptChange={() => {}}
        uploadedFiles={[]}
        onRemoveFile={() => {}}
        serverChatId="chat-1"
        serverChatState="in-progress"
        onStateChange={() => {}}
        serverChatTopic={null}
        onTopicChange={() => {}}
        onVersionChange={() => {}}
      />
    )

  it("persists enabled chat generation override", async () => {
    renderConversationTab()

    const section = screen.getByTestId("chat-generation-override")
    const modeSelect = within(section).getByRole("combobox")
    fireEvent.change(modeSelect, { target: { value: "on" } })

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          chatGenerationOverride: expect.objectContaining({
            enabled: true
          })
        })
      )
    })
  })

  it("parses and de-duplicates stop sequences on blur", async () => {
    renderConversationTab()

    const section = screen.getByTestId("chat-generation-override")
    const modeSelect = within(section).getByRole("combobox")
    fireEvent.change(modeSelect, { target: { value: "on" } })

    const stopInput = within(section).getByPlaceholderText(
      "Stop sequences, one per line"
    )
    await waitFor(() => {
      expect(stopInput).not.toBeDisabled()
    })
    fireEvent.change(stopInput, {
      target: { value: "END\nEND\nSTOP" }
    })
    fireEvent.blur(stopInput)

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          chatGenerationOverride: expect.objectContaining({
            stop: ["END", "STOP"]
          })
        })
      )
    })
  })
})
