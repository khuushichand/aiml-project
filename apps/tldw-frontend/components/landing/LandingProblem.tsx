import React from "react"
import { AlertTriangle, X } from "lucide-react"

interface LandingProblemProps {
  headline: string
  problems: string[]
  conclusion: string
}

export function LandingProblem({ headline, problems, conclusion }: LandingProblemProps) {
  return (
    <section className="py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <AlertTriangle className="w-6 h-6 text-warn" />
          <h2 className="text-3xl font-bold">{headline}</h2>
        </div>

        <div className="space-y-4 mb-8">
          {problems.map((problem, i) => (
            <div
              key={i}
              className="flex items-start gap-3 p-4 bg-danger/5 border border-danger/20 rounded-lg"
            >
              <X className="w-5 h-5 text-danger mt-0.5 flex-shrink-0" />
              <p className="text-text-muted">{problem}</p>
            </div>
          ))}
        </div>

        <p className="text-lg font-medium text-primary">{conclusion}</p>
      </div>
    </section>
  )
}
