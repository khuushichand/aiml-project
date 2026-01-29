import React from "react"
import Link from "next/link"

interface LandingCTAProps {
  headline: string
  description: string
  primaryCTA: { text: string; href: string }
  secondaryCTA?: { text: string; href: string }
}

export function LandingCTA({ headline, description, primaryCTA, secondaryCTA }: LandingCTAProps) {
  return (
    <section className="py-24 px-6">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl font-bold mb-4">{headline}</h2>
        <p className="text-xl text-text-muted mb-8">{description}</p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            href={primaryCTA.href}
            className="px-8 py-4 bg-primary text-white rounded-lg font-medium text-lg hover:bg-primary/90 transition-colors"
          >
            {primaryCTA.text}
          </Link>
          {secondaryCTA && (
            <Link
              href={secondaryCTA.href}
              className="px-8 py-4 bg-surface border border-border rounded-lg font-medium text-lg hover:bg-surface/80 transition-colors"
            >
              {secondaryCTA.text}
            </Link>
          )}
        </div>

        <p className="mt-6 text-sm text-text-muted">
          No credit card required. No data collection. Open source.
        </p>
      </div>
    </section>
  )
}
