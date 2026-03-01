// @vitest-environment jsdom

import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { JobPreviewModal } from "../JobPreviewModal"

const mocks = vi.hoisted(() => ({
  previewWatchlistJobMock: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown, options?: Record<string, unknown>) => {
      if (typeof defaultValue !== "string") return _key
      if (!options) return defaultValue
      return defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options[token] ?? ""))
    }
  })
}))

vi.mock("@/services/watchlists", () => ({
  previewWatchlistJob: (...args: unknown[]) => mocks.previewWatchlistJobMock(...args)
}))

vi.mock("antd", () => {
  const Modal = ({ open, title, children, onCancel }: any) => {
    const closeRef = React.useRef<HTMLButtonElement | null>(null)

    React.useEffect(() => {
      if (open) {
        closeRef.current?.focus()
      }
    }, [open])

    if (!open) return null

    return (
      <div>
        <h2>{title}</h2>
        <button type="button" ref={closeRef} onClick={() => onCancel?.()}>
          Close
        </button>
        {children}
      </div>
    )
  }

  const Spin = () => <div>Loading...</div>
  const Tag = ({ children }: any) => <span>{children}</span>
  const Table = ({ dataSource = [] }: any) => (
    <div>
      {dataSource.map((item: any, index: number) => (
        <div key={`${item.url || "item"}-${index}`}>{item.title || item.url || "-"}</div>
      ))}
    </div>
  )

  return {
    Modal,
    Spin,
    Tag,
    Table
  }
})

const buildJob = () => ({
  id: 11,
  name: "Morning monitor",
  description: null,
  scope: { sources: [1] },
  schedule_expr: "0 9 * * *",
  timezone: "UTC",
  active: true,
  output_prefs: {},
  created_at: "2026-02-18T00:00:00Z"
})

describe("JobPreviewModal focus restoration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.previewWatchlistJobMock.mockResolvedValue({
      items: [],
      total: 0,
      ingestable: 0,
      filtered: 0
    })
  })

  it("restores focus to the launch control when preview closes", async () => {
    const trigger = document.createElement("button")
    trigger.type = "button"
    trigger.textContent = "Open preview"
    document.body.appendChild(trigger)
    trigger.focus()

    const { rerender } = render(
      <JobPreviewModal
        job={buildJob() as any}
        open
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Close" })).toHaveFocus()
    })

    rerender(
      <JobPreviewModal
        job={buildJob() as any}
        open={false}
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(trigger).toHaveFocus()
    })

    trigger.remove()
  })
})
