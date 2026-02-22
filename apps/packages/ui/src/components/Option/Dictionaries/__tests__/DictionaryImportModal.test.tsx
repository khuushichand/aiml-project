import React from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Modal } from "antd"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { DictionaryImportModal } from "../components/DictionaryImportModal"

if (typeof window.ResizeObserver === "undefined") {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(window as any).ResizeObserver = ResizeObserverMock
  ;(globalThis as any).ResizeObserver = ResizeObserverMock
}

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false
    })
  })
}

const previewPayload = {
  format: "json" as const,
  payload: {
    kind: "json" as const,
    data: {
      name: "Clinical Terms",
      entries: [{ pattern: "BP", replacement: "blood pressure" }]
    }
  },
  summary: {
    name: "Clinical Terms",
    entryCount: 1,
    groups: ["medical"],
    hasAdvancedFields: false
  }
}

describe("DictionaryImportModal", () => {
  afterEach(() => {
    Modal.destroyAll()
  })

  it("handles paste-mode preview interactions", async () => {
    const user = userEvent.setup()
    const onImportSourceContentChange = vi.fn()
    const onBuildImportPreview = vi.fn()
    const onConfirmImport = vi.fn()

    render(
      <DictionaryImportModal
        open
        onCancel={vi.fn()}
        importFormat="json"
        onImportFormatChange={vi.fn()}
        importMode="paste"
        onImportModeChange={vi.fn()}
        importSourceContent='{"name":"Clinical Terms","entries":[]}'
        onImportSourceContentChange={onImportSourceContentChange}
        importMarkdownName=""
        onImportMarkdownNameChange={vi.fn()}
        importFileName={null}
        onImportFileSelection={vi.fn()}
        activateOnImport={false}
        onActivateOnImportChange={vi.fn()}
        onBuildImportPreview={onBuildImportPreview}
        importValidationErrors={[]}
        importPreview={previewPayload}
        onConfirmImport={onConfirmImport}
        importing={false}
        importConflictResolution={null}
        onCloseConflictResolution={vi.fn()}
        onResolveConflictRename={vi.fn()}
        onResolveConflictReplace={vi.fn()}
      />
    )

    await user.type(
      screen.getByPlaceholderText("Paste JSON dictionary content..."),
      " "
    )
    expect(onImportSourceContentChange).toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Preview import" }))
    expect(onBuildImportPreview).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole("button", { name: "Confirm import" }))
    expect(onConfirmImport).toHaveBeenCalledTimes(1)
    expect(screen.getByText("Clinical Terms")).toBeInTheDocument()
  })

  it("routes conflict resolution actions", async () => {
    const user = userEvent.setup()
    const onCloseConflictResolution = vi.fn()
    const onResolveConflictRename = vi.fn()
    const onResolveConflictReplace = vi.fn()

    render(
      <DictionaryImportModal
        open={false}
        onCancel={vi.fn()}
        importFormat="json"
        onImportFormatChange={vi.fn()}
        importMode="file"
        onImportModeChange={vi.fn()}
        importSourceContent=""
        onImportSourceContentChange={vi.fn()}
        importMarkdownName=""
        onImportMarkdownNameChange={vi.fn()}
        importFileName={null}
        onImportFileSelection={vi.fn()}
        activateOnImport={false}
        onActivateOnImportChange={vi.fn()}
        onBuildImportPreview={vi.fn()}
        importValidationErrors={[]}
        importPreview={null}
        onConfirmImport={vi.fn()}
        importing={false}
        importConflictResolution={{
          preview: previewPayload,
          suggestedName: "Clinical Terms (2)"
        }}
        onCloseConflictResolution={onCloseConflictResolution}
        onResolveConflictRename={onResolveConflictRename}
        onResolveConflictReplace={onResolveConflictReplace}
      />
    )

    await user.click(screen.getByRole("button", { name: 'Rename to "Clinical Terms (2)"' }))
    expect(onResolveConflictRename).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole("button", { name: "Replace existing" }))
    expect(onResolveConflictReplace).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(onCloseConflictResolution).toHaveBeenCalledTimes(1)
  })
})
