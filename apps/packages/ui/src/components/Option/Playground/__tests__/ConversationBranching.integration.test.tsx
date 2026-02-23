import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  BranchIndicator,
  ConversationBranching,
  QuickBranchButton
} from "../ConversationBranching"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Popover: ({
    children,
    content
  }: {
    children: React.ReactNode
    content?: React.ReactNode
  }) => (
    <>
      {children}
      {content}
    </>
  ),
  Modal: ({
    open,
    title,
    children
  }: {
    open?: boolean
    title?: React.ReactNode
    children?: React.ReactNode
  }) => (open ? <div>{title}{children}</div> : null),
  Radio: ({
    checked,
    onChange
  }: {
    checked?: boolean
    onChange?: () => void
  }) => (
    <input
      type="radio"
      checked={Boolean(checked)}
      onChange={() => onChange?.()}
    />
  )
}))

describe("ConversationBranching integration", () => {
  it("creates a fork from the selected message and respects include-response choice", () => {
    const onFork = vi.fn()

    render(
      <ConversationBranching
        messages={[
          {
            id: "u-1",
            role: "user",
            message: "Start from here",
            isBot: false
          },
          {
            id: "a-1",
            role: "assistant",
            message: "Assistant response",
            isBot: true
          },
          {
            id: "u-2",
            role: "user",
            message: "Alternative turn",
            isBot: false
          }
        ]}
        onBranch={vi.fn()}
        onFork={onFork}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Branch" }))

    const radios = screen.getAllByRole("radio")
    fireEvent.click(radios[0])

    const includeResponse = screen.getByRole("checkbox", {
      name: "Include the response that follows"
    })
    fireEvent.click(includeResponse)

    fireEvent.click(screen.getByRole("button", { name: "Create Branch" }))

    expect(onFork).toHaveBeenCalledWith(0, false)
  })

  it("invokes quick-branch action directly from message controls", () => {
    const onBranch = vi.fn()

    render(<QuickBranchButton messageIndex={3} onBranch={onBranch} />)

    fireEvent.click(screen.getByRole("button"))
    expect(onBranch).toHaveBeenCalledWith(3)
  })

  it("renders and activates the branch indicator when branches exist", () => {
    const onClick = vi.fn()
    render(<BranchIndicator branchCount={4} onClick={onClick} />)

    fireEvent.click(screen.getByRole("button"))
    expect(screen.getByText("4")).toBeInTheDocument()
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

