// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

const mocks = vi.hoisted(() => ({
  hasResumableSidepanelChat: vi.fn<() => Promise<boolean>>()
}))

vi.mock("../sidepanel-chat", () => ({
  __esModule: true,
  default: () => <div data-testid="sidepanel-chat-root">chat</div>
}))

vi.mock("../sidepanel-chat-resume", () => ({
  hasResumableSidepanelChat: () => mocks.hasResumableSidepanelChat()
}))

vi.mock("@/components/Common/PageAssistLoader", () => ({
  PageAssistLoader: ({ label }: { label?: string }) => (
    <div data-testid="page-assist-loader">{label || "loading"}</div>
  )
}))

vi.mock("../sidepanel-companion", () => ({
  __esModule: true,
  default: () => <div data-testid="sidepanel-companion-root">companion</div>
}))

import SidepanelHomeResolver from "../sidepanel-home-resolver"

describe("SidepanelHomeResolver", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders chat from sidepanel / when resumable chat exists", async () => {
    mocks.hasResumableSidepanelChat.mockResolvedValueOnce(true)

    render(
      <MemoryRouter>
        <SidepanelHomeResolver />
      </MemoryRouter>
    )

    expect(await screen.findByTestId("sidepanel-chat-root")).toBeInTheDocument()
  })

  it("renders Companion Home from sidepanel / when no resumable chat exists", async () => {
    mocks.hasResumableSidepanelChat.mockResolvedValueOnce(false)

    render(
      <MemoryRouter>
        <SidepanelHomeResolver />
      </MemoryRouter>
    )

    expect(await screen.findByTestId("sidepanel-companion-root")).toBeInTheDocument()
  })

  it("renders chat immediately when the route forces chat view", async () => {
    render(
      <MemoryRouter initialEntries={["/?view=chat"]}>
        <SidepanelHomeResolver />
      </MemoryRouter>
    )

    expect(await screen.findByTestId("sidepanel-chat-root")).toBeInTheDocument()
    expect(mocks.hasResumableSidepanelChat).not.toHaveBeenCalled()
  })

  it("renders Companion Home immediately when the route forces companion view", async () => {
    render(
      <MemoryRouter initialEntries={["/?view=companion"]}>
        <SidepanelHomeResolver />
      </MemoryRouter>
    )

    expect(await screen.findByTestId("sidepanel-companion-root")).toBeInTheDocument()
    expect(mocks.hasResumableSidepanelChat).not.toHaveBeenCalled()
  })
})
