// @vitest-environment jsdom

import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { OutputPreviewDrawer } from "../OutputsTab/OutputPreviewDrawer"
import type { WatchlistOutput } from "@/types/watchlists"

/* ------------------------------------------------------------------ */
/*  Hoisted mocks                                                      */
/* ------------------------------------------------------------------ */

const serviceMocks = vi.hoisted(() => ({
  downloadWatchlistOutput: vi.fn(),
  downloadWatchlistOutputBinary: vi.fn()
}))

const settingsMocks = vi.hoisted(() => ({
  setSetting: vi.fn()
}))

const navigateMock = vi.hoisted(() => vi.fn())

/* ------------------------------------------------------------------ */
/*  Module mocks                                                       */
/* ------------------------------------------------------------------ */

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      values?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        if (!values) return fallbackOrOptions
        return fallbackOrOptions.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
          const value = values[token]
          return value == null ? "" : String(value)
        })
      }
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

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock
}))

vi.mock("@/services/watchlists", () => ({
  downloadWatchlistOutput: (...args: unknown[]) =>
    serviceMocks.downloadWatchlistOutput(...args),
  downloadWatchlistOutputBinary: (...args: unknown[]) =>
    serviceMocks.downloadWatchlistOutputBinary(...args)
}))

vi.mock("@/services/settings", () => ({
  setSetting: (...args: unknown[]) => settingsMocks.setSetting(...args)
}))

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const buildOutput = (overrides: Partial<WatchlistOutput> = {}): WatchlistOutput => ({
  id: 42,
  run_id: 9,
  job_id: 7,
  type: "briefing",
  format: "md",
  title: "Daily Brief",
  content: null,
  storage_path: "watchlists/brief-42.md",
  metadata: {},
  media_item_id: null,
  chatbook_path: null,
  version: 1,
  expires_at: null,
  expired: false,
  created_at: "2026-02-20T00:00:00Z",
  ...overrides
})

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("OutputPreviewDrawer chat handoff", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    serviceMocks.downloadWatchlistOutput.mockResolvedValue("# Briefing content")
    serviceMocks.downloadWatchlistOutputBinary.mockResolvedValue(new ArrayBuffer(0))
    settingsMocks.setSetting.mockResolvedValue(undefined)
  })

  it("shows Chat button in drawer header when content is loaded", async () => {
    render(
      <OutputPreviewDrawer
        open
        onClose={vi.fn()}
        output={buildOutput()}
      />
    )

    await waitFor(() => {
      expect(serviceMocks.downloadWatchlistOutput).toHaveBeenCalledWith(42)
    })

    const chatBtn = await screen.findByTestId("watchlists-output-chat-about")
    expect(chatBtn).toBeInTheDocument()
    expect(chatBtn).not.toBeDisabled()
  })

  it("disables Chat button when content is not loaded", async () => {
    // Make download hang so content never loads
    serviceMocks.downloadWatchlistOutput.mockReturnValue(new Promise(() => {}))

    render(
      <OutputPreviewDrawer
        open
        onClose={vi.fn()}
        output={buildOutput()}
      />
    )

    const chatBtn = await screen.findByTestId("watchlists-output-chat-about")
    expect(chatBtn).toBeDisabled()
  })

  it("stores handoff payload and navigates to root on click", async () => {
    const output = buildOutput({ title: "My Report", media_item_id: 55 })

    render(
      <OutputPreviewDrawer
        open
        onClose={vi.fn()}
        output={output}
      />
    )

    // Wait for content to load
    await waitFor(() => {
      expect(serviceMocks.downloadWatchlistOutput).toHaveBeenCalledWith(42)
    })

    const chatBtn = await screen.findByTestId("watchlists-output-chat-about")
    expect(chatBtn).not.toBeDisabled()

    await userEvent.click(chatBtn)

    // Verify setSetting was called with the handoff payload
    expect(settingsMocks.setSetting).toHaveBeenCalledTimes(1)
    const [settingKey, payload] = settingsMocks.setSetting.mock.calls[0]
    expect(settingKey).toBeDefined()
    expect(payload).toMatchObject({
      articles: [
        {
          title: "My Report",
          content: "# Briefing content",
          sourceType: "output",
          mediaId: 55
        }
      ]
    })

    // Verify navigation to root
    expect(navigateMock).toHaveBeenCalledWith("/")
  })
})
