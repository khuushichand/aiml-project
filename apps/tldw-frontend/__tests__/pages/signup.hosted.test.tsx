import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mockRouter = {
  pathname: "/signup",
  asPath: "/signup",
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

import SignupPage from "@web/pages/signup"

describe("SignupPage hosted mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    mockRouter.push.mockReset()
  })

  it("submits registration through the hosted auth endpoint", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          message: "Registration successful",
          requires_verification: true
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json"
          }
        }
      )
    )
    vi.stubGlobal("fetch", fetchMock)

    render(<SignupPage />)

    await user.type(screen.getByLabelText(/username/i), "new-user")
    await user.type(screen.getByLabelText(/^email$/i), "new-user@example.com")
    await user.type(screen.getByLabelText(/password/i), "StrongPassword123!")
    await user.click(screen.getByRole("button", { name: /create account/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/register",
        expect.objectContaining({
          method: "POST"
        })
      )
    })

    expect(
      await screen.findByText(/check your email to verify your account/i)
    ).toBeInTheDocument()
  })
})
