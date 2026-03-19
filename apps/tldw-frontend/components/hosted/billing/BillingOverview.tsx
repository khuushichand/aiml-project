import React from "react"
import Link from "next/link"
import { CreditCard, GaugeCircle, ReceiptText } from "lucide-react"

import type {
  BillingInvoiceListResponse,
  BillingSubscription,
  BillingUsage
} from "@web/lib/api/billing"
import { Button } from "@web/components/ui/Button"

const formatDate = (value?: string | null): string => {
  if (!value) return "Not scheduled"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not scheduled"
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  })
}

const formatMetric = (key: string, value: number | null | undefined): string => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Unavailable"
  }
  if (key.includes("storage")) {
    const valueGb = value / 1024
    return Number.isInteger(valueGb) ? `${valueGb} GB` : `${valueGb.toFixed(1)} GB`
  }
  return value.toLocaleString()
}

type BillingOverviewProps = {
  subscription: BillingSubscription | null
  usage: BillingUsage | null
  invoices: BillingInvoiceListResponse
  onManageBilling: () => void
  managingPortal: boolean
}

export function BillingOverview({
  subscription,
  usage,
  invoices,
  onManageBilling,
  managingPortal
}: BillingOverviewProps) {
  const limitEntries = usage ? Object.entries(usage.limit_checks ?? {}) : []
  const highlightedUsage = limitEntries.slice(0, 4)

  return (
    <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Current plan
            </p>
            <h2 className="text-3xl font-semibold text-text">
              {subscription?.plan_display_name || "No active plan"}
            </h2>
            <p className="text-sm leading-6 text-text-muted">
              {subscription
                ? "Keep an eye on entitlement state, renewal timing, and whether the org is headed toward overages."
                : "Choose a hosted plan to unlock the customer-facing subscription flow."}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={onManageBilling}
              loading={managingPortal}
              disabled={!subscription}
            >
              Open billing portal
            </Button>
            <Link
              href="/billing/success"
              className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-surface2"
            >
              Success page
            </Link>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-border/60 bg-surface/60 p-4">
            <div className="mb-3 inline-flex rounded-2xl bg-primary/10 p-3 text-primary">
              <CreditCard className="h-5 w-5" />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Status
            </p>
            <p className="mt-2 text-lg font-semibold capitalize text-text">
              {subscription?.status || "Pending"}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {subscription?.billing_cycle || "No billing cycle selected"}
            </p>
          </div>

          <div className="rounded-3xl border border-border/60 bg-surface/60 p-4">
            <div className="mb-3 inline-flex rounded-2xl bg-primary/10 p-3 text-primary">
              <GaugeCircle className="h-5 w-5" />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Renewal
            </p>
            <p className="mt-2 text-lg font-semibold text-text">
              {formatDate(subscription?.current_period_end || subscription?.trial_end)}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {subscription?.cancel_at_period_end ? "Cancels at period end" : "Renews automatically"}
            </p>
          </div>

          <div className="rounded-3xl border border-border/60 bg-surface/60 p-4">
            <div className="mb-3 inline-flex rounded-2xl bg-primary/10 p-3 text-primary">
              <ReceiptText className="h-5 w-5" />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
              Invoice history
            </p>
            <p className="mt-2 text-lg font-semibold text-text">{invoices.total}</p>
            <p className="mt-1 text-sm text-text-muted">
              Recent invoice records are available below.
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {highlightedUsage.length > 0 ? (
            highlightedUsage.map(([key, state]) => (
              <div
                key={key}
                className="rounded-2xl border border-border/60 bg-surface/50 px-4 py-3"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {formatMetric(key, state?.usage)} / {formatMetric(key, state?.limit ?? null)}
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {state?.exceeded ? "Limit exceeded" : "Within plan allowance"}
                </p>
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-border/70 bg-surface/40 px-4 py-6 text-sm text-text-muted">
              Usage data will appear here after the first hosted billing record is available.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-5 shadow-sm">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            Invoices
          </p>
          <h2 className="text-xl font-semibold text-text">Recent charges</h2>
          <p className="text-sm leading-6 text-text-muted">
            Keep the first launch supportable by exposing invoice state directly here before a richer portal exists.
          </p>
        </div>

        <div className="mt-5 space-y-3">
          {invoices.items.length > 0 ? (
            invoices.items.map((invoice) => (
              <article
                key={invoice.id}
                className="rounded-2xl border border-border/60 bg-surface/50 px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {invoice.description || `Invoice #${invoice.id}`}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-text-muted">
                      {invoice.status}
                    </p>
                  </div>
                  <p className="text-base font-semibold text-text">
                    {invoice.amount_display || `$${(invoice.amount_cents / 100).toFixed(2)}`}
                  </p>
                </div>

                <div className="mt-3 flex items-center justify-between gap-3 text-sm text-text-muted">
                  <span>{formatDate(invoice.created_at)}</span>
                  {invoice.invoice_pdf_url ? (
                    <a
                      className="font-medium text-primary hover:underline"
                      href={invoice.invoice_pdf_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Download PDF
                    </a>
                  ) : (
                    <span>PDF unavailable</span>
                  )}
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-border/70 bg-surface/40 px-4 py-6 text-sm text-text-muted">
              Invoice records will appear after the first successful hosted charge.
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
