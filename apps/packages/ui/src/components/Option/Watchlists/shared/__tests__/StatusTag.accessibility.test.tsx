import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { StatusTag } from "../StatusTag"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown, options?: Record<string, unknown>) => {
      if (typeof defaultValue !== "string") return _key
      if (!options) return defaultValue
      return defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options[token] ?? ""))
    }
  })
}))

vi.mock("antd", () => ({
  Tag: ({ children, ...rest }: any) => <span {...rest}>{children}</span>
}))

describe("StatusTag accessibility labels", () => {
  it("exposes a descriptive SR label for known run statuses", () => {
    render(<StatusTag status="running" />)
    expect(screen.getByLabelText("Run status: Running")).toHaveTextContent("Running")
    expect(screen.getByTestId("watchlists-status-icon-running")).toBeInTheDocument()
  })

  it("humanizes unknown statuses and keeps descriptive SR labels", () => {
    render(<StatusTag status="in_progress" />)
    expect(screen.getByLabelText("Run status: In Progress")).toHaveTextContent("In Progress")
    expect(screen.getByTestId("watchlists-status-icon-unknown")).toBeInTheDocument()
  })
})
