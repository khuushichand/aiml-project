import React from "react"
import { Check, X, Minus } from "lucide-react"

interface ComparisonRow {
  feature: string
  tldw: boolean | "partial" | string
  competitors: Record<string, boolean | "partial" | string>
}

interface LandingComparisonProps {
  headline: string
  competitors: string[]
  rows: ComparisonRow[]
}

export function LandingComparison({ headline, competitors, rows }: LandingComparisonProps) {
  const renderCell = (value: boolean | "partial" | string) => {
    if (value === true) return <Check className="w-5 h-5 text-success" />
    if (value === false) return <X className="w-5 h-5 text-danger" />
    if (value === "partial") return <Minus className="w-5 h-5 text-warn" />
    return <span className="text-sm text-text-muted">{value}</span>
  }

  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-16">{headline}</h2>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-4 px-4 font-medium">Feature</th>
                <th className="text-center py-4 px-4 font-medium bg-primary/5">tldw</th>
                {competitors.map((comp) => (
                  <th key={comp} className="text-center py-4 px-4 font-medium text-text-muted">
                    {comp}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.feature} className="border-b border-border">
                  <td className="py-4 px-4">{row.feature}</td>
                  <td className="py-4 px-4 text-center bg-primary/5">
                    {renderCell(row.tldw)}
                  </td>
                  {competitors.map((comp) => (
                    <td key={comp} className="py-4 px-4 text-center">
                      {renderCell(row.competitors[comp])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
