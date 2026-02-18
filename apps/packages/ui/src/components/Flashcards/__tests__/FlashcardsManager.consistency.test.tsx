import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { FlashcardsManager } from "../FlashcardsManager"

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
      if (defaultValueOrOptions?.defaultValue) {
        return defaultValueOrOptions.defaultValue.replace(
          /\{\{(\w+)\}\}/g,
          (_match, token: string) =>
            String((defaultValueOrOptions as Record<string, unknown>)[token] ?? `{{${token}}}`)
        )
      }
      return key
    }
  })
}))

vi.mock("../tabs", () => ({
  ReviewTab: (props: { onNavigateToCreate: () => void }) => (
    <div data-testid="mock-review-tab">
      <button onClick={props.onNavigateToCreate}>Route Create</button>
    </div>
  ),
  ManageTab: (props: {
    onNavigateToImport: () => void
    openCreateSignal?: number
  }) => (
    <div data-testid="mock-manage-tab">
      <button onClick={props.onNavigateToImport}>Route Import</button>
      <span data-testid="mock-open-create-signal">{String(props.openCreateSignal ?? 0)}</span>
    </div>
  ),
  ImportExportTab: () => <div data-testid="mock-transfer-tab">Transfer panel</div>
}))

vi.mock("../components", () => ({
  KeyboardShortcutsModal: () => null
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("FlashcardsManager consistency standards", () => {
  it("uses Study/Manage/Transfer tab labels", () => {
    render(<FlashcardsManager />)

    expect(screen.getByText("Study")).toBeInTheDocument()
    expect(screen.getByText("Manage")).toBeInTheDocument()
    expect(screen.getByText("Transfer")).toBeInTheDocument()
  })

  it("routes secondary create CTA to the Manage tab create entry point", () => {
    render(<FlashcardsManager />)

    fireEvent.click(screen.getByText("Route Create"))
    expect(screen.getByTestId("mock-manage-tab")).toBeInTheDocument()
    expect(screen.getByTestId("mock-open-create-signal")).toHaveTextContent("1")
  })
})
