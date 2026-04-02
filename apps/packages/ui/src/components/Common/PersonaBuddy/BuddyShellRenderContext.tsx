import React from "react"

import type { PersonaBuddyRenderContext } from "@/types/persona-buddy"

type BuddyShellRenderContextValue = {
  context: PersonaBuddyRenderContext
  setContext: React.Dispatch<
    React.SetStateAction<PersonaBuddyRenderContext>
  >
}

const DEFAULT_CONTEXT: PersonaBuddyRenderContext = {
  surface_id: "",
  surface_active: false,
  active_persona_id: null,
  position_bucket: "web-desktop",
  persona_source: null
}

const noop = () => {}

const BuddyShellRenderContext = React.createContext<
  BuddyShellRenderContextValue | null
>(null)

type BuddyShellRenderContextProviderProps = {
  children: React.ReactNode
  value?: Partial<PersonaBuddyRenderContext>
}

const normalizeContext = (
  value?: Partial<PersonaBuddyRenderContext>
): PersonaBuddyRenderContext => ({
  ...DEFAULT_CONTEXT,
  ...value,
  position_bucket: value?.position_bucket ?? DEFAULT_CONTEXT.position_bucket
})

export const BuddyShellRenderContextProvider: React.FC<
  BuddyShellRenderContextProviderProps
> = ({ children, value }) => {
  const [context, setContext] = React.useState<PersonaBuddyRenderContext>(() =>
    normalizeContext(value)
  )

  React.useEffect(() => {
    if (value) {
      setContext((current) => ({
        ...current,
        ...value,
        position_bucket:
          value.position_bucket ?? current.position_bucket ?? "web-desktop"
      }))
    }
  }, [value])

  const memoized = React.useMemo(
    () => ({
      context,
      setContext
    }),
    [context]
  )

  return (
    <BuddyShellRenderContext.Provider value={memoized}>
      {children}
    </BuddyShellRenderContext.Provider>
  )
}

export const useBuddyShellRenderContext = () => {
  const value = React.useContext(BuddyShellRenderContext)
  return value?.context ?? DEFAULT_CONTEXT
}

export const useBuddyShellRenderContextSetter = () => {
  const value = React.useContext(BuddyShellRenderContext)
  return value?.setContext ?? noop
}

export const useBuddyShellRenderContextValue = () =>
  React.useContext(BuddyShellRenderContext)

export default BuddyShellRenderContext
