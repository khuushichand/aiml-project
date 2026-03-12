import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useMcpToolsControl } from "../useMcpToolsControl"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: unknown, maybeOptions?: Record<string, unknown>) => {
      let template = key
      let options: Record<string, unknown> | undefined
      if (typeof fallbackOrOptions === "string") {
        template = fallbackOrOptions
        options = maybeOptions
      } else if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        "defaultValue" in (fallbackOrOptions as Record<string, unknown>)
      ) {
        template = String(
          (fallbackOrOptions as { defaultValue?: unknown }).defaultValue ?? key
        )
        options = fallbackOrOptions as Record<string, unknown>
      } else {
        options = maybeOptions
      }
      if (!options) return template
      return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
        const value = options[token]
        return value == null ? "" : String(value)
      })
    }
  })
}))

describe("useMcpToolsControl", () => {
  it("reports unchecked MCP availability before the first tools load", () => {
    const { result } = renderHook(() =>
      useMcpToolsControl({
        hasMcp: true,
        mcpHealthState: "unknown",
        mcpTools: [],
        mcpToolsLoading: false,
        mcpCatalogs: [],
        toolCatalog: "",
        toolCatalogId: null,
        setToolCatalog: vi.fn(),
        setToolCatalogId: vi.fn(),
        toolChoice: "auto"
      })
    )

    expect(result.current.mcpSummaryLabel).toBe("Not checked yet")
    expect(result.current.mcpStatusLabel).toBe(
      "Open this panel to check availability"
    )
    expect(result.current.mcpAriaLabel).toContain("Not checked yet")
  })
})
