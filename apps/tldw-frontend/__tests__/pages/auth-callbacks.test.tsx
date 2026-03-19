import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  verifyMagicLink: vi.fn()
}))

const mockRouter = {
  pathname: "/auth/verify-email",
  asPath: "/auth/verify-email",
  query: {},
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn()
}

vi.mock("next/router", () => ({
  useRouter: () => mockRouter
}))

vi.mock("@/services/tldw/TldwAuth", () => ({
  tldwAuth: {
    verifyMagicLink: (...args: unknown[]) => mocks.verifyMagicLink(...args)
  }
}))

import VerifyEmailPage from "@web/pages/auth/verify-email"
import ResetPasswordPage from "@web/pages/auth/reset-password"
import MagicLinkPage from "@web/pages/auth/magic-link"

describe("Hosted auth callback pages", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    mockRouter.push.mockReset()
    mocks.verifyMagicLink.mockResolvedValue({ token_type: "bearer" })
  })

  it("verifies email via the hosted auth route", async () => {
    mockRouter.pathname = "/auth/verify-email"
    mockRouter.asPath = "/auth/verify-email?token=verify-token-1"
    mockRouter.query = { token: "verify-token-1" }

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "Email verified successfully" }), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    )
    vi.stubGlobal("fetch", fetchMock)

    render(<VerifyEmailPage />)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/verify-email",
        expect.objectContaining({
          method: "POST"
        })
      )
    })

    expect(
      await screen.findByText(/email verified successfully/i)
    ).toBeInTheDocument()
  })

  it("submits password resets through the hosted auth route", async () => {
    mockRouter.pathname = "/auth/reset-password"
    mockRouter.asPath = "/auth/reset-password?token=reset-token-1"
    mockRouter.query = { token: "reset-token-1" }

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ message: "Password has been reset successfully" }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json"
          }
        }
      )
    )
    vi.stubGlobal("fetch", fetchMock)

    render(<ResetPasswordPage />)

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/new password/i), "NextPassword123!")
    await user.click(screen.getByRole("button", { name: /reset password/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/reset-password",
        expect.objectContaining({
          method: "POST"
        })
      )
    })
  })

  it("verifies magic links through the hosted auth service", async () => {
    mockRouter.pathname = "/auth/magic-link"
    mockRouter.asPath = "/auth/magic-link?token=magic-token-1"
    mockRouter.query = { token: "magic-token-1" }

    render(<MagicLinkPage />)

    await waitFor(() => {
      expect(mocks.verifyMagicLink).toHaveBeenCalledWith("magic-token-1")
    })

    expect(
      await screen.findByText(/signed in successfully/i)
    ).toBeInTheDocument()
  })
})
