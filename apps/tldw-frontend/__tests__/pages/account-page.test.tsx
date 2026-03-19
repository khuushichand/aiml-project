import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

import AccountPage from "@web/pages/account"

describe("AccountPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  })

  it("loads the authenticated user profile into the account page", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          profile_version: "v1",
          catalog_version: "v1",
          user: {
            id: 7,
            username: "owner",
            email: "owner@example.com",
            role: "user",
            is_active: true,
            is_verified: true,
            created_at: "2026-02-01T00:00:00Z",
            last_login: "2026-03-17T10:00:00Z",
            storage_quota_mb: 5120,
            storage_used_mb: 1024
          },
          memberships: [
            {
              org_id: 21,
              org_name: "Northwind Research",
              role: "owner",
              is_active: true,
              is_default: true
            }
          ],
          security: {
            verified: true,
            mfa_enabled: false
          },
          quotas: {
            storage_quota_mb: 5120,
            storage_used_mb: 1024
          }
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

    render(<AccountPage />)

    expect(await screen.findByText("owner@example.com")).toBeInTheDocument()
    expect(screen.getByText(/northwind research/i)).toBeInTheDocument()
    expect(screen.getByText(/5 gb/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /open billing/i })).toHaveAttribute(
      "href",
      "/billing"
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/proxy/users/me/profile",
        expect.objectContaining({
          method: "GET"
        })
      )
    })
  })
})
