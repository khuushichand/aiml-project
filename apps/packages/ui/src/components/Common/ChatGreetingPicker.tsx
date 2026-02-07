import React from "react"
import { RefreshCcw } from "lucide-react"
import { Select, Switch } from "antd"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"
import type { Character } from "@/types/character"
import type { Message } from "@/store/option/types"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"
import {
  buildGreetingOptionsFromEntries,
  buildGreetingsChecksumFromOptions,
  collectGreetingEntries,
  isGreetingMessageType
} from "@/utils/character-greetings"
import { replaceUserDisplayNamePlaceholders } from "@/utils/chat-display-name"

type Props = {
  selectedCharacter: Character | null
  messages: Message[]
  historyId: string | null
  serverChatId: string | null
  className?: string
}

export const ChatGreetingPicker: React.FC<Props> = ({
  selectedCharacter,
  messages,
  historyId,
  serverChatId,
  className
}) => {
  const { t } = useTranslation(["sidepanel", "common", "playground"])
  const [userDisplayName] = useStorage("chatUserDisplayName", "")
  const { settings, updateSettings } = useChatSettingsRecord({
    historyId,
    serverChatId
  })

  const hasNonGreetingMessages = React.useMemo(
    () =>
      messages.some(
        (message) => !isGreetingMessageType(message?.messageType)
      ),
    [messages]
  )

  const greetingEntries = React.useMemo(
    () => collectGreetingEntries(selectedCharacter),
    [selectedCharacter]
  )
  const greetingOptions = React.useMemo(
    () => buildGreetingOptionsFromEntries(greetingEntries),
    [greetingEntries]
  )
  const checksum = React.useMemo(
    () =>
      greetingOptions.length > 0
        ? buildGreetingsChecksumFromOptions(greetingOptions)
        : null,
    [greetingOptions]
  )
  const storedSelectionId =
    typeof settings?.greetingSelectionId === "string"
      ? settings.greetingSelectionId
      : null
  const storedChecksum =
    typeof settings?.greetingsChecksum === "string"
      ? settings.greetingsChecksum
      : null
  const greetingEnabled = settings?.greetingEnabled ?? true
  const useCharacterDefault = settings?.useCharacterDefault ?? false

  if (!selectedCharacter?.id) return null
  if (hasNonGreetingMessages) return null
  if (greetingOptions.length === 0) return null

  const resolvedSelection =
    storedChecksum && checksum && storedChecksum !== checksum
      ? null
      : greetingOptions.find((option) => option.id === storedSelectionId)
  const selectedOption =
    useCharacterDefault && greetingOptions.length > 0
      ? greetingOptions[0]
      : resolvedSelection || greetingOptions[0]
  const selectedOptionId = selectedOption?.id

  const previewText = selectedOption?.text
    ? replaceUserDisplayNamePlaceholders(
        selectedOption.text,
        userDisplayName
      )
    : ""

  const handleReroll = async () => {
    if (greetingOptions.length < 2) return
    const currentId = selectedOption?.id
    const candidates = greetingOptions.filter(
      (option) => option.id !== currentId
    )
    const next =
      candidates[Math.floor(Math.random() * candidates.length)] ||
      greetingOptions[0]
    await updateSettings({
      greetingSelectionId: next.id,
      greetingsChecksum: checksum,
      useCharacterDefault: false
    })
  }

  const handleSelectGreeting = async (value: string) => {
    await updateSettings({
      greetingSelectionId: value,
      greetingsChecksum: checksum,
      useCharacterDefault: false
    })
  }

  const handleUseDefault = async (checked: boolean) => {
    const defaultId = greetingOptions[0]?.id ?? null
    await updateSettings({
      useCharacterDefault: checked,
      greetingSelectionId: checked
        ? defaultId
        : storedSelectionId ?? selectedOption?.id ?? null,
      greetingsChecksum: checksum
    })
  }

  const handleToggle = async (checked: boolean) => {
    await updateSettings({ greetingEnabled: checked })
  }

  return (
    <div
      className={`w-full max-w-2xl rounded-2xl border border-border/60 bg-surface/80 p-3 text-xs text-text shadow-sm backdrop-blur ${className || ""}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
          {t("sidepanel:greetingPicker.title", { defaultValue: "Greeting" })}
        </div>
        <button
          type="button"
          onClick={handleReroll}
          disabled={greetingOptions.length < 2}
          className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-surface2 px-2 py-1 text-[11px] text-text-muted transition hover:border-primary/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCcw className="h-3 w-3" />
          {t("sidepanel:greetingPicker.reroll", { defaultValue: "Reroll" })}
        </button>
      </div>
      <div className="mt-2">
        <div className="mb-1 text-[10px] uppercase tracking-wide text-text-muted">
          {t("sidepanel:greetingPicker.pickLabel", {
            defaultValue: "Pick from list"
          })}
        </div>
        <Select
          value={selectedOptionId}
          onChange={handleSelectGreeting}
          disabled={useCharacterDefault}
          className="w-full"
          size="small"
          optionLabelProp="label"
          options={greetingOptions.map((option) => ({
            value: option.id,
            label: option.text,
            title: option.text,
            option
          }))}
          dropdownRender={(menu) => <div className="p-1">{menu}</div>}
          optionRender={(option) => {
            const data = (option.data as any)?.option || option.data
            const sourceLabel = data?.sourceLabel
              ? data.sourceLabel
              : t("sidepanel:greetingPicker.sourceUnknown", {
                  defaultValue: "Greeting"
                })
            const lengthLabel = t("sidepanel:greetingPicker.charCount", {
              defaultValue: "{{count}} chars",
              count: data?.text?.length || 0
            })
            return (
              <div className="flex flex-col gap-1">
                <div className="text-[10px] uppercase tracking-wide text-text-muted">
                  {sourceLabel} • {lengthLabel}
                </div>
                <div className="text-xs text-text line-clamp-2">
                  {data?.text}
                </div>
              </div>
            )
          }}
        />
        <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-text-muted">
          <div>
            {t("sidepanel:greetingPicker.useDefault", {
              defaultValue: "Use character default"
            })}
          </div>
          <Switch
            size="small"
            checked={useCharacterDefault}
            onChange={handleUseDefault}
          />
        </div>
      </div>
      {previewText && (
        <div className="mt-2 rounded-lg border border-border/40 bg-surface2/60 p-2 text-[12px] text-text">
          {previewText}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-text-muted">
        <div>
          {t("sidepanel:greetingPicker.includeInContext", {
            defaultValue: "Include greeting in context"
          })}
        </div>
        <Switch
          size="small"
          checked={greetingEnabled}
          onChange={handleToggle}
        />
      </div>
    </div>
  )
}
