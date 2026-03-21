import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { EmptySidePanel } from "../empty"

const connectionStateMock = vi.hoisted(() => ({
  state: {
    phase: "unconfigured",
    isConnected: false,
    serverUrl: null
  },
  uxState: {
    uxState: "unconfigured",
    mode: "normal",
    configStep: "url",
    hasCompletedFirstRun: false
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      getURL: vi.fn((path: string) => `chrome-extension://test${path}`),
      sendMessage: vi.fn()
    },
    tabs: {
      create: vi.fn()
    }
  }
}))

vi.mock("antd", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children?: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionState: () => connectionStateMock.state,
  useConnectionUxState: () => connectionStateMock.uxState
}))

describe("EmptySidePanel", () => {
  beforeEach(() => {
    connectionStateMock.state = {
      phase: "unconfigured",
      isConnected: false,
      serverUrl: null
    }
    connectionStateMock.uxState = {
      uxState: "unconfigured",
      mode: "normal",
      configStep: "url",
      hasCompletedFirstRun: false
    }
  })

  it("frames setup around Companion Home instead of a chat-only launch", () => {
    render(<EmptySidePanel />)

    expect(screen.getByText("Finish setup to open Companion Home")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Before you can use Companion Home here, finish the short setup flow in Options to connect tldw Assistant to your tldw server or choose demo mode."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Finish setup" })).toBeInTheDocument()
  })
})
