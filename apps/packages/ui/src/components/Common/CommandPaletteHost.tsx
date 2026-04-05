import React, { Suspense, lazy, useCallback, useEffect, useState } from "react"
import { useLocation } from "react-router-dom"

import { useShortcut } from "@/hooks/useKeyboardShortcuts"
import { WORKSPACE_PLAYGROUND_PATH } from "@/routes/route-paths"

import type { CommandPaletteProps } from "./CommandPalette"

const CommandPalette = lazy(() =>
  import("./CommandPalette").then((m) => ({ default: m.CommandPalette }))
)

type CommandPaletteHostProps = {
  commandPaletteProps?: CommandPaletteProps
}

export const CommandPaletteHost = ({
  commandPaletteProps
}: CommandPaletteHostProps) => {
  const location = useLocation()
  const shortcutEnabled = location.pathname !== WORKSPACE_PLAYGROUND_PATH
  const [hasMountedPalette, setHasMountedPalette] = useState(false)
  const [openSignal, setOpenSignal] = useState(0)

  const openPalette = useCallback(() => {
    setHasMountedPalette(true)
    setOpenSignal((current) => current + 1)
  }, [])

  useShortcut(
    {
      key: "k",
      modifiers: ["meta"],
      action: openPalette,
      description: "Open command palette",
      enabled: shortcutEnabled,
      allowInInput: true
    },
    [openPalette, shortcutEnabled]
  )

  useShortcut(
    {
      key: "k",
      modifiers: ["ctrl"],
      action: openPalette,
      description: "Open command palette",
      enabled: shortcutEnabled,
      allowInInput: true
    },
    [openPalette, shortcutEnabled]
  )

  useEffect(() => {
    window.addEventListener("tldw:open-command-palette", openPalette)
    return () => {
      window.removeEventListener("tldw:open-command-palette", openPalette)
    }
  }, [openPalette])

  if (!hasMountedPalette) {
    return null
  }

  return (
    <Suspense fallback={null}>
      <CommandPalette
        {...commandPaletteProps}
        openSignal={openSignal}
        registerGlobalOpenShortcut={false}
        listenForOpenEvents={false}
      />
    </Suspense>
  )
}
