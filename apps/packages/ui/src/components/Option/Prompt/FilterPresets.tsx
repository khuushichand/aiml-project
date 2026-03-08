import React, { useState } from "react"
import { Bookmark, X, Plus } from "lucide-react"
import type { FilterPreset } from "./useFilterPresets"

type Props = {
  presets: FilterPreset[]
  onLoad: (preset: FilterPreset) => void
  onSave: (name: string) => void
  onDelete: (id: string) => void
}

export const FilterPresets: React.FC<Props> = ({
  presets,
  onLoad,
  onSave,
  onDelete,
}) => {
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState("")

  const handleSave = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    onSave(trimmed)
    setName("")
    setSaving(false)
  }

  return (
    <div data-testid="filter-presets">
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
        Filter Presets
      </h4>
      <div className="space-y-0.5">
        {presets.map((p) => (
          <div
            key={p.id}
            className="group flex items-center gap-1 rounded px-2 py-1 hover:bg-surface2"
          >
            <button
              type="button"
              onClick={() => onLoad(p)}
              className="flex flex-1 items-center gap-1.5 text-sm text-text-muted hover:text-text truncate"
              data-testid={`filter-preset-${p.id}`}
            >
              <Bookmark className="size-3.5 shrink-0" />
              <span className="truncate">{p.name}</span>
            </button>
            <button
              type="button"
              onClick={() => onDelete(p.id)}
              className="hidden shrink-0 rounded p-0.5 text-text-muted hover:text-danger group-hover:block"
              aria-label={`Delete preset ${p.name}`}
              data-testid={`filter-preset-delete-${p.id}`}
            >
              <X className="size-3" />
            </button>
          </div>
        ))}

        {saving ? (
          <div className="flex items-center gap-1 px-2 py-1">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave()
                if (e.key === "Escape") setSaving(false)
              }}
              placeholder="Preset name..."
              className="flex-1 rounded border border-border bg-surface px-1.5 py-0.5 text-sm outline-none focus:border-primary"
              autoFocus
              data-testid="filter-preset-name-input"
            />
            <button
              type="button"
              onClick={handleSave}
              disabled={!name.trim()}
              className="rounded bg-primary px-2 py-0.5 text-xs text-white disabled:opacity-50"
              data-testid="filter-preset-save-confirm"
            >
              Save
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setSaving(true)}
            className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm text-text-muted hover:bg-surface2 hover:text-text"
            data-testid="filter-preset-save-btn"
          >
            <Plus className="size-3.5" />
            <span>Save current filters</span>
          </button>
        )}
      </div>
    </div>
  )
}
