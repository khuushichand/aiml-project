import React from "react"

import type { BillingPlan } from "@web/lib/api/billing"
import { Button } from "@web/components/ui/Button"

type PlanSelectorProps = {
  plans: BillingPlan[]
  billingCycle: "monthly" | "yearly"
  currentPlanName?: string
  pendingPlanName?: string | null
  onBillingCycleChange: (billingCycle: "monthly" | "yearly") => void
  onSelectPlan: (planName: string) => void
}

const formatPrice = (price?: number): string => {
  if (typeof price !== "number" || !Number.isFinite(price)) {
    return "Contact sales"
  }
  if (price === 0) {
    return "$0"
  }
  return `$${price.toFixed(0)}`
}

export function PlanSelector({
  plans,
  billingCycle,
  currentPlanName,
  pendingPlanName,
  onBillingCycleChange,
  onSelectPlan
}: PlanSelectorProps) {
  const visiblePlans = plans.filter((plan) => plan.is_public !== false && plan.is_active !== false)

  return (
    <section className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            Plan selector
          </p>
          <h2 className="text-2xl font-semibold text-text">Upgrade or change your tier</h2>
          <p className="max-w-2xl text-sm leading-6 text-text-muted">
            Keep the first hosted billing offer opinionated. Expose a small set of customer-visible plans and route every paid change through the backend checkout flow.
          </p>
        </div>

        <div className="inline-flex rounded-full border border-border/70 bg-surface/70 p-1">
          {(["monthly", "yearly"] as const).map((cycle) => (
            <button
              key={cycle}
              type="button"
              className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                billingCycle === cycle
                  ? "bg-primary text-white"
                  : "text-text-muted hover:text-text"
              }`}
              onClick={() => onBillingCycleChange(cycle)}
            >
              {cycle === "monthly" ? "Monthly" : "Yearly"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {visiblePlans.map((plan) => {
          const cyclePrice =
            billingCycle === "yearly" ? plan.price_usd_yearly : plan.price_usd_monthly
          const isCurrentPlan = plan.name === currentPlanName
          const isPending = pendingPlanName === plan.name

          return (
            <article
              key={plan.name}
              className={`rounded-[1.5rem] border p-5 transition-colors ${
                isCurrentPlan
                  ? "border-primary/40 bg-primary/5"
                  : "border-border/70 bg-surface/50"
              }`}
            >
              <div className="space-y-2">
                <p className="text-sm font-semibold uppercase tracking-[0.16em] text-text-muted">
                  {plan.display_name}
                </p>
                <p className="text-3xl font-semibold text-text">{formatPrice(cyclePrice)}</p>
                <p className="text-sm text-text-muted">
                  per {billingCycle === "monthly" ? "month" : "year"}
                </p>
                <p className="min-h-[3rem] text-sm leading-6 text-text-muted">
                  {plan.description || "Hosted access to the core tldw workflow."}
                </p>
              </div>

              <div className="mt-5 space-y-2 text-sm text-text-muted">
                {Object.entries(plan.limits ?? {})
                  .slice(0, 4)
                  .map(([key, value]) => (
                    <div key={`${plan.name}-${key}`} className="flex items-center justify-between gap-3">
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-medium text-text">{String(value)}</span>
                    </div>
                  ))}
              </div>

              <div className="mt-6">
                <Button
                  type="button"
                  className="w-full"
                  variant={isCurrentPlan ? "secondary" : "primary"}
                  disabled={isCurrentPlan}
                  loading={isPending}
                  onClick={() => onSelectPlan(plan.name)}
                >
                  {isCurrentPlan ? "Current plan" : `Choose ${plan.display_name}`}
                </Button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
