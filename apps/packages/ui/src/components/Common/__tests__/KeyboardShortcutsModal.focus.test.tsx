import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { KeyboardShortcutsModal } from "../KeyboardShortcutsModal"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key
  })
}))

vi.mock("@/hooks/keyboard/useShortcutConfig", () => ({
  defaultShortcuts: {
    focusTextarea: { key: "Escape", shiftKey: true },
    newChat: { key: "u", ctrlKey: true, shiftKey: true },
    toggleSidebar: { key: "b", ctrlKey: true },
    toggleChatMode: { key: "e", ctrlKey: true },
    toggleWebSearch: { key: "w", altKey: true },
    toggleQuickChatHelper: { key: "h", ctrlKey: true, shiftKey: true },
    modePlayground: { key: "1", altKey: true },
    modeMedia: { key: "3", altKey: true },
    modeKnowledge: { key: "4", altKey: true },
    modeNotes: { key: "5", altKey: true },
    modePrompts: { key: "6", altKey: true },
    modeFlashcards: { key: "7", altKey: true }
  },
  formatShortcut: ({ key }: { key: string }) => key
}))

vi.mock("@/hooks/keyboard/useKeyboardShortcuts", () => ({
  isMac: false
}))

describe("KeyboardShortcutsModal focus styling", () => {
  it("applies focus-visible classes to the close button in modal context", async () => {
    render(<KeyboardShortcutsModal />)
    window.dispatchEvent(new CustomEvent("tldw:open-shortcuts-modal"))

    const closeButton = await screen.findByRole("button", { name: "Close" })
    expect(closeButton.className).toContain("focus-visible:outline")
    expect(closeButton.className).toContain("focus-visible:outline-2")
    expect(closeButton.className).toContain("focus-visible:outline-focus")
  })
})
