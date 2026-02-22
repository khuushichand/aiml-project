import React, { Suspense, lazy } from "react"
import type { CommandPaletteProps } from "@/components/Common/CommandPalette"

const CommandPalette = lazy(() =>
  import("@/components/Common/CommandPalette").then((m) => ({
    default: m.CommandPalette
  }))
)

const PageHelpModal = lazy(() =>
  import("@/components/Common/PageHelpModal").then((m) => ({
    default: m.PageHelpModal
  }))
)

type EventOnlyHostsProps = {
  commandPaletteProps?: CommandPaletteProps
}

export const EventOnlyHosts = ({
  commandPaletteProps
}: EventOnlyHostsProps) => (
  <>
    <Suspense fallback={null}>
      <CommandPalette {...commandPaletteProps} />
    </Suspense>
    <Suspense fallback={null}>
      <PageHelpModal />
    </Suspense>
  </>
)
