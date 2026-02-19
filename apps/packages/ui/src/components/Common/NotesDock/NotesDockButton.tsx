import React from "react"
import { Tooltip, type TooltipProps } from "antd"
import { StickyNote } from "lucide-react"
import { useNotesDockStore } from "@/store/notes-dock"
import { classNames } from "@/libs/class-name"
import { useMobile } from "@/hooks/useMediaQuery"

type NotesDockButtonProps = {
  className?: string
  tooltipPlacement?: TooltipProps["placement"]
  ariaLabel?: string
  appearance?: "primary" | "ghost"
}

export const NotesDockButton: React.FC<NotesDockButtonProps> = ({
  className,
  tooltipPlacement = "right",
  ariaLabel = "Open Notes Dock",
  appearance = "ghost"
}) => {
  const shortcutHint = "Ctrl/Cmd+Shift+N"
  const desktopHint = "Desktop only"
  const isMobile = useMobile()
  const { isOpen, setOpen } = useNotesDockStore((state) => ({
    isOpen: state.isOpen,
    setOpen: state.setOpen
  }))

  if (isMobile) return null

  const handleClick = () => {
    if (isOpen) {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("tldw:notes-dock-request-close"))
      }
      return
    }
    setOpen(true)
  }

  const buttonClassName =
    appearance === "ghost"
      ? classNames(
          "flex items-center justify-center",
          "p-2 rounded-lg",
          isOpen ? "bg-surface text-text" : "text-text-muted",
          "hover:bg-surface hover:text-text",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        )
      : classNames(
          "flex items-center justify-center",
          "w-9 h-9 rounded-full",
          "bg-[color:var(--color-primary)] hover:bg-[color:var(--color-primary-strong)]",
          "text-white shadow-sm",
          "transition-colors duration-150",
          "focus:outline-none focus:ring-2 focus:ring-[color:var(--color-focus)] focus:ring-offset-2",
          "focus:ring-offset-[color:var(--color-surface)]"
        )

  return (
    <Tooltip title={`${ariaLabel} (${desktopHint} · ${shortcutHint})`} placement={tooltipPlacement}>
      <button
        type="button"
        onClick={handleClick}
        aria-label={ariaLabel}
        aria-keyshortcuts="Control+Shift+N Meta+Shift+N"
        aria-pressed={isOpen}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        className={classNames(buttonClassName, className)}
      >
        <StickyNote className={appearance === "ghost" ? "size-4" : "size-5"} />
      </button>
    </Tooltip>
  )
}

export default NotesDockButton
