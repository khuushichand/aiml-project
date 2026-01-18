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
  const resolvedDemoEnabled = demoEnabled ?? false
  const handleSetDemoEnabled = React.useCallback(
    (enabled: boolean) => {
      setDemoEnabled(enabled)
    },
    [setDemoEnabled]
  )

  const value = React.useMemo(
    () => ({
      demoEnabled: resolvedDemoEnabled,
      setDemoEnabled: handleSetDemoEnabled
    }),
    [resolvedDemoEnabled, handleSetDemoEnabled]
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
