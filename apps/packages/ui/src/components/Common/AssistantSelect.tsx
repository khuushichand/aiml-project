import React from "react"
import { UserCircle2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useSelectedAssistant } from "@/hooks/useSelectedAssistant"
import {
  characterToAssistantSelection,
  personaToAssistantSelection,
  type AssistantSelection
} from "@/types/assistant-selection"

type Props = {
  className?: string
  iconClassName?: string
  showLabel?: boolean
  variant?: "inline" | "dropdown"
}

type CharacterSummary = Record<string, unknown> & {
  id?: string | number
  slug?: string
  name?: string
  title?: string
  avatar_url?: string
  system_prompt?: string
  greeting?: string
  extensions?: Record<string, unknown> | null
}

type PersonaSummary = Record<string, unknown> & {
  id?: string | number
  name?: string | null
  avatar_url?: string | null
  system_prompt?: string | null
  greeting?: string | null
  extensions?: Record<string, unknown> | null
}

const normalizeCharacterSelection = (
  character: CharacterSummary
): AssistantSelection | null => {
  const normalizedId =
    character.id != null
      ? String(character.id)
      : typeof character.slug === "string" && character.slug.trim().length > 0
        ? character.slug.trim()
        : null
  const normalizedName =
    typeof character.name === "string" && character.name.trim().length > 0
      ? character.name.trim()
      : typeof character.title === "string" && character.title.trim().length > 0
        ? character.title.trim()
        : normalizedId
  if (!normalizedId || !normalizedName) return null
  return characterToAssistantSelection({
    ...character,
    id: normalizedId,
    name: normalizedName
  })
}

const normalizePersonaSelection = (
  persona: PersonaSummary
): AssistantSelection | null => {
  const normalizedId =
    persona.id != null ? String(persona.id) : null
  const normalizedName =
    typeof persona.name === "string" && persona.name.trim().length > 0
      ? persona.name.trim()
      : normalizedId
  if (!normalizedId || !normalizedName) return null
  return personaToAssistantSelection({
    ...persona,
    id: normalizedId,
    name: normalizedName
  })
}

const renderSelectionList = ({
  entries,
  activeSelection,
  onSelect,
  emptyLabel
}: {
  entries: AssistantSelection[]
  activeSelection: AssistantSelection | null
  onSelect: (entry: AssistantSelection) => void
  emptyLabel: string
}) => {
  if (entries.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-sm text-text-subtle">
        {emptyLabel}
      </div>
    )
  }

  return (
    <div className="max-h-80 overflow-y-auto px-2 py-2">
      <div className="flex flex-col gap-1">
        {entries.map((entry) => {
          const isActive =
            activeSelection?.kind === entry.kind &&
            activeSelection?.id === entry.id
          return (
            <button
              key={`${entry.kind}:${entry.id}`}
              type="button"
              className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                isActive
                  ? "border-primary bg-primary/10 text-text"
                  : "border-border bg-background text-text hover:bg-surface2"
              }`}
              onClick={() => onSelect(entry)}
            >
              <span className="block truncate font-medium">{entry.name}</span>
              <span className="block truncate text-xs text-text-subtle">
                {entry.kind === "persona" ? "Persona" : "Character"}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export const AssistantSelect: React.FC<Props> = ({
  className = "text-text-muted",
  iconClassName = "size-5",
  showLabel = true,
  variant = "inline"
}) => {
  const { t } = useTranslation(["option", "common"])
  const [selectedAssistant, setSelectedAssistant] =
    useSelectedAssistant(null)
  const [open, setOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<"character" | "persona">(
    selectedAssistant?.kind ?? "character"
  )
  const [characters, setCharacters] = React.useState<CharacterSummary[]>([])
  const [personas, setPersonas] = React.useState<PersonaSummary[]>([])

  React.useEffect(() => {
    if (selectedAssistant?.kind === "character" || selectedAssistant?.kind === "persona") {
      setActiveTab(selectedAssistant.kind)
    }
  }, [selectedAssistant?.kind])

  React.useEffect(() => {
    let cancelled = false

    const loadOptions = async () => {
      await tldwClient.initialize().catch(() => null)

      if (typeof tldwClient.listAllCharacters === "function") {
        const result = await tldwClient.listAllCharacters().catch(() => [])
        if (!cancelled && Array.isArray(result)) {
          setCharacters(result as CharacterSummary[])
        }
      }

      if (typeof tldwClient.listPersonaProfiles === "function") {
        const result = await tldwClient.listPersonaProfiles().catch(() => [])
        if (!cancelled && Array.isArray(result)) {
          setPersonas(result as PersonaSummary[])
        }
      }
    }

    void loadOptions()
    return () => {
      cancelled = true
    }
  }, [])

  const characterEntries = React.useMemo(
    () =>
      characters
        .map(normalizeCharacterSelection)
        .filter((entry): entry is AssistantSelection => Boolean(entry)),
    [characters]
  )
  const personaEntries = React.useMemo(
    () =>
      personas
        .map(normalizePersonaSelection)
        .filter((entry): entry is AssistantSelection => Boolean(entry)),
    [personas]
  )

  const handleSelect = React.useCallback(
    async (entry: AssistantSelection) => {
      await setSelectedAssistant(entry)
      setOpen(false)
    },
    [setSelectedAssistant]
  )

  const buttonLabel =
    selectedAssistant?.name ||
    t("option:assistant.selectAssistant", "Select assistant")

  const tabs = [
    {
      key: "character" as const,
      label: t("option:assistant.charactersTab", "Characters"),
      content: renderSelectionList({
        entries: characterEntries,
        activeSelection: selectedAssistant,
        onSelect: handleSelect,
        emptyLabel: t("option:assistant.noCharacters", "No characters available.")
      })
    },
    {
      key: "persona" as const,
      label: t("option:assistant.personasTab", "Personas"),
      content: renderSelectionList({
        entries: personaEntries,
        activeSelection: selectedAssistant,
        onSelect: handleSelect,
        emptyLabel: t("option:assistant.noPersonas", "No personas available.")
      })
    }
  ]
  const activeTabContent =
    tabs.find((tab) => tab.key === activeTab)?.content ?? tabs[0]?.content ?? null

  const content = (
    <div className="w-[320px] rounded-lg border border-border bg-background shadow-lg">
      <div
        role="tablist"
        aria-label={t("option:assistant.tabList", "Assistant types")}
        className="flex items-center gap-1 border-b border-border px-2 pt-2"
      >
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab
          return (
            <button
              key={tab.key}
              id={`assistant-tab-${tab.key}`}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`assistant-tabpanel-${tab.key}`}
              className={`rounded-t-md px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-surface2 font-medium text-text"
                  : "text-text-subtle hover:text-text"
              }`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      <div
        id={`assistant-tabpanel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`assistant-tab-${activeTab}`}
      >
        {activeTabContent}
      </div>
    </div>
  )

  if (variant === "inline") {
    return content
  }

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="character-select"
        className={`inline-flex items-center gap-2 ${className}`.trim()}
        aria-label={buttonLabel}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <UserCircle2 className={iconClassName} />
        {showLabel ? (
          <span className="max-w-[180px] truncate text-sm">{buttonLabel}</span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute left-0 top-full z-50 mt-2">
          {content}
        </div>
      ) : null}
    </div>
  )
}

export default AssistantSelect
