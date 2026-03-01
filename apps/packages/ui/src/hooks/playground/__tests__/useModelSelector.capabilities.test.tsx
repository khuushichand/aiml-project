import React from "react"
import { render, renderHook, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useModelSelector } from "../useModelSelector"

const chatModelSettingsState = vi.hoisted(() => ({
  apiProvider: null as string | null,
  numCtx: null as number | null
}))

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
        const value = options?.[token]
        return value == null ? "" : String(value)
      })
    }
  })
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    const initialValue =
      key === "favoriteChatModels"
        ? []
        : key === "modelSelectSortMode"
          ? "provider"
          : defaultValue
    const [value, setValue] = React.useState(initialValue)
    return [value, setValue, { isLoading: false }] as const
  }
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/components/Common/ProviderIcon", () => ({
  ProviderIcons: ({ provider }: { provider?: string }) => (
    <span data-testid={`provider-icon-${provider || "unknown"}`} />
  )
}))

vi.mock("@/services/tldw", () => ({
  tldwModels: {
    getProviderDisplayName: (provider: string) =>
      provider ? provider.toUpperCase() : "CUSTOM"
  }
}))

vi.mock("@/utils/provider-registry", () => ({
  getProviderDisplayName: (provider?: string) =>
    provider ? provider.toUpperCase() : "OTHER"
}))

vi.mock("@/store/model", () => ({
  useStoreChatModelSettings: (
    selector: (state: { apiProvider: string | null; numCtx: number | null }) => unknown
  ) => selector(chatModelSettingsState)
}))

const unwrapFirstMenuItem = (items: any[]) => {
  if (!Array.isArray(items) || items.length === 0) return null
  const first = items[0]
  if (first?.type === "group" && Array.isArray(first.children)) {
    return first.children[0] ?? null
  }
  return first
}

describe("useModelSelector capability rendering", () => {
  it("includes vision/tools/streaming/context and price badges in dropdown items", () => {
    const { result } = renderHook(() =>
      useModelSelector({
        composerModels: [
          {
            model: "openai/gpt-4o-mini",
            nickname: "GPT-4o mini",
            provider: "openai",
            context_length: 8192,
            details: {
              capabilities: ["vision", "tools", "streaming"],
              price_hint: "$0.15/$0.60"
            }
          }
        ],
        selectedModel: "openai/gpt-4o-mini",
        setSelectedModel: vi.fn(),
        navigate: vi.fn()
      })
    )

    const firstItem = unwrapFirstMenuItem(result.current.modelDropdownMenuItems)
    expect(firstItem).not.toBeNull()

    render(<>{firstItem?.label}</>)

    expect(screen.getByText("Vision")).toBeInTheDocument()
    expect(screen.getByText("Tools")).toBeInTheDocument()
    expect(screen.getByText("Streaming")).toBeInTheDocument()
    expect(screen.getByText("8k ctx")).toBeInTheDocument()
    expect(screen.getByText("$0.15/$0.60")).toBeInTheDocument()
  })
})

