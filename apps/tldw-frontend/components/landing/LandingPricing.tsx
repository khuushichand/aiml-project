import React from "react"
import Link from "next/link"
import { Check } from "lucide-react"
import { cn } from "@web/lib/utils"

interface PricingTier {
  name: string
  price: string
  period?: string
  description: string
  features: string[]
  cta: { text: string; href: string }
  highlighted?: boolean
}

interface LandingPricingProps {
  headline: string
  tiers: PricingTier[]
  footnote?: string
}

export function LandingPricing({ headline, tiers, footnote }: LandingPricingProps) {
  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">{headline}</h2>

        <div className="grid md:grid-cols-3 gap-8">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={cn(
                "p-6 rounded-xl border",
                tier.highlighted
                  ? "border-primary bg-primary/5 ring-2 ring-primary"
                  : "border-border bg-surface"
              )}
            >
              <h3 className="text-xl font-semibold mb-2">{tier.name}</h3>
              <div className="mb-4">
                <span className="text-3xl font-bold">{tier.price}</span>
                {tier.period && (
                  <span className="text-text-muted">/{tier.period}</span>
                )}
              </div>
              <p className="text-text-muted mb-6">{tier.description}</p>

              <ul className="space-y-3 mb-8">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={tier.cta.href}
                className={cn(
                  "block text-center py-3 rounded-lg font-medium transition-colors",
                  tier.highlighted
                    ? "bg-primary text-white hover:bg-primary/90"
                    : "bg-bg border border-border hover:bg-surface"
                )}
              >
                {tier.cta.text}
              </Link>
            </div>
          ))}
        </div>

        {footnote && (
          <p className="text-center text-sm text-text-muted mt-8">{footnote}</p>
        )}
      </div>
    </section>
  )
}
