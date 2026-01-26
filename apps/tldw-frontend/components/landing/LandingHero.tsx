import React from "react"
import Link from "next/link"
import { Shield, Server, Github } from "lucide-react"

interface LandingHeroProps {
  headline: string
  subheadline: string
  primaryCTA: { text: string; href: string }
  secondaryCTA: { text: string; href: string }
  badges?: string[]
}

export function LandingHero({
  headline,
  subheadline,
  primaryCTA,
  secondaryCTA,
  badges = ["Open Source", "Self-Hosted", "No Telemetry"],
}: LandingHeroProps) {
  return (
    <section className="py-24 px-6">
      <div className="max-w-4xl mx-auto text-center">
        {/* Trust Badges */}
        <div className="flex items-center justify-center gap-4 mb-8 flex-wrap">
          {badges.map((badge) => (
            <span
              key={badge}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-surface rounded-full text-xs font-medium text-text-muted border border-border"
            >
              {badge === "Open Source" && <Github className="w-3 h-3" />}
              {badge === "Self-Hosted" && <Server className="w-3 h-3" />}
              {badge === "No Telemetry" && <Shield className="w-3 h-3" />}
              {badge === "Air-Gap Compatible" && <Shield className="w-3 h-3" />}
              {badge === "IRB Compliant" && <Shield className="w-3 h-3" />}
              {badge}
            </span>
          ))}
        </div>

        {/* Headline */}
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight mb-6">
          {headline.split("\n").map((line, i) => (
            <React.Fragment key={i}>
              {line}
              {i < headline.split("\n").length - 1 && <br />}
            </React.Fragment>
          ))}
        </h1>

        {/* Subheadline */}
        <p className="text-xl text-text-muted max-w-2xl mx-auto mb-10">
          {subheadline}
        </p>

        {/* CTAs */}
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            href={primaryCTA.href}
            className="px-6 py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
          >
            {primaryCTA.text}
          </Link>
          <Link
            href={secondaryCTA.href}
            className="px-6 py-3 bg-surface border border-border rounded-lg font-medium hover:bg-surface/80 transition-colors"
          >
            {secondaryCTA.text}
          </Link>
        </div>

        {/* Small Print */}
        <p className="mt-6 text-sm text-text-muted">
          No credit card required. No data collection. Free to self-host forever.
        </p>
      </div>
    </section>
  )
}
