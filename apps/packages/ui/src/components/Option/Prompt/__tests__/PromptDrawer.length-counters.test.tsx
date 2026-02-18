import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PromptDrawer } from "../PromptDrawer"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        if (fallbackOrOptions.defaultValue) {
          return Object.entries(fallbackOrOptions).reduce(
            (acc, [name, value]) =>
              name === "defaultValue"
                ? acc
                : acc.replace(new RegExp(`{{${name}}}`, "g"), String(value)),
            fallbackOrOptions.defaultValue
          )
        }
        return key
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useFormDraft", () => ({
  useFormDraft: () => ({
    hasDraft: false,
    draftData: null,
    saveDraft: vi.fn(),
    clearDraft: vi.fn(),
    applyDraft: vi.fn(),
    dismissDraft: vi.fn()
  }),
  formatDraftAge: () => "now"
}))

vi.mock("../Studio/Prompts/VersionHistoryDrawer", () => ({
  VersionHistoryDrawer: () => null
}))

describe("PromptDrawer length counters", () => {
  const baseProps = {
    open: true,
    onClose: vi.fn(),
    mode: "create" as const,
    onSubmit: vi.fn(),
    isLoading: false,
    allTags: []
  }

  it("shows initial char/token counters for system and user fields", async () => {
    render(<PromptDrawer {...baseProps} />)

    expect(await screen.findByTestId("prompt-drawer-system-counter")).toHaveTextContent(
      "0 chars / ~0 tokens"
    )
    expect(screen.getByTestId("prompt-drawer-user-counter")).toHaveTextContent(
      "0 chars / ~0 tokens"
    )
  })

  it("updates counters live and shows warning/danger budget states", async () => {
    render(<PromptDrawer {...baseProps} />)

    fireEvent.change(screen.getByTestId("prompt-drawer-system"), {
      target: { value: "a".repeat(5000) }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-user"), {
      target: { value: "b".repeat(9000) }
    })

    await waitFor(() => {
      expect(screen.getByTestId("prompt-drawer-system-counter")).toHaveTextContent(
        "5,000 chars / ~1,250 tokens"
      )
    })
    expect(screen.getByTestId("prompt-drawer-system-counter")).toHaveTextContent(
      "Approaching high token load"
    )
    expect(screen.getByTestId("prompt-drawer-user-counter")).toHaveTextContent(
      "9,000 chars / ~2,250 tokens"
    )
    expect(screen.getByTestId("prompt-drawer-user-counter")).toHaveTextContent(
      "High token load"
    )
  })
})
