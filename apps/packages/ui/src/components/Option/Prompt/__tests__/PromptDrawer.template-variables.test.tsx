import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
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

describe("PromptDrawer template variable UX", () => {
  const baseProps = {
    open: true,
    onClose: vi.fn(),
    mode: "create" as const,
    onSubmit: vi.fn(),
    isLoading: false,
    allTags: []
  }

  it("renders extracted variable chips and highlighted previews", async () => {
    render(<PromptDrawer {...baseProps} />)

    fireEvent.change(screen.getByTestId("prompt-drawer-system"), {
      target: { value: "You are {{assistant_name}} helping {{user_name}}." }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-user"), {
      target: { value: "Answer about {{topic}} and {{topic}} in detail." }
    })

    const systemVars = await screen.findByTestId("prompt-drawer-system-vars")
    expect(within(systemVars).getByText("{{assistant_name}}")).toBeInTheDocument()
    expect(within(systemVars).getByText("{{user_name}}")).toBeInTheDocument()

    const userVars = screen.getByTestId("prompt-drawer-user-vars")
    expect(within(userVars).getByText("{{topic}}")).toBeInTheDocument()
    expect(within(userVars).queryAllByText("{{topic}}")).toHaveLength(1)

    expect(screen.getByTestId("prompt-drawer-system-preview")).toHaveTextContent(
      "{{assistant_name}}"
    )
    expect(screen.getByTestId("prompt-drawer-user-preview")).toHaveTextContent(
      "{{topic}}"
    )
  }, 15000)

  it("blocks submit on invalid template syntax and allows valid template references", async () => {
    const onSubmit = vi.fn()
    render(<PromptDrawer {...baseProps} onSubmit={onSubmit} />)

    fireEvent.change(screen.getByTestId("prompt-drawer-name"), {
      target: { value: "Template prompt" }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-system"), {
      target: { value: "Invalid variable {{bad-name}}" }
    })

    fireEvent.click(
      screen.getByRole("button", { name: "managePrompts.form.btnSave.save" })
    )

    expect(onSubmit).not.toHaveBeenCalled()
    await waitFor(() => {
      expect(
        screen
          .getByTestId("prompt-drawer-system")
          .closest(".ant-form-item")
      ).toHaveClass("ant-form-item-has-error")
    })

    fireEvent.change(screen.getByTestId("prompt-drawer-system"), {
      target: { value: "Valid variable {{good_name}}" }
    })

    fireEvent.click(
      screen.getByRole("button", { name: "managePrompts.form.btnSave.save" })
    )

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
  }, 15000)
})
