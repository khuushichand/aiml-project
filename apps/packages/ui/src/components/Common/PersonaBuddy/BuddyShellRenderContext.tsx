import React from "react"

import { usePersonaBuddyShellStore } from "@/store/persona-buddy-shell"
import type { PersonaBuddyRenderContext } from "@/types/persona-buddy"

type BuddyShellRenderContextValue = {
  renderContext: PersonaBuddyRenderContext | null
  setRenderContext: (value: PersonaBuddyRenderContext | null) => void
  clearRenderContext: () => void
}

const noop = () => {}

const BuddyShellRenderContext = React.createContext<BuddyShellRenderContextValue>(
  {
    renderContext: null,
    setRenderContext: noop,
    clearRenderContext: noop
  }
)

const areRenderContextsEqual = (
  left: PersonaBuddyRenderContext | null,
  right: PersonaBuddyRenderContext | null
) =>
  left === right ||
  (left !== null &&
    right !== null &&
    left.surface_id === right.surface_id &&
    left.surface_active === right.surface_active &&
    left.active_persona_id === right.active_persona_id &&
    left.position_bucket === right.position_bucket &&
    left.persona_source === right.persona_source)

type BuddyShellRenderContextProviderProps = {
  children: React.ReactNode
  initialContext?: PersonaBuddyRenderContext | null
}

export const BuddyShellRenderContextProvider: React.FC<
  BuddyShellRenderContextProviderProps
> = ({ children, initialContext = null }) => {
  const [renderContext, setRenderContextState] =
    React.useState<PersonaBuddyRenderContext | null>(initialContext)

  React.useEffect(() => {
    usePersonaBuddyShellStore.getState().resetSessionState()
  }, [])

  const setRenderContext = React.useCallback(
    (value: PersonaBuddyRenderContext | null) => {
      setRenderContextState((current) =>
        areRenderContextsEqual(current, value) ? current : value
      )
    },
    []
  )

  const clearRenderContext = React.useCallback(() => {
    setRenderContextState(null)
  }, [])

  const value = React.useMemo(
    () => ({
      renderContext,
      setRenderContext,
      clearRenderContext
    }),
    [clearRenderContext, renderContext, setRenderContext]
  )

  return (
    <BuddyShellRenderContext.Provider value={value}>
      {children}
    </BuddyShellRenderContext.Provider>
  )
}

export const useBuddyShellRenderContext = (): PersonaBuddyRenderContext | null =>
  React.useContext(BuddyShellRenderContext).renderContext

export const useBuddyShellRenderContextController = () =>
  React.useContext(BuddyShellRenderContext)

export const useSetBuddyShellRenderContext = () =>
  React.useContext(BuddyShellRenderContext).setRenderContext

export const usePublishBuddyShellRenderContext = (
  value: PersonaBuddyRenderContext | null
) => {
  const setRenderContext = useSetBuddyShellRenderContext()

  React.useEffect(() => {
    setRenderContext(value)
    return () => {
      setRenderContext(null)
    }
  }, [setRenderContext, value])
}
