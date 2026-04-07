import React from "react"

import type {
  PersonaBuddyShellPosition
} from "@/store/persona-buddy-shell"
import type { PersonaBuddySummary } from "@/types/persona-buddy"

import { BuddyShellPopover } from "./BuddyShellPopover"

type BuddyShellDockProps = {
  buddySummary: PersonaBuddySummary
  isOpen: boolean
  isDormant?: boolean
  position: PersonaBuddyShellPosition
  onToggle: () => void
  onDragHandlePointerDown: (event: React.PointerEvent<HTMLDivElement>) => void
  dockRef: React.RefObject<HTMLDivElement | null>
}

export const BuddyShellDock: React.FC<BuddyShellDockProps> = ({
  buddySummary,
  isOpen,
  isDormant = false,
  position,
  onToggle,
  onDragHandlePointerDown,
  dockRef
}) => (
  <div
    ref={dockRef}
    data-testid="persona-buddy-dock"
    data-dormant={isDormant ? "true" : "false"}
    className="fixed z-[1100] flex flex-col gap-2"
    style={{
      left: position.x,
      top: position.y
    }}
  >
    <div
      data-testid="persona-buddy-drag-handle"
      onPointerDown={onDragHandlePointerDown}
      className="cursor-grab rounded-full border border-border bg-bg/95 px-3 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-text-muted shadow-sm backdrop-blur active:cursor-grabbing"
    >
      Drag Buddy
    </div>

    <button
      type="button"
      onClick={onToggle}
      disabled={isDormant}
      aria-expanded={isOpen}
      aria-label={`Toggle buddy for ${buddySummary.persona_name}`}
      className="flex min-w-[160px] items-center justify-between gap-3 rounded-2xl border border-border bg-bg/95 px-4 py-3 text-left shadow-xl backdrop-blur"
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-text">
          {buddySummary.persona_name}
        </div>
        <div className="truncate text-xs text-text-muted">
          {buddySummary.visual?.species_id ?? "buddy unavailable"}
        </div>
      </div>
      <div className="text-lg leading-none text-text">
        {isDormant ? "·" : isOpen ? "−" : "+"}
      </div>
    </button>

    {isOpen && !isDormant ? (
      <BuddyShellPopover buddySummary={buddySummary} />
    ) : null}
  </div>
)

export default BuddyShellDock
