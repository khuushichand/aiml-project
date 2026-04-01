import React from "react"
import { createPortal } from "react-dom"

import { useDesktop } from "@/hooks/useMediaQuery"
import { useSelectedAssistant } from "@/hooks/useSelectedAssistant"
import {
  clampPersonaBuddyShellPosition,
  DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS,
  usePersonaBuddyShellStore
} from "@/store/persona-buddy-shell"
import type {
  PersonaBuddyPositionBucket,
  PersonaBuddySummary
} from "@/types/persona-buddy"

import { useBuddyShellRenderContext } from "./BuddyShellRenderContext"
import { BuddyShellDock } from "./BuddyShellDock"

type BuddyShellHostProps = {
  root: "web" | "sidepanel"
}

type DragState = {
  offsetX: number
  offsetY: number
}

const ensurePortalRoot = () => {
  if (typeof document === "undefined") return null
  return document.getElementById("tldw-portal-root") || document.body
}

const isPersonaSelection = (
  value: unknown
): value is {
  kind: "persona"
  id: string
  buddy_summary?: PersonaBuddySummary | null
} => {
  if (!value || typeof value !== "object") {
    return false
  }
  const candidate = value as Record<string, unknown>
  return candidate.kind === "persona" && typeof candidate.id === "string"
}

const resolveActivePersonaSelection = ({
  renderContext,
  selectedAssistant
}: {
  renderContext:
    | {
        surface_active: boolean
        active_persona_id: string | null
      }
    | null
    | undefined
  selectedAssistant: unknown
}) => {
  if (!renderContext?.surface_active) {
    return null
  }

  if (!isPersonaSelection(selectedAssistant)) {
    return null
  }

  if (renderContext.active_persona_id) {
    return selectedAssistant.id === renderContext.active_persona_id
      ? selectedAssistant
      : null
  }

  return selectedAssistant
}

export const BuddyShellHost: React.FC<BuddyShellHostProps> = ({ root }) => {
  const renderContext = useBuddyShellRenderContext()
  const [selectedAssistant] = useSelectedAssistant()
  const isDesktop = useDesktop()
  const dockRef = React.useRef<HTMLDivElement | null>(null)
  const dragStateRef = React.useRef<DragState | null>(null)

  const isSupportedViewport = root === "sidepanel" || isDesktop
  const positionBucket: PersonaBuddyPositionBucket =
    renderContext?.position_bucket ??
    (root === "sidepanel" ? "sidepanel-desktop" : "web-desktop")

  const isOpen = usePersonaBuddyShellStore((state) => state.isOpen)
  const setOpen = usePersonaBuddyShellStore((state) => state.setOpen)
  const resetSessionState = usePersonaBuddyShellStore(
    (state) => state.resetSessionState
  )
  const setPosition = usePersonaBuddyShellStore((state) => state.setPosition)
  const position = usePersonaBuddyShellStore(
    (state) =>
      state.positions[positionBucket] ??
      DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS[positionBucket]
  )

  React.useEffect(() => {
    resetSessionState()
  }, [resetSessionState])

  React.useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (!dragStateRef.current || !dockRef.current) {
        return
      }

      const rect = dockRef.current.getBoundingClientRect()
      const nextPosition = clampPersonaBuddyShellPosition(
        {
          x: event.clientX - dragStateRef.current.offsetX,
          y: event.clientY - dragStateRef.current.offsetY
        },
        positionBucket,
        {
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          shellWidth: rect.width,
          shellHeight: rect.height,
          margin: 16
        }
      )

      setPosition(positionBucket, nextPosition)
    }

    const handlePointerUp = () => {
      dragStateRef.current = null
    }

    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", handlePointerUp)
    return () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", handlePointerUp)
    }
  }, [positionBucket, setPosition])

  const handleDragHandlePointerDown = React.useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0 || !dockRef.current) {
        return
      }

      const rect = dockRef.current.getBoundingClientRect()
      dragStateRef.current = {
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top
      }
      event.preventDefault()
    },
    []
  )

  const resolvedPersona = React.useMemo(
    () =>
      resolveActivePersonaSelection({
        renderContext,
        selectedAssistant
      }),
    [renderContext, selectedAssistant]
  )

  const buddySummary = resolvedPersona?.buddy_summary ?? null
  const portalRoot = ensurePortalRoot()

  if (!isSupportedViewport) {
    return null
  }

  if (!renderContext?.surface_active) {
    return null
  }

  if (!buddySummary?.has_buddy) {
    return null
  }

  if (!portalRoot) {
    return null
  }

  return createPortal(
    <BuddyShellDock
      buddySummary={buddySummary}
      isOpen={isOpen}
      position={position}
      onToggle={() => setOpen(!isOpen)}
      onDragHandlePointerDown={handleDragHandlePointerDown}
      dockRef={dockRef}
    />,
    portalRoot
  )
}

export default BuddyShellHost
