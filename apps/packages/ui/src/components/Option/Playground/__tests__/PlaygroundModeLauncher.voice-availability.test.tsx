// @vitest-environment jsdom
import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { PlaygroundModeLauncher } from "../PlaygroundModeLauncher"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

vi.mock("antd", () => ({
  Popover: ({
    content,
    children
  }: {
    content: React.ReactNode
    children: React.ReactNode
  }) => (
    <div data-testid="popover">
      {children}
      {content}
    </div>
  )
}))

vi.mock("@/components/Common/Button", () => ({
  Button: ({
    children,
    ariaLabel,
    title,
    className,
    ...props
  }: {
    children: React.ReactNode
    ariaLabel?: string
    title?: string
    className?: string
    [key: string]: unknown
  }) => (
    <button
      type="button"
      aria-label={ariaLabel}
      title={title}
      className={className}
      {...props}
    >
      {children}
    </button>
  )
}))

describe("PlaygroundModeLauncher voice availability", () => {
  it("keeps Voice mode visible and disabled with the shared unavailable reason", () => {
    const reason = "This server does not advertise voice conversation streaming."
    const props = {
      open: true,
      onOpenChange: vi.fn(),
      compareModeActive: false,
      compareFeatureEnabled: true,
      onToggleCompare: vi.fn(),
      selectedCharacterName: null,
      onOpenActorSettings: vi.fn(),
      contextToolsOpen: false,
      onToggleKnowledgePanel: vi.fn(),
      voiceChatEnabled: false,
      voiceChatAvailable: false,
      isSending: false,
      onVoiceChatToggle: vi.fn(),
      webSearch: false,
      hasWebSearch: false,
      onToggleWebSearch: vi.fn(),
      onModeAnnouncement: vi.fn(),
      t: (key: string, fallback?: string) => fallback || key,
      voiceChatUnavailableReason: reason
    } satisfies React.ComponentProps<typeof PlaygroundModeLauncher> & {
      voiceChatUnavailableReason: string
    }

    render(<PlaygroundModeLauncher {...props} />)

    const voiceModeButton = screen.getByRole("button", {
      name: /Voice mode/i
    })

    expect(voiceModeButton).toBeDisabled()
    expect(voiceModeButton).toHaveAttribute("title", reason)
  })
})
