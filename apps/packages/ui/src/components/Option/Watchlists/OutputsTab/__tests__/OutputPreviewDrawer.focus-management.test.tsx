// @vitest-environment jsdom

import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { OutputPreviewDrawer } from "../OutputPreviewDrawer"
import type { WatchlistOutput } from "@/types/watchlists"

const serviceMocks = vi.hoisted(() => ({
  downloadWatchlistOutput: vi.fn(),
  downloadWatchlistOutputBinary: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        typeof fallbackOrOptions.defaultValue === "string"
      ) {
        return fallbackOrOptions.defaultValue
      }
      return key
    }
  })
}))

vi.mock("antd", () => {
  const Drawer = ({ open, title, extra, children, onClose, afterOpenChange }: any) => {
    const closeRef = React.useRef<HTMLButtonElement | null>(null)
    React.useEffect(() => {
      afterOpenChange?.(open)
      if (open) {
        closeRef.current?.focus()
      }
    }, [afterOpenChange, open])

    if (!open) return null
    return (
      <div>
        <div>{title}</div>
        {extra}
        <button type="button" ref={closeRef} onClick={() => onClose?.()}>
          Close drawer
        </button>
        {children}
      </div>
    )
  }

  const Button = ({ children, onClick, disabled }: any) => (
    <button type="button" disabled={Boolean(disabled)} onClick={() => onClick?.()}>
      {children}
    </button>
  )

  return {
    Button,
    Drawer,
    Empty: ({ description }: any) => <div>{description}</div>,
    Segmented: () => null,
    Spin: () => <div>Loading</div>,
    Tag: ({ children }: any) => <span>{children}</span>,
    Tooltip: ({ children }: any) => <>{children}</>,
    message: {
      success: vi.fn(),
      error: vi.fn()
    }
  }
})

vi.mock("@/services/watchlists", () => ({
  downloadWatchlistOutput: (...args: unknown[]) =>
    serviceMocks.downloadWatchlistOutput(...args),
  downloadWatchlistOutputBinary: (...args: unknown[]) =>
    serviceMocks.downloadWatchlistOutputBinary(...args)
}))

const buildOutput = (overrides: Partial<WatchlistOutput> = {}): WatchlistOutput => ({
  id: 77,
  run_id: 3,
  job_id: 2,
  type: "briefing",
  format: "md",
  title: "Morning Brief",
  content: null,
  storage_path: "watchlists/morning-brief.md",
  metadata: {},
  media_item_id: null,
  chatbook_path: null,
  version: 1,
  expires_at: null,
  expired: false,
  created_at: "2026-02-23T00:00:00Z",
  ...overrides
})

describe("OutputPreviewDrawer focus management", () => {
  it("restores focus to the launch control after the drawer closes", async () => {
    serviceMocks.downloadWatchlistOutput.mockResolvedValue("# Morning brief")
    serviceMocks.downloadWatchlistOutputBinary.mockResolvedValue(new ArrayBuffer(0))

    const trigger = document.createElement("button")
    trigger.type = "button"
    trigger.textContent = "Open output preview"
    document.body.appendChild(trigger)
    trigger.focus()

    const { rerender } = render(
      <OutputPreviewDrawer
        open
        output={buildOutput()}
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Close drawer" })).toHaveFocus()
    })

    rerender(
      <OutputPreviewDrawer
        open={false}
        output={buildOutput()}
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(trigger).toHaveFocus()
    })

    trigger.remove()
  })
})

