import React, { useEffect, useMemo, useRef, useState } from "react"
import type { RagPresetName } from "@/services/rag/unified-rag"
import { cn } from "@/lib/utils"
import { ChevronDown, Layers, Settings, Globe, Check, CircleHelp } from "lucide-react"

type KnowledgeContextBarProps = {
  preset: RagPresetName
  onPresetChange: (preset: RagPresetName) => void
  sources: string[]
  onSourcesChange: (sources: string[]) => void
  webEnabled: boolean
  onToggleWeb: () => void
  contextChangedSinceLastRun: boolean
  onOpenSettings: () => void
}

const PRESET_OPTIONS: Array<{
  value: Exclude<RagPresetName, "custom">
  label: string
}> = [
  { value: "fast", label: "Fast" },
  { value: "balanced", label: "Balanced" },
  { value: "thorough", label: "Deep" },
]

const PRESET_DESCRIPTIONS: Record<Exclude<RagPresetName, "custom">, string> = {
  fast: "Fast: Quick lookup with fewer retrieval steps.",
  balanced: "Balanced: Good quality and speed for most queries.",
  thorough: "Deep: Exhaustive retrieval and verification, slower runtime.",
}

const SOURCE_LABELS: Record<string, string> = {
  media_db: "Docs & Media",
  notes: "Notes",
  characters: "Characters",
  chats: "Chats",
  kanban: "Kanban",
}

const SOURCE_OPTIONS = [
  { key: "media_db", label: "Docs & Media" },
  { key: "notes", label: "Notes" },
  { key: "characters", label: "Characters" },
  { key: "chats", label: "Chats" },
  { key: "kanban", label: "Kanban" },
] as const

function summarizeSources(sources: string[]): string {
  if (!Array.isArray(sources) || sources.length === 0) {
    return "None selected"
  }
  if (sources.length === 1) {
    return SOURCE_LABELS[sources[0]] || sources[0]
  }
  if (sources.length >= 5) {
    return "All sources"
  }
  return `${sources.length} selected`
}

export function KnowledgeContextBar({
  preset,
  onPresetChange,
  sources,
  onSourcesChange,
  webEnabled,
  onToggleWeb,
  contextChangedSinceLastRun,
  onOpenSettings,
}: KnowledgeContextBarProps) {
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const normalizedSources = useMemo(
    () =>
      Array.from(
        new Set(
          sources
            .filter((value): value is string => typeof value === "string")
            .map((value) => value.trim())
            .filter(Boolean)
        )
      ),
    [sources]
  )
  const presetDescription =
    preset === "custom"
      ? "Custom: Using your manually configured retrieval and generation settings."
      : PRESET_DESCRIPTIONS[preset]

  useEffect(() => {
    if (!sourceMenuOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (!menuRef.current) return
      if (menuRef.current.contains(event.target as Node)) return
      setSourceMenuOpen(false)
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSourceMenuOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    document.addEventListener("keydown", handleEscape)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
      document.removeEventListener("keydown", handleEscape)
    }
  }, [sourceMenuOpen])

  const toggleSource = (sourceKey: string) => {
    const exists = normalizedSources.includes(sourceKey)
    const nextSources = exists
      ? normalizedSources.filter((value) => value !== sourceKey)
      : [...normalizedSources, sourceKey]
    onSourcesChange(nextSources)
  }

  const selectAllSources = () => {
    onSourcesChange(SOURCE_OPTIONS.map((option) => option.key))
  }

  const clearSources = () => {
    onSourcesChange([])
  }

  return (
    <div className="rounded-xl border border-border bg-surface/90 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative" ref={menuRef}>
          <button
            id="knowledge-source-selector-toggle"
            type="button"
            onClick={() => setSourceMenuOpen((previous) => !previous)}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
            aria-expanded={sourceMenuOpen}
            aria-controls={sourceMenuOpen ? "knowledge-source-menu" : undefined}
          >
            <Layers className="h-3.5 w-3.5 text-text-muted" />
            Sources: {summarizeSources(normalizedSources)}
            <ChevronDown className="h-3.5 w-3.5 text-text-muted" />
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            className="ml-1 inline-flex rounded-md border border-border bg-surface p-1.5 text-text-subtle hover:bg-hover hover:text-text transition-colors"
            aria-label="Explain source categories"
            title="Docs & Media (files/transcripts), Notes, Characters, Chats, and Kanban items can all be included in retrieval scope."
          >
            <CircleHelp className="h-3.5 w-3.5" />
          </button>
          {sourceMenuOpen ? (
            <div
              id="knowledge-source-menu"
              className="absolute left-0 z-30 mt-2 w-64 rounded-lg border border-border bg-surface p-2 shadow-lg"
              role="menu"
              aria-label="Source selector"
            >
              <div className="mb-2 flex items-center justify-between px-1">
                <span className="text-xs font-semibold text-text-muted">Search Sources</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="rounded px-1.5 py-0.5 text-[11px] text-text-muted hover:bg-hover hover:text-text transition-colors"
                    onClick={selectAllSources}
                  >
                    All
                  </button>
                  <button
                    type="button"
                    className="rounded px-1.5 py-0.5 text-[11px] text-text-muted hover:bg-hover hover:text-text transition-colors"
                    onClick={clearSources}
                  >
                    None
                  </button>
                </div>
              </div>
              <div className="space-y-1">
                {SOURCE_OPTIONS.map((option) => {
                  const selected = normalizedSources.includes(option.key)
                  return (
                    <button
                      key={option.key}
                      type="button"
                      role="menuitemcheckbox"
                      aria-checked={selected}
                      onClick={() => toggleSource(option.key)}
                      className={cn(
                        "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors",
                        selected ? "bg-primary/10 text-primary" : "hover:bg-hover text-text"
                      )}
                    >
                      <span>{option.label}</span>
                      <span className="h-4 w-4">
                        {selected ? <Check className="h-4 w-4" /> : null}
                      </span>
                    </button>
                  )
                })}
              </div>
              {normalizedSources.length === 0 ? (
                <p className="mt-2 rounded-md border border-warn/30 bg-warn/10 px-2 py-1.5 text-[11px] text-warn">
                  No sources selected. Searches may return empty results.
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div
          role="group"
          aria-label="Preset selection"
          aria-describedby="knowledge-preset-description"
          className="inline-flex rounded-md border border-border bg-bg-subtle p-0.5"
        >
          {PRESET_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onPresetChange(option.value)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                preset === option.value
                  ? "bg-primary text-white"
                  : "text-text-subtle hover:text-text hover:bg-hover"
              )}
              aria-pressed={preset === option.value}
            >
              {option.label}
            </button>
          ))}
          {preset === "custom" ? (
            <button
              type="button"
              onClick={onOpenSettings}
              className="rounded px-2.5 py-1 text-xs font-medium text-primary hover:bg-surface transition-colors"
              aria-label="Custom preset active. Open settings."
            >
              Custom
            </button>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onToggleWeb}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              webEnabled
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border bg-surface text-text-subtle hover:bg-hover hover:text-text"
            )}
            aria-pressed={webEnabled}
          >
          <Globe className="h-3.5 w-3.5" />
          Web: {webEnabled ? "On" : "Off"}
        </button>

        <button
          type="button"
          onClick={onOpenSettings}
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-subtle hover:bg-hover hover:text-text transition-colors"
        >
          <Settings className="h-3.5 w-3.5" />
          Settings
        </button>

        {contextChangedSinceLastRun ? (
          <span className="inline-flex items-center rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
            Scope changed
          </span>
        ) : null}
      </div>
      <p id="knowledge-preset-description" className="mt-2 text-xs text-text-muted">
        {presetDescription}
      </p>
    </div>
  )
}
