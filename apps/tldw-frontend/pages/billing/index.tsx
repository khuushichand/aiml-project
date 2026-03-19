import React from "react"

import { BillingOverview } from "@web/components/hosted/billing/BillingOverview"
import { PlanSelector } from "@web/components/hosted/billing/PlanSelector"
import {
  createCheckoutSession,
  createPortalSession,
  fetchInvoices,
  fetchPlans,
  fetchSubscription,
  fetchUsage,
  type BillingInvoiceListResponse,
  type BillingPlan,
  type BillingSubscription,
  type BillingUsage
} from "@web/lib/api/billing"

const toAbsoluteUrl = (path: string): string => {
  if (typeof window === "undefined") {
    return path
  }
  return new URL(path, window.location.origin).toString()
}

export default function BillingPage() {
  const [subscription, setSubscription] = React.useState<BillingSubscription | null>(null)
  const [usage, setUsage] = React.useState<BillingUsage | null>(null)
  const [invoices, setInvoices] = React.useState<BillingInvoiceListResponse>({
    items: [],
    total: 0
  })
  const [plans, setPlans] = React.useState<BillingPlan[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [managingPortal, setManagingPortal] = React.useState(false)
  const [pendingPlanName, setPendingPlanName] = React.useState<string | null>(null)
  const [billingCycle, setBillingCycle] = React.useState<"monthly" | "yearly">("monthly")

  React.useEffect(() => {
    let cancelled = false

    const loadBilling = async () => {
      setLoading(true)
      setError(null)

      try {
        const [nextSubscription, nextUsage, nextInvoices, nextPlans] =
          await Promise.all([
            fetchSubscription(),
            fetchUsage(),
            fetchInvoices(),
            fetchPlans()
          ])

        if (cancelled) {
          return
        }

        setSubscription(nextSubscription)
        setUsage(nextUsage)
        setInvoices(nextInvoices)
        setPlans(nextPlans.plans ?? [])
      } catch (caughtError) {
        if (!cancelled) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Unable to load billing information right now."
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadBilling()

    return () => {
      cancelled = true
    }
  }, [])

  const handleManageBilling = async () => {
    setManagingPortal(true)
    setError(null)

    try {
      const session = await createPortalSession({
        returnUrl: toAbsoluteUrl("/billing")
      })
      window.location.assign(session.url)
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to open the billing portal right now."
      )
    } finally {
      setManagingPortal(false)
    }
  }

  const handleSelectPlan = async (planName: string) => {
    setPendingPlanName(planName)
    setError(null)

    try {
      const session = await createCheckoutSession({
        planName,
        billingCycle,
        successUrl: toAbsoluteUrl("/billing/success"),
        cancelUrl: toAbsoluteUrl("/billing/cancel")
      })
      window.location.assign(session.url)
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to start checkout right now."
      )
    } finally {
      setPendingPlanName(null)
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-6 text-sm text-text-muted shadow-sm">
          Loading billing details...
        </div>
      </div>
    )
  }

  if (error && !subscription && !usage && plans.length === 0) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-[1.75rem] border border-danger/30 bg-danger/5 p-6 text-sm text-text">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_right,_rgba(16,185,129,0.16),_transparent_24%),linear-gradient(180deg,_rgba(255,255,255,0.88),_rgba(255,255,255,0.94))] p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            Billing
          </p>
          <h1 className="font-serif text-4xl text-text">Hosted plan and usage</h1>
          <p className="max-w-3xl text-sm leading-6 text-text-muted">
            Keep the first paid launch legible. The page shows subscription status, usage posture, invoices, and a direct path into checkout or the billing portal.
          </p>
        </div>
      </section>

      {error ? (
        <div className="rounded-[1.5rem] border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-text">
          {error}
        </div>
      ) : null}

      <BillingOverview
        subscription={subscription}
        usage={usage}
        invoices={invoices}
        onManageBilling={handleManageBilling}
        managingPortal={managingPortal}
      />

      <PlanSelector
        plans={plans}
        billingCycle={billingCycle}
        currentPlanName={subscription?.plan_name}
        pendingPlanName={pendingPlanName}
        onBillingCycleChange={setBillingCycle}
        onSelectPlan={handleSelectPlan}
      />
    </div>
  )
}
