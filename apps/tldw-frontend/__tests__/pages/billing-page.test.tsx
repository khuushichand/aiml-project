import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

import BillingPage from "@web/pages/billing"

describe("BillingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
  })

  it("loads subscription, usage, and invoice data into the billing page", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === "/api/proxy/billing/subscription") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              org_id: 21,
              plan_name: "pro",
              plan_display_name: "Pro",
              status: "active",
              billing_cycle: "monthly",
              current_period_end: "2026-04-18T00:00:00Z",
              cancel_at_period_end: false,
              limits: {
                storage_mb: 5120,
                rag_queries_day: 200
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
      }

      if (url === "/api/proxy/billing/usage") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              org_id: 21,
              plan_name: "pro",
              limits: {
                storage_mb: 5120,
                rag_queries_day: 200
              },
              usage: {
                storage_mb: 1024,
                rag_queries_day: 42
              },
              limit_checks: {
                storage_mb: {
                  usage: 1024,
                  limit: 5120,
                  exceeded: false
                },
                rag_queries_day: {
                  usage: 42,
                  limit: 200,
                  exceeded: false
                }
              },
              has_warnings: false,
              has_exceeded: false
            }),
            {
              status: 200,
              headers: {
                "Content-Type": "application/json"
              }
            }
          )
        )
      }

      if (url === "/api/proxy/billing/invoices") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: 91,
                  org_id: 21,
                  stripe_invoice_id: "in_123",
                  amount_cents: 2900,
                  amount_display: "$29.00",
                  currency: "usd",
                  status: "succeeded",
                  description: "Pro monthly",
                  invoice_pdf_url: "https://example.com/invoice.pdf",
                  created_at: "2026-03-01T00:00:00Z"
                }
              ],
              total: 1
            }),
            {
              status: 200,
              headers: {
                "Content-Type": "application/json"
              }
            }
          )
        )
      }

      if (url === "/api/proxy/billing/plans") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              plans: [
                {
                  id: 1,
                  name: "free",
                  display_name: "Free",
                  description: "Get started",
                  price_usd_monthly: 0,
                  price_usd_yearly: 0,
                  limits: {
                    storage_mb: 512
                  },
                  is_active: true,
                  is_public: true
                },
                {
                  id: 2,
                  name: "pro",
                  display_name: "Pro",
                  description: "Core hosted workflow",
                  price_usd_monthly: 29,
                  price_usd_yearly: 290,
                  limits: {
                    storage_mb: 5120
                  },
                  is_active: true,
                  is_public: true
                }
              ]
            }),
            {
              status: 200,
              headers: {
                "Content-Type": "application/json"
              }
            }
          )
        )
      }

      return Promise.reject(new Error(`Unexpected fetch: ${url}`))
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<BillingPage />)

    await waitFor(() => {
      expect(
        screen.getByText(/current plan/i, { selector: "p" })
      ).toBeInTheDocument()
    })
    expect(screen.getByRole("heading", { level: 2, name: /^pro$/i })).toBeInTheDocument()
    expect(screen.getByText(/\$29\.00/)).toBeInTheDocument()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/proxy/billing/subscription",
        expect.objectContaining({
          method: "GET"
        })
      )
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/proxy/billing/usage",
        expect.objectContaining({
          method: "GET"
        })
      )
    })
  })
})
