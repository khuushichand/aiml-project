// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SessionInsightsPanel } from "../SessionInsightsPanel"

const t = ((key: string, fallback?: string, options?: Record<string, unknown>) => {
  const template = fallback || key
  if (!options) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = options[token]
    return value == null ? "" : String(value)
  })
}) as any

describe("SessionInsightsPanel", () => {
  it("filters models by provider and supports drilldown details", () => {
    render(
      <SessionInsightsPanel
        t={t}
        insights={{
          totals: {
            generatedMessages: 5,
            totalTokens: 900,
            estimatedCostUsd: 0.12
          },
          providers: [
            {
              providerKey: "openai",
              modelCount: 1,
              totalTokens: 600,
              estimatedCostUsd: 0.08
            },
            {
              providerKey: "anthropic",
              modelCount: 1,
              totalTokens: 300,
              estimatedCostUsd: 0.04
            }
          ],
          models: [
            {
              key: "openai::gpt-4o-mini",
              providerKey: "openai",
              modelId: "gpt-4o-mini",
              messageCount: 3,
              inputTokens: 360,
              outputTokens: 240,
              totalTokens: 600,
              estimatedCostUsd: 0.08
            },
            {
              key: "anthropic::claude-3-5-sonnet",
              providerKey: "anthropic",
              modelId: "claude-3-5-sonnet",
              messageCount: 2,
              inputTokens: 180,
              outputTokens: 120,
              totalTokens: 300,
              estimatedCostUsd: 0.04
            }
          ],
          topics: [
            { label: "research", count: 4 },
            { label: "migration", count: 3 }
          ]
        }}
      />
    )

    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument()
    expect(screen.getByText("claude-3-5-sonnet")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "openai" }))
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument()
    expect(screen.queryByText("claude-3-5-sonnet")).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: "View details" }))
    expect(screen.getByTestId("session-insights-drilldown")).toHaveTextContent(
      "Model detail"
    )
    expect(screen.getByTestId("session-insights-drilldown")).toHaveTextContent(
      "gpt-4o-mini"
    )
  })
})
