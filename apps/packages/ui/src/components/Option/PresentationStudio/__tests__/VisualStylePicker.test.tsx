import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { VisualStylePicker } from "../VisualStylePicker"

const styles = [
  {
    id: "minimal-academic",
    scope: "builtin",
    name: "Minimal Academic",
    description: "Structured, restrained, study-first slides.",
    category: "educational",
    guide_number: 1,
    tags: ["study", "notes"],
    best_for: ["exam prep", "course notes"],
    generation_rules: {},
    artifact_preferences: [],
    appearance_defaults: { theme: "white" },
    fallback_policy: {},
    version: 1
  },
  {
    id: "notebooklm-blueprint",
    scope: "builtin",
    name: "Blueprint",
    description: "Technical diagrams and systems breakdowns.",
    category: "technical",
    guide_number: 12,
    tags: ["architecture", "systems"],
    best_for: ["engineering review"],
    generation_rules: {},
    artifact_preferences: [],
    appearance_defaults: { theme: "night" },
    fallback_policy: {},
    version: 1
  },
  {
    id: "blueprint-lab",
    scope: "user",
    name: "Blueprint Lab",
    description: "A custom technical deck style.",
    generation_rules: {},
    artifact_preferences: [],
    appearance_defaults: { theme: "night" },
    fallback_policy: {},
    version: 2
  }
]

describe("VisualStylePicker", () => {
  it("groups, searches, and preserves selection for built-in and custom styles", () => {
    const onChange = vi.fn()

    render(
      <VisualStylePicker
        label="Visual style"
        value="builtin::minimal-academic"
        styles={styles as any}
        onChange={onChange}
      />
    )

    expect(screen.getByRole("searchbox", { name: "Search visual styles" })).toBeInTheDocument()
    expect(screen.getAllByRole("heading").map((node) => node.textContent)).toEqual([
      "Educational and Explainer",
      "Technical and Engineering",
      "Custom styles"
    ])
    expect(screen.getByText("Guide 1")).toBeInTheDocument()
    expect(screen.getAllByText("Best for")).toHaveLength(2)
    expect(
      screen.getByRole("button", { name: /Minimal Academic/ })
    ).toHaveAttribute("aria-pressed", "true")

    fireEvent.change(screen.getByRole("searchbox", { name: "Search visual styles" }), {
      target: { value: "blueprint" }
    })

    expect(screen.queryByRole("button", { name: /Minimal Academic/ })).toBeNull()
    expect(screen.getByText("Blueprint Lab")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /Blueprint Lab/ }))

    expect(onChange).toHaveBeenCalledWith("user::blueprint-lab")
    expect(screen.queryByRole("region", { name: "Educational and Explainer" })).toBeNull()
  })

  it("disables both the search box and style actions when disabled", () => {
    const onChange = vi.fn()

    render(
      <VisualStylePicker
        label="Visual style"
        value="builtin::minimal-academic"
        styles={styles as any}
        onChange={onChange}
        disabled
      />
    )

    expect(screen.getByRole("searchbox", { name: "Search visual styles" })).toBeDisabled()
    expect(screen.getByRole("button", { name: /Minimal Academic/ })).toBeDisabled()

    fireEvent.click(screen.getByRole("button", { name: /Blueprint Lab/ }))

    expect(onChange).not.toHaveBeenCalled()
  })
})
