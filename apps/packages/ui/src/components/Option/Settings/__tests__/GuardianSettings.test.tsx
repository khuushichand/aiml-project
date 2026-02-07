import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest"

import { GuardianSettings } from "../GuardianSettings"

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

describe("GuardianSettings", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn()
      }))
    })
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  it("does not offer warn as a self-monitoring rule action", async () => {
    render(<GuardianSettings />)

    fireEvent.click(screen.getByRole("button", { name: /Create Rule/i }))

    const dialog = await screen.findByRole("dialog")
    const actionLabel = within(dialog).getByText("Action")
    const actionFormItem = actionLabel.closest(".ant-form-item")
    expect(actionFormItem).not.toBeNull()

    const actionSelector = actionFormItem?.querySelector(".ant-select-selector")
    expect(actionSelector).not.toBeNull()
    fireEvent.mouseDown(actionSelector as Element)

    await waitFor(() => {
      expect(document.querySelector('.ant-select-item-option[title="Notify"]')).toBeInTheDocument()
      expect(document.querySelector('.ant-select-item-option[title="Redact"]')).toBeInTheDocument()
      expect(document.querySelector('.ant-select-item-option[title="Block"]')).toBeInTheDocument()
    })

    expect(document.querySelector('.ant-select-item-option[title="Warn"]')).toBeNull()
  })
})
