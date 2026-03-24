import React, { Suspense, lazy } from "react"
import { CommandPalette, type CommandPaletteProps } from "@/components/Common/CommandPalette"

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
    <CommandPalette {...commandPaletteProps} />
    <Suspense fallback={null}>
      <PageHelpModal />
    </Suspense>
  </>
)
