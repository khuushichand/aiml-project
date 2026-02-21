// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ModelRecommendationsPanel } from "../ModelRecommendationsPanel"
import type { ModelRecommendationAction } from "../model-recommendations"

const t = ((key: string, fallback?: string) => fallback || key) as any

describe("ModelRecommendationsPanel integration", () => {
  it("wires recommendation actions, dismiss controls, and insights shortcut", async () => {
    const user = userEvent.setup()
    const onOpenInsights = vi.fn()
    const onRunAction = vi.fn()
    const onDismiss = vi.fn()
    const getActionLabel = (action: ModelRecommendationAction) => {
      if (action === "enable_json_mode") return "Enable JSON"
      if (action === "open_context_window") return "Adjust context"
      if (action === "open_session_insights") return "Open insights"
      return "Review models"
    }

    render(
      <ModelRecommendationsPanel
        t={t}
        recommendations={[
          {
            id: "structured-json-mode",
            title: "Enable JSON mode for structured output",
            reason: "Structured output was requested.",
            action: "enable_json_mode"
          },
          {
            id: "token-risk",
            title: "Reduce truncation risk before sending",
            reason: "Context budget is near limit.",
            action: "open_context_window"
          }
        ]}
        showOpenInsights
        onOpenInsights={onOpenInsights}
        onRunAction={onRunAction}
        onDismiss={onDismiss}
        getActionLabel={getActionLabel}
      />
    )

    expect(screen.getByTestId("model-recommendations-panel")).toBeInTheDocument()
    expect(
      screen.getByText("Enable JSON mode for structured output")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Reduce truncation risk before sending")
    ).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Open insights" }))
    await user.click(screen.getByRole("button", { name: "Enable JSON" }))
    await user.click(screen.getByRole("button", { name: "Adjust context" }))
    await user.click(
      screen.getByTestId("model-recommendation-structured-json-mode").querySelector(
        "button[aria-label='Dismiss recommendation']"
      ) as HTMLElement
    )

    expect(onOpenInsights).toHaveBeenCalledTimes(1)
    expect(onRunAction).toHaveBeenCalledWith("enable_json_mode")
    expect(onRunAction).toHaveBeenCalledWith("open_context_window")
    expect(onDismiss).toHaveBeenCalledWith("structured-json-mode")
  })

  it("returns null when there are no recommendations", () => {
    const { container } = render(
      <ModelRecommendationsPanel
        t={t}
        recommendations={[]}
        showOpenInsights={false}
        onOpenInsights={vi.fn()}
        onRunAction={vi.fn()}
        onDismiss={vi.fn()}
        getActionLabel={() => "Run"}
      />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
