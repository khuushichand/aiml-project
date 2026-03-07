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
}

describe("Header research link", () => {
  beforeEach(() => {
    authState.logout.mockClear()
    process.env.NEXT_PUBLIC_ENABLE_RUNS_LINK = "1"
    process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN = "1"
  })

  it("shows Research for non-admin users even when the legacy admin flag is enabled", () => {
    authState.user = {
      username: "normal-user",
      role: "user",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    const link = screen.getByRole("link", { name: "Research" })
    expect(link).toBeInTheDocument()
    expect(link.getAttribute("href")).toBe("/research")
  })

  it("shows Research for admin users", () => {
    authState.user = {
      username: "admin-user",
      role: "admin",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    const link = screen.getByRole("link", { name: "Research" })
    expect(link).toBeInTheDocument()
    expect(link.getAttribute("href")).toBe("/research")
  })

  it("shows Research when the user has an admin claims shape", () => {
    authState.user = {
      username: "claims-admin-user",
      role: "user",
      roles: ["admin"],
      is_admin: false
    }

    render(<Header />)

    expect(screen.getByRole("link", { name: "Research" })).toBeInTheDocument()
  })

  it("shows Research for non-admin when the legacy admin requirement is disabled", () => {
    process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN = "0"
    authState.user = {
      username: "normal-user-2",
      role: "user",
      roles: ["user"],
      is_admin: false
    }

    render(<Header />)

    expect(screen.getByRole("link", { name: "Research" })).toBeInTheDocument()
  })
})

afterEach(() => {
  resetEnv()
})
