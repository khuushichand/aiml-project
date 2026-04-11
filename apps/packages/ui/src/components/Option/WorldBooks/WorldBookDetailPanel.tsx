import React from "react"
import { Button, Form, Select, Tabs, Tag } from "antd"
import { ArrowLeft } from "lucide-react"
import { WorldBookEntryManager, DEFAULT_ENTRY_FILTER_PRESET } from "./WorldBookEntryManager"
import { WorldBookForm } from "./WorldBookForm"
import type { EntryFilterPreset } from "./WorldBookEntryManager"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Friendly relative-time label for last_modified timestamps */
const formatRelativeTime = (timestamp: number | null | undefined): string => {
  if (timestamp == null || !Number.isFinite(timestamp)) return ""
  const delta = Date.now() - timestamp
  if (delta < 0) return "just now"
  const seconds = Math.floor(delta / 1000)
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WorldBookDetailPanelProps = {
  worldBook: any | null
  attachedCharacters: any[]
  allWorldBooks: any[]
  allCharacters: any[]
  onUpdateWorldBook: (values: any) => void
  onAttachCharacter: (characterId: number) => Promise<void>
  onDetachCharacter: (characterId: number) => Promise<void>
  onOpenTestMatching: (worldBookId?: number) => void
  maxRecursiveDepth: number
  updating: boolean
  entryFormInstance: any
  entryFilterPreset?: EntryFilterPreset
  onBack?: () => void
}

// ---------------------------------------------------------------------------
// Attachments tab content
// ---------------------------------------------------------------------------

const AttachmentsTabContent: React.FC<{
  attachedCharacters: any[]
  allCharacters: any[]
  onAttachCharacter: (characterId: number) => Promise<void>
  onDetachCharacter: (characterId: number) => Promise<void>
}> = ({ attachedCharacters, allCharacters, onAttachCharacter, onDetachCharacter }) => {
  const [selectedCharacterId, setSelectedCharacterId] = React.useState<number | null>(null)
  const [attaching, setAttaching] = React.useState(false)

  const attachedIds = React.useMemo(
    () => new Set(attachedCharacters.map((c: any) => c.id)),
    [attachedCharacters]
  )

  const availableCharacters = React.useMemo(
    () => allCharacters.filter((c: any) => !attachedIds.has(c.id)),
    [allCharacters, attachedIds]
  )

  const handleAttach = React.useCallback(async () => {
    if (selectedCharacterId == null) return
    setAttaching(true)
    try {
      await onAttachCharacter(selectedCharacterId)
      setSelectedCharacterId(null)
    } finally {
      setAttaching(false)
    }
  }, [selectedCharacterId, onAttachCharacter])

  return (
    <div className="space-y-4">
      {/* Attached characters list */}
      <div>
        <h3 className="text-sm font-medium mb-2">
          Attached Characters ({attachedCharacters.length})
        </h3>
        {attachedCharacters.length === 0 ? (
          <p className="text-text-muted text-sm">No characters attached.</p>
        ) : (
          <div className="space-y-2">
            {attachedCharacters.map((character: any) => (
              <div
                key={character.id}
                className="flex items-center justify-between rounded border border-border px-3 py-2"
              >
                <span className="text-sm">{character.name}</span>
                <Button
                  danger
                  size="small"
                  onClick={() => onDetachCharacter(character.id)}
                >
                  Detach
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Attach new character */}
      {availableCharacters.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2">Attach a Character</h3>
          <div className="flex gap-2">
            <Select
              className="flex-1"
              placeholder="Select a character"
              value={selectedCharacterId}
              onChange={(value) => setSelectedCharacterId(value)}
              options={availableCharacters.map((c: any) => ({
                label: c.name,
                value: c.id
              }))}
              allowClear
            />
            <Button
              type="primary"
              disabled={selectedCharacterId == null}
              loading={attaching}
              onClick={handleAttach}
            >
              Attach
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Settings tab content
// ---------------------------------------------------------------------------

const SettingsTabContent: React.FC<{
  worldBook: any
  allWorldBooks: any[]
  maxRecursiveDepth: number
  updating: boolean
  onUpdateWorldBook: (values: any) => void
}> = ({ worldBook, allWorldBooks, maxRecursiveDepth, updating, onUpdateWorldBook }) => {
  const [form] = Form.useForm()

  React.useEffect(() => {
    if (worldBook) {
      form.setFieldsValue({
        name: worldBook.name,
        description: worldBook.description,
        enabled: worldBook.enabled,
        scan_depth: worldBook.scan_depth,
        token_budget: worldBook.token_budget,
        recursive_scanning: worldBook.recursive_scanning
      })
    }
  }, [worldBook, form])

  return (
    <WorldBookForm
      mode="edit"
      form={form}
      worldBooks={allWorldBooks}
      submitting={updating}
      currentWorldBookId={worldBook?.id}
      maxRecursiveDepth={maxRecursiveDepth}
      onSubmit={onUpdateWorldBook}
    />
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const WorldBookDetailPanel: React.FC<WorldBookDetailPanelProps> = ({
  worldBook,
  attachedCharacters,
  allWorldBooks,
  allCharacters,
  onUpdateWorldBook,
  onAttachCharacter,
  onDetachCharacter,
  onOpenTestMatching,
  maxRecursiveDepth,
  updating,
  entryFormInstance,
  entryFilterPreset,
  onBack
}) => {
  const headingRef = React.useRef<HTMLHeadingElement>(null)

  React.useEffect(() => {
    if (worldBook && headingRef.current) {
      headingRef.current.focus()
    }
  }, [worldBook?.id])

  // No-selection state
  if (worldBook == null) {
    return (
      <main aria-label="World book detail" className="flex items-center justify-center h-full">
        <p className="text-text-muted text-center">
          Select a world book to view its entries and settings
        </p>
      </main>
    )
  }

  const entryCount = typeof worldBook.entry_count === "number" ? worldBook.entry_count : 0
  const characterCount = attachedCharacters.length

  const tabItems = [
    {
      key: "entries",
      label: "Entries",
      children: (
        <WorldBookEntryManager
          worldBookId={worldBook.id}
          worldBookName={worldBook.name}
          tokenBudget={worldBook.token_budget}
          worldBooks={allWorldBooks}
          entryFilterPreset={entryFilterPreset ?? DEFAULT_ENTRY_FILTER_PRESET}
          form={entryFormInstance}
        />
      )
    },
    {
      key: "attachments",
      label: "Attachments",
      children: (
        <AttachmentsTabContent
          attachedCharacters={attachedCharacters}
          allCharacters={allCharacters}
          onAttachCharacter={onAttachCharacter}
          onDetachCharacter={onDetachCharacter}
        />
      )
    },
    {
      key: "stats",
      label: "Stats",
      children: (
        <div data-testid="stats-tab-content">
          Statistics loading...
        </div>
      )
    },
    {
      key: "settings",
      label: "Settings",
      children: (
        <SettingsTabContent
          worldBook={worldBook}
          allWorldBooks={allWorldBooks}
          maxRecursiveDepth={maxRecursiveDepth}
          updating={updating}
          onUpdateWorldBook={onUpdateWorldBook}
        />
      )
    }
  ]

  return (
    <main aria-label="World book detail" className="flex flex-col h-full">
      {/* Back button (mobile navigation) */}
      {onBack && (
        <button
          className="mb-2 flex items-center gap-1 text-sm text-primary hover:underline"
          onClick={onBack}
          aria-label="Back to world books list"
        >
          <ArrowLeft className="w-4 h-4" /> World Books
        </button>
      )}

      {/* Summary bar */}
      <div className="px-4 py-3 border-b border-border flex flex-wrap items-center gap-3">
        <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold m-0">
          {worldBook.name}
        </h2>
        <Tag color={worldBook.enabled ? "green" : "default"}>
          {worldBook.enabled ? "Enabled" : "Disabled"}
        </Tag>
        <span className="text-sm text-text-muted">
          {entryCount} {entryCount === 1 ? "entry" : "entries"}
        </span>
        {worldBook.token_budget != null && (
          <span className="text-sm text-text-muted">
            Budget: {worldBook.token_budget}
          </span>
        )}
        <span className="text-sm text-text-muted">
          {characterCount} {characterCount === 1 ? "character" : "characters"}
        </span>
        {worldBook.last_modified != null && (
          <span className="text-xs text-text-muted">
            {formatRelativeTime(worldBook.last_modified)}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex-1 overflow-auto px-4">
        <Tabs defaultActiveKey="entries" items={tabItems} />
      </div>
    </main>
  )
}
