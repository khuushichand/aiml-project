import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TokenProgressBar } from "../TokenProgressBar"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

describe("TokenProgressBar", () => {
  it("invokes onClick when interactive", () => {
    const onClick = vi.fn()

    render(
      <TokenProgressBar
        conversationTokens={1200}
        draftTokens={80}
        maxTokens={4096}
        modelLabel="Test model"
        onClick={onClick}
      />
    )

    fireEvent.click(
      screen.getByRole("button", { name: "Configure context window size" })
    )

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("renders a non-interactive indicator when no click handler is provided", () => {
    render(
      <TokenProgressBar
        conversationTokens={1200}
        draftTokens={80}
        maxTokens={4096}
        modelLabel="Test model"
      />
    )

    expect(
      screen.queryByRole("button", { name: "Configure context window size" })
    ).toBeNull()
    expect(screen.getByText(/used/i)).toBeInTheDocument()
  })
})
