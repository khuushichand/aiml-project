import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CommandAnalyticsSummary } from "../CommandAnalyticsSummary"

describe("CommandAnalyticsSummary", () => {
  it("renders total runs, success rate, and fallback rate", () => {
    render(
      <CommandAnalyticsSummary
        analytics={{
          persona_id: "persona-1",
          summary: {
            total_events: 8,
            direct_command_count: 6,
            planner_fallback_count: 2,
            success_rate: 75,
            fallback_rate: 25,
            avg_response_time_ms: 180
          },
          live_voice: {
            total_committed_turns: 5,
            vad_auto_commit_count: 3,
            manual_commit_count: 2,
            vad_auto_rate: 60,
            manual_commit_rate: 40,
            degraded_session_count: 1
          },
          commands: [],
          fallbacks: {
            total_invocations: 2,
            success_count: 2,
            error_count: 0,
            avg_response_time_ms: 220,
            last_used: "2026-03-12T18:40:00Z"
          }
        }}
      />
    )

    expect(screen.getByTestId("persona-command-analytics-summary")).toBeInTheDocument()
    expect(screen.getByTestId("persona-command-analytics-total-events")).toHaveTextContent(
      "8"
    )
    expect(screen.getByTestId("persona-command-analytics-success-rate")).toHaveTextContent(
      "75%"
    )
    expect(screen.getByTestId("persona-command-analytics-fallback-rate")).toHaveTextContent(
      "25%"
    )
    expect(screen.getByTestId("persona-command-analytics-fallback-note")).toHaveTextContent(
      "2 planner fallbacks"
    )
    expect(screen.getByTestId("persona-command-analytics-live-auto-rate")).toHaveTextContent(
      "60%"
    )
    expect(screen.getByTestId("persona-command-analytics-live-manual-rate")).toHaveTextContent(
      "40%"
    )
    expect(screen.getByTestId("persona-command-analytics-live-degraded-note")).toHaveTextContent(
      "1 degraded live session"
    )
  })
})
