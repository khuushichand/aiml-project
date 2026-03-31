import React from "react"
import { useStorage } from "@plasmohq/storage/hook"

type DemoModeContextValue = {
  demoEnabled: boolean
  setDemoEnabled: (enabled: boolean) => void
}

const DemoModeContext = React.createContext<DemoModeContextValue | undefined>(
  undefined
)

export const DemoModeProvider: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const [demoEnabled, setDemoEnabled] = useStorage<boolean>(
    "demoModeEnabled",
    false
  )

  const value = React.useMemo(
    () => ({
      demoEnabled,
      setDemoEnabled
    }),
    [demoEnabled, setDemoEnabled]
  )

  return (
    <DemoModeContext.Provider value={value}>
      {children}
    </DemoModeContext.Provider>
  )
}

export const useDemoMode = (): DemoModeContextValue => {
  const ctx = React.useContext(DemoModeContext)
  if (!ctx) {
    throw new Error("useDemoMode must be used within DemoModeProvider")
  }
  return ctx
}

const DEMO_MODE_FALLBACK: DemoModeContextValue = {
  demoEnabled: false,
  setDemoEnabled: () => {}
}

/**
 * Safe variant of useDemoMode that returns a no-op fallback when
 * DemoModeProvider is not in the component tree (e.g., sidepanel surface).
 */
export const useSafeDemoMode = (): DemoModeContextValue => {
  const ctx = React.useContext(DemoModeContext)
  return ctx ?? DEMO_MODE_FALLBACK
}
