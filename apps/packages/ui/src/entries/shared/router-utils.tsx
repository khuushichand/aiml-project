import React from "react"
import { HashRouter, MemoryRouter } from "react-router-dom"

const routerFutureConfig = {
  v7_startTransition: true,
  v7_relativeSplatPath: true
}

export const HashRouterWithFuture: React.FC<{ children: React.ReactNode }> = ({
  children
}) => <HashRouter future={routerFutureConfig}>{children}</HashRouter>

export const MemoryRouterWithFuture: React.FC<{
  children: React.ReactNode
}> = ({ children }) => (
  <MemoryRouter future={routerFutureConfig}>{children}</MemoryRouter>
)

export const resolveRouter = (mode: "hash" | "memory") =>
  mode === "hash" ? HashRouterWithFuture : MemoryRouterWithFuture

const resolveMemoryInitialEntry = () => {
  if (typeof window === "undefined") {
    return "/"
  }
  const rawHash = window.location.hash || ""
  const trimmed = rawHash.startsWith("#") ? rawHash.slice(1) : rawHash
  if (!trimmed || trimmed === "/") {
    return "/"
  }
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

export const SidepanelMemoryRouter: React.FC<{
  children: React.ReactNode
}> = ({ children }) => {
  const initialEntries = React.useMemo(() => [resolveMemoryInitialEntry()], [])
  return (
    <MemoryRouter initialEntries={initialEntries} future={routerFutureConfig}>
      {children}
    </MemoryRouter>
  )
}
