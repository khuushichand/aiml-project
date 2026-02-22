import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import FeatureEmptyState from "../FeatureEmptyState"

vi.mock("antd", () => ({
  Button: ({ children, className, ...props }: any) => (
    <button className={className} {...props}>
      {children}
    </button>
  ),
}))

describe("FeatureEmptyState", () => {
  it("uses semantic surface/text token classes for container content", () => {
    const { container } = render(
      <FeatureEmptyState
        title="No items yet"
        description="Create your first item to continue."
      />
    )

    const root = container.firstElementChild
    expect(root).toBeTruthy()
    expect(root?.className).toContain("bg-surface/90")
    expect(root?.className).toContain("border-border/80")
    expect(root?.className).toContain("text-text")
  })

  it("applies focus-visible classes to empty-state action buttons", () => {
    render(
      <FeatureEmptyState
        title="No prompts"
        primaryActionLabel="Create prompt"
        secondaryActionLabel="Import prompt"
        onPrimaryAction={vi.fn()}
        onSecondaryAction={vi.fn()}
      />
    )

    const controls = [
      screen.getByRole("button", { name: "Create prompt" }),
      screen.getByRole("button", { name: "Import prompt" }),
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })
})
