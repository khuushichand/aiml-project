import React from "react"
import { Layers, Star, Clock, TrendingUp, Tag as TagIcon } from "lucide-react"
import type { PromptSavedView } from "./prompt-workspace-types"

type SmartCollectionItem = {
  id: PromptSavedView
  label: string
  icon: React.ReactNode
}

const COLLECTIONS: SmartCollectionItem[] = [
  { id: "all", label: "All Prompts", icon: <Layers className="size-4" /> },
  { id: "favorites", label: "Favorites", icon: <Star className="size-4" /> },
  { id: "recent", label: "Recently Used", icon: <Clock className="size-4" /> },
  { id: "most_used", label: "Most Used", icon: <TrendingUp className="size-4" /> },
  { id: "untagged", label: "Untagged", icon: <TagIcon className="size-4" /> },
]

type Props = {
  activeView: PromptSavedView
  onViewChange: (view: PromptSavedView) => void
  counts: Partial<Record<PromptSavedView, number>>
}

export const SmartCollections: React.FC<Props> = ({
  activeView,
  onViewChange,
  counts,
}) => {
  return (
    <div className="space-y-0.5" data-testid="smart-collections">
      {COLLECTIONS.map((c) => (
        <button
          key={c.id}
          type="button"
          data-testid={`smart-collection-${c.id}`}
          onClick={() => onViewChange(c.id)}
          className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
            activeView === c.id
              ? "bg-primary/10 text-primary font-medium"
              : "text-text-muted hover:bg-surface2 hover:text-text"
          }`}
        >
          {c.icon}
          <span className="flex-1 text-left">{c.label}</span>
          {counts[c.id] != null && (
            <span className="text-xs text-text-muted tabular-nums">
              {counts[c.id]}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
