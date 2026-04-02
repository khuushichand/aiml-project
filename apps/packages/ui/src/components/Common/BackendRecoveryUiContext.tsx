import React from "react"

type BackendRecoveryUiContextValue = {
  routeRecoveryEnabled: boolean
  fatalBackendRecoveryActive: boolean
  setFatalBackendRecoveryActive: (active: boolean) => void
}

const noop = () => {}

const BackendRecoveryUiContext = React.createContext<BackendRecoveryUiContextValue>({
  routeRecoveryEnabled: false,
  fatalBackendRecoveryActive: false,
  setFatalBackendRecoveryActive: noop
})

type BackendRecoveryUiProviderProps = {
  children: React.ReactNode
  routeRecoveryEnabled?: boolean
}

export const BackendRecoveryUiProvider: React.FC<
  BackendRecoveryUiProviderProps
> = ({ children, routeRecoveryEnabled = false }) => {
  const [fatalBackendRecoveryActive, setFatalBackendRecoveryActive] =
    React.useState(false)

  const value = React.useMemo(
    () => ({
      routeRecoveryEnabled,
      fatalBackendRecoveryActive,
      setFatalBackendRecoveryActive
    }),
    [fatalBackendRecoveryActive, routeRecoveryEnabled]
  )

  return (
    <BackendRecoveryUiContext.Provider value={value}>
      {children}
    </BackendRecoveryUiContext.Provider>
  )
}

export const useBackendRecoveryUi = () =>
  React.useContext(BackendRecoveryUiContext)

export default BackendRecoveryUiContext
