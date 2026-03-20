import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { GuardianSettings } from "../GuardianSettings"

const {
  useQueryMock,
  useMutationMock,
  useQueryClientMock,
  serverCapabilitiesState,
  connectionState
} = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useMutationMock: vi.fn(),
  useQueryClientMock: vi.fn(),
  serverCapabilitiesState: {
    capabilities: {
      hasGuardian: true,
      hasSelfMonitoring: true
    },
    loading: false
  } as {
    capabilities: { hasGuardian: boolean; hasSelfMonitoring: boolean } | null
    loading: boolean
  },
  connectionState: {
    online: true,
    uxState: "connected_ok" as
      | "connected_ok"
      | "testing"
      | "configuring_url"
      | "configuring_auth"
      | "error_auth"
      | "error_unreachable"
      | "unconfigured",
    navigate: vi.fn()
  }
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useMutation: useMutationMock,
  useQueryClient: useQueryClientMock
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  )
  return {
    ...actual,
    useNavigate: () => connectionState.navigate
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => connectionState.online
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionUxState: () => ({
    uxState: connectionState.uxState,
    hasCompletedFirstRun: true
  })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => serverCapabilitiesState
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

describe("GuardianSettings connection warning", () => {
  const makeQueryResult = (overrides: Record<string, unknown> = {}) =>
    ({
      data: { items: [], total: 0 },
      isLoading: false,
      isFetching: false,
      isRefetching: false,
      refetch: vi.fn(),
      ...overrides
    }) as any

  beforeEach(() => {
    serverCapabilitiesState.loading = false
    serverCapabilitiesState.capabilities = {
      hasGuardian: true,
      hasSelfMonitoring: true
    }
    connectionState.online = true
    connectionState.uxState = "connected_ok"
    connectionState.navigate.mockReset()
    useQueryClientMock.mockReturnValue({
      invalidateQueries: vi.fn()
    })
    useMutationMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false
    })
    useQueryMock.mockImplementation(() => makeQueryResult())
  })

  it("shows credential guidance when auth is missing", () => {
    connectionState.online = false
    connectionState.uxState = "error_auth"

    render(<GuardianSettings />)

    expect(
      screen.getByText("Add your credentials to manage Guardian settings.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }))
    expect(connectionState.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("shows setup guidance when setup is incomplete", () => {
    connectionState.online = false
    connectionState.uxState = "unconfigured"

    render(<GuardianSettings />)

    expect(
      screen.getByText("Finish setup to manage Guardian settings.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Finish Setup" }))
    expect(connectionState.navigate).toHaveBeenCalledWith("/")
  })

  it("suppresses the warning while connection checks are still testing", () => {
    connectionState.online = false
    connectionState.uxState = "testing"

    render(<GuardianSettings />)

    expect(
      screen.queryByText("Add your credentials to manage Guardian settings.")
    ).not.toBeInTheDocument()
    expect(screen.queryByText("Server offline")).not.toBeInTheDocument()
  })
})
