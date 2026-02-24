// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { WatchlistsHelpTooltip } from "../WatchlistsHelpTooltip"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: unknown, options?: Record<string, unknown>) => {
      if (typeof defaultValue === "string" && options?.topic) {
        return defaultValue.replace("{{topic}}", String(options.topic))
      }
      if (typeof defaultValue === "string") return defaultValue
      return key
    }
  })
}))

vi.mock("antd", () => ({
  Button: ({ children, icon, ...rest }: any) => (
    <button type="button" {...rest}>
      {icon}
      {children}
    </button>
  ),
  Tooltip: ({ title, children }: any) => (
    <div>
      {children}
      <div data-testid="tooltip-content">{title}</div>
    </div>
  )
}))

describe("WatchlistsHelpTooltip", () => {
  it("renders help tooltip content snapshots for all configured topics", () => {
    const { container } = render(
      <div>
        <WatchlistsHelpTooltip topic="opml" />
        <WatchlistsHelpTooltip topic="cron" />
        <WatchlistsHelpTooltip topic="ttl" />
        <WatchlistsHelpTooltip topic="jinja2" />
        <WatchlistsHelpTooltip topic="claimClusters" />
      </div>
    )

    expect(container).toMatchSnapshot()
  })

  it("uses keyboard-focusable, screen-reader discoverable triggers", () => {
    render(<WatchlistsHelpTooltip topic="cron" />)
    const trigger = screen.getByRole("button", {
      name: "Open help for advanced schedule timing"
    })
    trigger.focus()
    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute("aria-label", "Open help for advanced schedule timing")
    expect(screen.getByRole("link", { name: "Learn more" })).toHaveAttribute(
      "href",
      "https://crontab.guru/"
    )
  })
})
