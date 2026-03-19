import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  login: vi.fn()
}))

const mockRouter = {
  pathname: "/login",
  asPath: "/login",
  query: {},
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn()
}

vi.mock("next/router", () => ({
  useRouter: () => mockRouter
}))

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string
    children: React.ReactNode
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  )
}))

vi.mock("@/services/tldw/TldwAuth", () => ({
  tldwAuth: {
    login: (...args: unknown[]) => mocks.login(...args)
  }
}))

import LoginPage from "@web/pages/login"

describe("LoginPage hosted mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    mocks.login.mockResolvedValue({ token_type: "bearer" })
    mockRouter.push.mockReset()
  })

  it("renders hosted login instead of server settings in hosted mode", () => {
    render(<LoginPage />)

    expect(
      screen.getByRole("heading", { name: /sign in/i })
    ).toBeInTheDocument()
    expect(screen.queryByText(/server url/i)).toBeNull()
  })

  it("submits magic-link requests through the hosted auth endpoint", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "sent" }), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    )
    vi.stubGlobal("fetch", fetchMock)

    render(<LoginPage />)

    await user.type(screen.getByLabelText(/email/i), "user@example.com")
    await user.click(
      screen.getByRole("button", { name: /email me a sign-in link/i })
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/magic-link/request",
        expect.objectContaining({
          method: "POST"
        })
      )
    })
  })
})
