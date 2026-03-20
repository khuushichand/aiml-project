import React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const mockRouter = {
  pathname: "/",
  asPath: "/",
  push: vi.fn(),
  replace: vi.fn()
}

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  user: null as any,
  logout: vi.fn()
}))

vi.mock("next/router", () => ({
  useRouter: () => mockRouter
}))

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={typeof href === "string" ? href : ""} {...rest}>
      {children}
    </a>
  )
}))

vi.mock("@web/hooks/useAuth", () => ({
  useAuth: () => authState
}))

import { Header } from "@web/components/layout/Header"

const originalEnableRunsLink = process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK
const originalRequireAdmin = process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN
const originalDeploymentMode = process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE

const resetEnv = () => {
  if (originalEnableRunsLink === undefined) {
    delete process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK
  } else {
    process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK = originalEnableRunsLink
  }
  if (originalRequireAdmin === undefined) {
    delete process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN
  } else {
    process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN = originalRequireAdmin
  }
  if (originalDeploymentMode === undefined) {
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  } else {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = originalDeploymentMode
  }
}

describe("Header runs link role gating", () => {
  beforeEach(() => {
    authState.logout.mockClear()
    process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK = "1"
    process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN = "1"
  })

  it("hides Runs when admin is required and user is non-admin", () => {
    authState.user = {
      username: "normal-user",
      role: "user",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    expect(screen.queryByRole("link", { name: "Runs" })).toBeNull()
  })

  it("shows Runs when admin is required and user role is admin", () => {
    authState.user = {
      username: "admin-user",
      role: "admin",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    const link = screen.getByRole("link", { name: "Runs" })
    expect(link).toBeInTheDocument()
    expect(link.getAttribute("href")).toBe("/admin/watchlists-runs")
  })

  it("shows Runs when admin is required and user has admin claims shape", () => {
    authState.user = {
      username: "claims-admin-user",
      role: "user",
      roles: ["admin"],
      is_admin: false
    }

    render(<Header />)

    expect(screen.getByRole("link", { name: "Runs" })).toBeInTheDocument()
  })

  it("shows Runs for non-admin when admin requirement is disabled", () => {
    process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN = "0"
    authState.user = {
      username: "normal-user-2",
      role: "user",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    expect(screen.getByRole("link", { name: "Runs" })).toBeInTheDocument()
  })
})

afterEach(() => {
  resetEnv()
})
