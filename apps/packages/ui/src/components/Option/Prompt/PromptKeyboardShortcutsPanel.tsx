import React from "react"
import { X } from "lucide-react"

type ShortcutEntry = {
  keys: string[]
  description: string
}

const SHORTCUTS: ShortcutEntry[] = [
  { keys: ["Enter"], description: "Open inspector" },
  { keys: ["E"], description: "Edit prompt" },
  { keys: ["Space"], description: "Toggle selection" },
  { keys: ["⌘", "K"], description: "Command palette" },
  { keys: ["⌘", "N"], description: "New prompt" },
  { keys: ["/"], description: "Focus search" },
  { keys: ["?"], description: "Show shortcuts" },
  { keys: ["Escape"], description: "Close editor / inspector" },
  { keys: ["⌘", "S"], description: "Save (in editor)" },
]

type Props = {
  open: boolean
  onClose: () => void
}

export const PromptKeyboardShortcutsPanel: React.FC<Props> = ({
  open,
  onClose,
}) => {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-border bg-surface p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
        data-testid="prompt-shortcuts-panel"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text">
            Keyboard Shortcuts
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-text-muted hover:bg-surface2 hover:text-text"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div
              key={s.description}
              className="flex items-center justify-between py-1"
            >
              <span className="text-sm text-text-muted">{s.description}</span>
              <div className="flex items-center gap-1">
                {s.keys.map((key) => (
                  <kbd
                    key={key}
                    className="rounded border border-border bg-surface2 px-1.5 py-0.5 text-xs font-medium text-text"
                  >
                    {key}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
