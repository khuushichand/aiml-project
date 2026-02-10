import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/hooks/useTheme", () => ({
  useTheme: () => ({ antdTheme: {} })
}))

vi.mock("@/components/Common/PageAssistProvider", () => ({
  PageAssistProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  )
}))

vi.mock("@/context/FontSizeProvider", () => ({
  FontSizeProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  )
}))

vi.mock("@/components/Common/LocaleJsonDiagnostics", () => ({
  LocaleJsonDiagnostics: () => null
}))

vi.mock("@/components/Common/SplashScreen", () => ({
  SplashOverlay: ({ message }: { message: string }) => (
    <div data-testid="splash-overlay">{message}</div>
  )
}))

import { SPLASH_TRIGGER_EVENT } from "@/services/splash-events"
import { AppShell } from "../AppShell"

const Router: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <>{children}</>
)

describe("AppShell splash integration", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("shows splash overlay when splash trigger event fires", async () => {
    render(
      <AppShell router={Router} direction="ltr" emptyDescription="No data">
        <div>App content</div>
      </AppShell>
    )

    expect(screen.queryByTestId("splash-overlay")).not.toBeInTheDocument()

    window.dispatchEvent(new CustomEvent(SPLASH_TRIGGER_EVENT))

    await waitFor(() => {
      expect(screen.getByTestId("splash-overlay")).toBeInTheDocument()
    })
  })

  it("shows splash on forced login trigger even when splash preference is disabled", async () => {
    localStorage.setItem("tldw_splash_disabled", "true")
    render(
      <AppShell router={Router} direction="ltr" emptyDescription="No data">
        <div>App content</div>
      </AppShell>
    )

    expect(screen.queryByTestId("splash-overlay")).not.toBeInTheDocument()

    window.dispatchEvent(
      new CustomEvent(SPLASH_TRIGGER_EVENT, { detail: { force: true } })
    )

    await waitFor(() => {
      expect(screen.getByTestId("splash-overlay")).toBeInTheDocument()
    })
  })
})
