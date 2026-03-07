import React, { useEffect } from "react"
import { X, Lightbulb } from "lucide-react"
import type { HintId } from "./useContextualHints"

type ContextualHintProps = {
  id: HintId
  message: string
  visible: boolean
  onDismiss: (id: HintId) => void
  onShown?: (id: HintId) => void
}

export const ContextualHint: React.FC<ContextualHintProps> = ({
  id,
  message,
  visible,
  onDismiss,
  onShown,
}) => {
  useEffect(() => {
    if (visible && onShown) {
      onShown(id)
    }
  }, [visible, id, onShown])

  if (!visible) return null

  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-text"
      data-testid={`hint-${id}`}
    >
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
      <span className="flex-1">{message}</span>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="shrink-0 rounded p-0.5 text-text-muted hover:bg-surface2 hover:text-text"
        aria-label="Dismiss hint"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}
