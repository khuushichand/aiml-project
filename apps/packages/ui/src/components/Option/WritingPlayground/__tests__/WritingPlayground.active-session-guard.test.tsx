import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { WritingPlaygroundActiveSessionGuard } from "../WritingPlaygroundActiveSessionGuard"

const t = (key: string, defaultValue: string) => defaultValue || key

describe("WritingPlaygroundActiveSessionGuard", () => {
  it("renders the empty state when there is no active session", () => {
    render(
      <WritingPlaygroundActiveSessionGuard
        hasActiveSession={false}
        isLoading={false}
        hasError={false}
        t={t}>
        <div>ready content</div>
      </WritingPlaygroundActiveSessionGuard>
    )

    expect(
      screen.getByText("Select a session to edit settings.")
    ).toBeInTheDocument()
  })

  it("renders a loading skeleton when the active session is loading", () => {
    const { container } = render(
      <WritingPlaygroundActiveSessionGuard
        hasActiveSession
        isLoading
        hasError={false}
        t={t}>
        <div>ready content</div>
      </WritingPlaygroundActiveSessionGuard>
    )

    expect(container.querySelector(".ant-skeleton")).not.toBeNull()
  })

  it("renders the error state when the active session fails to load", () => {
    render(
      <WritingPlaygroundActiveSessionGuard
        hasActiveSession
        isLoading={false}
        hasError
        t={t}>
        <div>ready content</div>
      </WritingPlaygroundActiveSessionGuard>
    )

    expect(
      screen.getByText("Unable to load session settings.")
    ).toBeInTheDocument()
  })

  it("renders children when the active session is ready", () => {
    render(
      <WritingPlaygroundActiveSessionGuard
        hasActiveSession
        isLoading={false}
        hasError={false}
        t={t}>
        <div>ready content</div>
      </WritingPlaygroundActiveSessionGuard>
    )

    expect(screen.getByText("ready content")).toBeInTheDocument()
  })
})
