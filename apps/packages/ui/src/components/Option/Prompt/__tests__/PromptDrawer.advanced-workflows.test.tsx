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
  VersionHistoryDrawer: ({ open, promptId }: { open: boolean; promptId: number | null }) =>
    open ? <div data-testid="mock-version-history">{promptId}</div> : null
}))

describe("PromptDrawer advanced workflows", () => {
  const baseProps = {
    open: true,
    onClose: vi.fn(),
    mode: "create" as const,
    onSubmit: vi.fn(),
    isLoading: false,
    allTags: []
  }

  it(
    "supports inline few-shot add/reorder/remove and submits normalized payload",
    async () => {
    const onSubmit = vi.fn()
    render(<PromptDrawer {...baseProps} onSubmit={onSubmit} />)

    fireEvent.click(screen.getByText("Advanced"))

    const addButton = await screen.findByTestId("prompt-drawer-few-shot-add")
    fireEvent.click(addButton)
    fireEvent.click(addButton)

    fireEvent.change(await screen.findByTestId("prompt-drawer-few-shot-input-0"), {
      target: { value: "A input" }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-few-shot-output-0"), {
      target: { value: "A output" }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-few-shot-input-1"), {
      target: { value: "B input" }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-few-shot-output-1"), {
      target: { value: "B output" }
    })

    fireEvent.click(screen.getByTestId("prompt-drawer-few-shot-move-up-1"))
    fireEvent.click(screen.getByTestId("prompt-drawer-few-shot-remove-1"))

    fireEvent.change(screen.getByTestId("prompt-drawer-name"), {
      target: { value: "Few-shot test prompt" }
    })
    fireEvent.change(screen.getByTestId("prompt-drawer-user"), {
      target: { value: "Use this template for quick drafting." }
    })
    const form = document.querySelector("form")
    expect(form).not.toBeNull()
    fireEvent.submit(form as HTMLFormElement)

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        fewShotExamples: [
          {
            inputs: { input: "B input" },
            outputs: { output: "B output" }
          }
        ]
      })
    )
    },
    10000
  )

  it("shows view history for synced prompts and opens the shared history drawer", async () => {
    render(
      <PromptDrawer
        {...baseProps}
        mode="edit"
        initialValues={{
          name: "Synced prompt",
          serverId: 42,
          versionNumber: 3
        }}
      />
    )

    fireEvent.click(screen.getByText("Advanced"))
    const viewHistoryButton = await screen.findByTestId("prompt-drawer-view-history")
    fireEvent.click(viewHistoryButton)

    expect(await screen.findByTestId("mock-version-history")).toHaveTextContent("42")
  })

  it("hides view history action for prompts without a server link", async () => {
    render(
      <PromptDrawer
        {...baseProps}
        mode="edit"
        initialValues={{
          name: "Local prompt",
          versionNumber: 3
        }}
      />
    )

    fireEvent.click(screen.getByText("Advanced"))
    await screen.findByText("Version 3")
    expect(screen.queryByTestId("prompt-drawer-view-history")).not.toBeInTheDocument()
  })
})
