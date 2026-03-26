import React from "react"
import { Layers, Globe, ChevronDown, Settings } from "lucide-react"
import { cn } from "@/libs/utils"
import type { RagPresetName, RagSource } from "@/services/rag/unified-rag"

type CompactToolbarProps = {
  sources: RagSource[]
  preset: RagPresetName
  webEnabled: boolean
  onToggleWeb: () => void
  onOpenSourceSelector: () => void
  onOpenSettings: () => void
  contextChangedSinceLastRun: boolean
  className?: string
}

const ALL_SOURCES_THRESHOLD = 5

const SOURCE_LABELS: Record<RagSource, string> = {
  media_db: "Docs & Media",
  notes: "Notes",
  characters: "Characters",
  chats: "Chats",
  kanban: "Kanban",
}

function summarizeSources(sources: RagSource[]): string {
  if (!Array.isArray(sources) || sources.length === 0) return "None"
  if (sources.length === 1) return SOURCE_LABELS[sources[0]] || sources[0]
  if (sources.length >= ALL_SOURCES_THRESHOLD) return "All sources"
  return `${sources.length} selected`
}

const PRESET_LABELS: Record<string, string> = {
  fast: "Fast",
  balanced: "Balanced",
  thorough: "Deep",
  custom: "Custom",
}

export function CompactToolbar({
  sources,
  preset,
  webEnabled,
  onToggleWeb,
  onOpenSourceSelector,
  onOpenSettings,
  contextChangedSinceLastRun,
  className,
}: CompactToolbarProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {/* Sources pill */}
      <button
        type="button"
        onClick={onOpenSourceSelector}
        className="inline-flex h-7 items-center gap-1 rounded-full border border-border bg-surface px-2.5 text-[11px] font-medium text-text-muted hover:bg-surface2 hover:text-text transition-colors"
      >
        <Layers className="h-3.5 w-3.5" />
        Sources: {summarizeSources(sources)}
        <ChevronDown className="h-3 w-3" />
      </button>

      {/* Preset pill */}
      <button
        type="button"
        onClick={onOpenSettings}
        className="inline-flex h-7 items-center gap-1 rounded-full border border-border bg-surface px-2.5 text-[11px] font-medium text-text-muted hover:bg-surface2 hover:text-text transition-colors"
        title={`Search preset: ${PRESET_LABELS[preset] ?? preset}`}
      >
        {PRESET_LABELS[preset] ?? preset}
        <ChevronDown className="h-3 w-3" />
      </button>

      {/* Web toggle pill */}
      <button
        type="button"
        onClick={onToggleWeb}
        className={cn(
          "inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[11px] font-medium transition-colors",
          webEnabled
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-border bg-surface text-text-muted hover:bg-surface2 hover:text-text"
        )}
        aria-pressed={webEnabled}
        aria-label={`Web fallback is currently ${webEnabled ? "enabled" : "disabled"}. Click to toggle.`}
        title="Falls back to web search when local source relevance is below threshold."
      >
        <Globe className={cn("h-3.5 w-3.5", webEnabled ? "fill-current" : "")} />
        Web
      </button>

      {/* Settings gear */}
      <button
        type="button"
        onClick={onOpenSettings}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border text-text-muted hover:bg-surface2 hover:text-text transition-colors"
        aria-label="Open settings"
        title="Open search settings"
      >
        <Settings className="h-3.5 w-3.5" />
      </button>

      {contextChangedSinceLastRun && (
        <span className="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
          Scope changed
        </span>
      )}
    </div>
  )
}
