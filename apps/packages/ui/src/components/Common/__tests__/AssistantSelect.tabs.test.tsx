import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  listPersonaProfiles: vi.fn(async () => []),
  setSelectedAssistant: vi.fn(async () => undefined)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn(async () => null),
    listPersonaProfiles: mocks.listPersonaProfiles
  }
}))

vi.mock("@/hooks/useSelectedAssistant", () => ({
  useSelectedAssistant: () => [
    null,
    mocks.setSelectedAssistant,
    { isLoading: false, setRenderValue: vi.fn() }
  ]
}))

import { AssistantSelect } from "../AssistantSelect"

describe("AssistantSelect tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows separate Characters and Personas tabs", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    })

    render(
      <QueryClientProvider client={queryClient}>
        <AssistantSelect />
      </QueryClientProvider>
    )

    expect(screen.getByRole("tab", { name: "Characters" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Personas" })).toBeInTheDocument()
  })
})
