import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

import {
  PersonaSetupAnalyticsCard,
  type PersonaSetupAnalyticsResponse
} from "../PersonaSetupAnalyticsCard"

const buildAnalytics = (
  overrides: Partial<PersonaSetupAnalyticsResponse["summary"]> = {}
): PersonaSetupAnalyticsResponse => ({
  persona_id: "garden-helper",
  summary: {
    total_runs: 4,
    completed_runs: 3,
    completion_rate: 0.75,
    dry_run_completion_count: 2,
    live_session_completion_count: 1,
    most_common_dropoff_step: "commands",
    handoff_click_rate: 0.5,
    handoff_target_reach_rate: 0.25,
    first_post_setup_action_rate: 0.5,
    handoff_target_reached_counts: {},
    detour_started_counts: {},
    detour_returned_counts: {},
    ...overrides
  },
  recent_runs: []
})

describe("PersonaSetupAnalyticsCard", () => {
  it("hides when there are no recorded setup runs", () => {
    render(
      <PersonaSetupAnalyticsCard
        analytics={buildAnalytics({
          total_runs: 0,
          completed_runs: 0,
          completion_rate: 0,
          dry_run_completion_count: 0,
          live_session_completion_count: 0,
          most_common_dropoff_step: null,
          handoff_click_rate: 0,
          handoff_target_reach_rate: 0,
          first_post_setup_action_rate: 0
        })}
      />
    )

    expect(screen.queryByTestId("persona-setup-analytics-card")).not.toBeInTheDocument()
  })

  it("shows a compact loading state before analytics are available", () => {
    render(<PersonaSetupAnalyticsCard loading />)

    expect(screen.getByText("Loading setup analytics...")).toBeInTheDocument()
  })

  it("renders the compact setup funnel metrics", () => {
    render(<PersonaSetupAnalyticsCard analytics={buildAnalytics()} />)

    expect(screen.getByTestId("persona-setup-analytics-card")).toBeInTheDocument()
    expect(screen.getByText("Setup analytics")).toBeInTheDocument()
    expect(screen.getByText("Completion rate").parentElement).toHaveTextContent("75%")
    expect(screen.getByText("Most common drop-off").parentElement).toHaveTextContent(
      "Starter commands"
    )
    expect(screen.getByText("Dry run completions").parentElement).toHaveTextContent("2")
    expect(screen.getByText("Live session completions").parentElement).toHaveTextContent("1")
    expect(screen.getByText("Handoff click rate").parentElement).toHaveTextContent("50%")
    expect(screen.getByText("Target reached rate").parentElement).toHaveTextContent("25%")
    expect(screen.getByText("First next-step rate").parentElement).toHaveTextContent("50%")
  })

  it("falls back cleanly for missing and unknown drop-off steps", () => {
    const view = render(
      <PersonaSetupAnalyticsCard
        analytics={buildAnalytics({ most_common_dropoff_step: null })}
      />
    )

    expect(screen.getByText("Most common drop-off").parentElement).toHaveTextContent(
      "None yet"
    )

    view.rerender(
      <PersonaSetupAnalyticsCard
        analytics={buildAnalytics({ most_common_dropoff_step: "mystery_phase" as never })}
      />
    )

    expect(screen.getByText("Most common drop-off").parentElement).toHaveTextContent(
      "Mystery phase"
    )
  })
})
