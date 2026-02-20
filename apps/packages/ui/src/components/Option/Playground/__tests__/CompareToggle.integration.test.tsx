// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { CompareToggle } from "../CompareToggle"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/components/Common/ProviderIcon", () => ({
  ProviderIcons: ({
    provider,
    className
  }: {
    provider?: string
    className?: string
  }) => (
    <span
      data-testid={`provider-${provider || "custom"}`}
      className={className}
    />
  )
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Popover: ({
    children,
    content
  }: {
    children: React.ReactNode
    content: React.ReactNode
  }) => (
    <div>
      {children}
      <div>{content}</div>
    </div>
  ),
  Select: ({
    options,
    onChange,
    placeholder
  }: {
    options?: Array<{ value: string; label: string }>
    onChange?: (value: string) => void
    placeholder?: string
  }) => (
    <select
      aria-label={placeholder}
      defaultValue=""
      onChange={(event) => {
        if (!event.target.value) return
        onChange?.(event.target.value)
      }}
    >
      <option value="">--</option>
      {(options || []).map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}))

describe("CompareToggle activation and model constraints", () => {
  it("toggles compare mode from the main control", async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <CompareToggle
        featureEnabled
        active={false}
        onToggle={onToggle}
        selectedModels={[]}
        availableModels={[{ model: "model-a", nickname: "Model A" }]}
        maxModels={3}
        onAddModel={vi.fn()}
        onRemoveModel={vi.fn()}
      />
    )

    await user.click(screen.getByRole("button", { name: "Compare" }))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it("adds and removes models while respecting max-model constraints", async () => {
    const user = userEvent.setup()
    const onAddModel = vi.fn()
    const onRemoveModel = vi.fn()

    const { rerender } = render(
      <CompareToggle
        featureEnabled
        active
        onToggle={vi.fn()}
        selectedModels={["model-a"]}
        availableModels={[
          { model: "model-a", nickname: "Model A", provider: "openai" },
          { model: "model-b", nickname: "Model B", provider: "anthropic" },
          { model: "model-c", nickname: "Model C", provider: "google" }
        ]}
        maxModels={2}
        onAddModel={onAddModel}
        onRemoveModel={onRemoveModel}
      />
    )

    await user.selectOptions(screen.getByLabelText("Add a model..."), "model-b")
    expect(onAddModel).toHaveBeenCalledWith("model-b")

    await user.click(screen.getByRole("button", { name: "Remove" }))
    expect(onRemoveModel).toHaveBeenCalledWith("model-a")

    rerender(
      <CompareToggle
        featureEnabled
        active
        onToggle={vi.fn()}
        selectedModels={["model-a", "model-b"]}
        availableModels={[
          { model: "model-a", nickname: "Model A", provider: "openai" },
          { model: "model-b", nickname: "Model B", provider: "anthropic" },
          { model: "model-c", nickname: "Model C", provider: "google" }
        ]}
        maxModels={2}
        onAddModel={onAddModel}
        onRemoveModel={onRemoveModel}
      />
    )

    expect(screen.queryByLabelText("Add a model...")).not.toBeInTheDocument()
  })
})
