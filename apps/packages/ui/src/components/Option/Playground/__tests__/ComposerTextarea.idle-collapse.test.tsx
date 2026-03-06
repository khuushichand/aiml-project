import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ComposerTextarea } from "../ComposerTextarea"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

const createProps = (overrides: Record<string, unknown> = {}) => ({
  textareaRef: { current: null } as React.RefObject<HTMLTextAreaElement | null>,
  value: "",
  displayValue: "",
  onChange: vi.fn(),
  onKeyDown: vi.fn(),
  onPaste: vi.fn(),
  onFocus: vi.fn(),
  onSelect: vi.fn(),
  onCompositionStart: vi.fn(),
  onCompositionEnd: vi.fn(),
  onMouseDown: vi.fn(),
  onMouseUp: vi.fn(),
  placeholder: "Type a message...",
  isProMode: true,
  isMobile: false,
  isConnectionReady: true,
  isCollapsed: false,
  ariaExpanded: true,
  formInputProps: {},
  showSlashMenu: false,
  slashCommands: [],
  slashActiveIndex: 0,
  onSlashSelect: vi.fn(),
  onSlashActiveIndexChange: vi.fn(),
  slashEmptyLabel: "No results found",
  showMentions: false,
  filteredTabs: [],
  mentionPosition: null,
  onMentionSelect: vi.fn(),
  onMentionsClose: vi.fn(),
  onMentionRefetch: vi.fn(async () => undefined),
  onMentionsOpen: vi.fn(async () => undefined),
  draftSaved: false,
  ...overrides
})

describe("ComposerTextarea idle collapse", () => {
  it("uses a compact min-height when idle-collapsed", () => {
    render(<ComposerTextarea {...(createProps({ compactWhenInactive: true }) as any)} />)

    const textarea = screen.getByTestId("chat-input")
    expect(textarea).toHaveStyle({ minHeight: "44px" })
  })
})
