import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { EvaluationsSettings } from "../evaluations"

const connectionState = {
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

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: {
      defaultEvalType: "response_quality",
      defaultTargetModel: "gpt-4o-mini",
      defaultRunConfig: "",
      defaultDatasetId: null,
      defaultSpecByType: {}
    },
    isLoading: false
  }),
  useMutation: () => ({
    mutateAsync: vi.fn(),
    isPending: false
  })
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

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      return fallbackOrOptions?.defaultValue ?? _key
    }
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => connectionState.online
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionUxState: () => ({
    uxState: connectionState.uxState,
    hasCompletedFirstRun: true
  })
}))

vi.mock("@/services/evaluations", () => ({
  getRateLimits: vi.fn()
}))

vi.mock("@/services/evaluations-settings", () => ({
  getEvaluationDefaults: vi.fn(),
  setEvaluationDefaults: vi.fn(),
  setDefaultSpecForType: vi.fn()
}))

describe("EvaluationsSettings connection warning", () => {
  beforeEach(() => {
    connectionState.online = true
    connectionState.uxState = "connected_ok"
    connectionState.navigate.mockReset()
  })

  it("shows credential guidance when auth is missing", () => {
    connectionState.online = false
    connectionState.uxState = "error_auth"

    render(<EvaluationsSettings />)

    expect(
      screen.getByText("Add your credentials to test Evaluations.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }))
    expect(connectionState.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("shows unreachable guidance when the server is unreachable", () => {
    connectionState.online = false
    connectionState.uxState = "error_unreachable"

    render(<EvaluationsSettings />)

    expect(
      screen.getByText("Can't reach your tldw server right now.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Health & diagnostics" }))
    expect(connectionState.navigate).toHaveBeenCalledWith("/settings/health")
  })

  it("suppresses the warning while connection checks are still testing", () => {
    connectionState.online = false
    connectionState.uxState = "testing"

    render(<EvaluationsSettings />)

    expect(
      screen.queryByText("Add your credentials to test Evaluations.")
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText("Connect to your tldw server to test Evaluations.")
    ).not.toBeInTheDocument()
  })
})
