import React, { Suspense, lazy } from "react"

import type { CommandPaletteProps } from "@/components/Common/CommandPalette"
import { CommandPaletteHost } from "@/components/Common/CommandPaletteHost"

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
    <CommandPaletteHost commandPaletteProps={commandPaletteProps} />
    <Suspense fallback={null}>
      <PageHelpModal />
    </Suspense>
  </>
)
