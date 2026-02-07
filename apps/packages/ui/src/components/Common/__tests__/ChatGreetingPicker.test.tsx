import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import type { Character } from "@/types/character"
import { ChatGreetingPicker } from "../ChatGreetingPicker"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"
import {
  buildGreetingOptionsFromEntries,
  buildGreetingsChecksumFromOptions,
  collectGreetingEntries
} from "@/utils/character-greetings"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) =>
      options?.defaultValue || key
  })
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: () => [""]
}))

vi.mock("antd", () => ({
  Select: ({ value, onChange, options, disabled }: any) => (
    <select
      data-testid="greeting-select"
      value={value ?? ""}
      onChange={(event) => onChange?.(event.target.value)}
      disabled={disabled}
    >
      {(options ?? []).map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
  Switch: ({ checked, onChange }: any) => (
    <input
      type="checkbox"
      role="switch"
      checked={Boolean(checked)}
      onChange={(event) => onChange?.(event.target.checked)}
    />
  )
}))

vi.mock("@/hooks/chat/useChatSettingsRecord", () => ({
  useChatSettingsRecord: vi.fn()
}))

const character = {
  id: "char-1",
  name: "Guide",
  greeting: "Welcome aboard",
  alternateGreetings: ["Good to see you"]
} as Character

const greetingEntries = collectGreetingEntries(character)
const greetingOptions = buildGreetingOptionsFromEntries(greetingEntries)
const checksum = buildGreetingsChecksumFromOptions(greetingOptions)
const defaultGreetingId = greetingOptions[0]?.id ?? null
const alternateGreetingId = greetingOptions[1]?.id ?? null

const renderPicker = (
  settings: Record<string, unknown>,
  updateSettings: ReturnType<typeof vi.fn>
) => {
  vi.mocked(useChatSettingsRecord).mockReturnValue({
    settings,
    updateSettings,
    chatKey: "chat:test"
  })

  render(
    <ChatGreetingPicker
      selectedCharacter={character}
      messages={[]}
      historyId="history-1"
      serverChatId={null}
    />
  )
}

describe("ChatGreetingPicker", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("falls back to current selection when disabling default without stored selection", () => {
    const updateSettings = vi.fn().mockResolvedValue(null)
    renderPicker(
      {
        useCharacterDefault: true,
        greetingSelectionId: null,
        greetingsChecksum: checksum
      },
      updateSettings
    )

    const [useDefaultSwitch] = screen.getAllByRole("switch")
    fireEvent.click(useDefaultSwitch)

    expect(updateSettings).toHaveBeenCalledWith({
      useCharacterDefault: false,
      greetingSelectionId: defaultGreetingId,
      greetingsChecksum: checksum
    })
  })

  it("keeps stored greeting selection when disabling default", () => {
    const updateSettings = vi.fn().mockResolvedValue(null)
    renderPicker(
      {
        useCharacterDefault: true,
        greetingSelectionId: alternateGreetingId,
        greetingsChecksum: checksum
      },
      updateSettings
    )

    const [useDefaultSwitch] = screen.getAllByRole("switch")
    fireEvent.click(useDefaultSwitch)

    expect(updateSettings).toHaveBeenCalledWith({
      useCharacterDefault: false,
      greetingSelectionId: alternateGreetingId,
      greetingsChecksum: checksum
    })
  })
})
