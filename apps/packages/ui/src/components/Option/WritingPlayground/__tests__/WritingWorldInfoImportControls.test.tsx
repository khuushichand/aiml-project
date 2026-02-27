// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { WritingWorldInfoImportControls } from "../WritingWorldInfoImportControls"
import type { WritingWorldInfoSettings } from "../writing-context-utils"

const translate = (
  key: string,
  fallbackOrOptions?: string | Record<string, unknown>,
  maybeOptions?: Record<string, unknown>
) => {
  if (typeof fallbackOrOptions === "string") {
    if (!maybeOptions) return fallbackOrOptions
    return fallbackOrOptions.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
      const value = maybeOptions[token]
      return value == null ? "" : String(value)
    })
  }
  return key
}

const baseWorldInfo: WritingWorldInfoSettings = {
  enabled: true,
  prefix: "",
  suffix: "",
  search_range: 1200,
  entries: [
    {
      id: "entry-1",
      enabled: true,
      keys: ["hero"],
      content: "Existing",
      use_regex: false,
      case_sensitive: false
    }
  ]
}

describe("WritingWorldInfoImportControls", () => {
  it("imports in replace mode by default", async () => {
    const onImported = vi.fn()
    const onImportError = vi.fn()

    render(
      <WritingWorldInfoImportControls
        disabled={false}
        worldInfo={baseWorldInfo}
        onImported={onImported}
        onImportError={onImportError}
        t={translate}
      />
    )

    const input = screen.getByTestId("writing-world-info-import")
    const file = new File(
      [
        JSON.stringify({
          world_info: {
            entries: [{ id: "entry-2", keys: ["new"], content: "New entry" }]
          }
        })
      ],
      "world-info.json",
      { type: "application/json" }
    )

    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(onImported).toHaveBeenCalledTimes(1)
    })

    const [nextWorldInfo, mode] = onImported.mock.calls[0]
    expect(mode).toBe("replace")
    expect(nextWorldInfo.entries).toHaveLength(1)
    expect(nextWorldInfo.entries[0]?.id).toBe("entry-2")
    expect(onImportError).not.toHaveBeenCalled()
  })

  it("imports in append mode when selected", async () => {
    const onImported = vi.fn()
    const onImportError = vi.fn()

    render(
      <WritingWorldInfoImportControls
        disabled={false}
        worldInfo={baseWorldInfo}
        onImported={onImported}
        onImportError={onImportError}
        t={translate}
        initialMode="append"
      />
    )

    const input = screen.getByTestId("writing-world-info-import")
    const file = new File(
      [
        JSON.stringify({
          world_info: {
            entries: [{ id: "entry-1", keys: ["new"], content: "Appended entry" }]
          }
        })
      ],
      "world-info.json",
      { type: "application/json" }
    )

    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(onImported).toHaveBeenCalledTimes(1)
    })

    const [nextWorldInfo, mode] = onImported.mock.calls[0]
    expect(mode).toBe("append")
    expect(nextWorldInfo.entries).toHaveLength(2)
    expect(nextWorldInfo.entries[0]?.id).toBe("entry-1")
    expect(nextWorldInfo.entries[1]?.id).toBe("entry-1-2")
    expect(onImportError).not.toHaveBeenCalled()
  })
})
