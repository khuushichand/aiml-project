import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery } from "@tanstack/react-query"

import { PromptAssemblyPreview } from "../PromptAssemblyPreview"
import { LorebookDebugPanel } from "../LorebookDebugPanel"

const queryCalls: any[] = []

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn((options: any) => {
    queryCalls.push(options)
    return {
      data: null,
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn()
    }
  })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) =>
      options?.defaultValue || key
  })
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultValue: unknown) => [defaultValue, vi.fn()] as const
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: () => ({
    messageSteeringMode: "none",
    messageSteeringForceNarrate: false
  })
}))

vi.mock("antd", () => ({
  message: {
    success: vi.fn(),
    error: vi.fn()
  }
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getCharacterPromptPreview: vi.fn(),
    getChat: vi.fn(),
    listChatMessages: vi.fn(),
    processWorldBookContext: vi.fn(),
    listCharacterWorldBooks: vi.fn(),
    getChatLorebookDiagnostics: vi.fn()
  }
}))

describe("persona chat settings guards", () => {
  beforeEach(() => {
    queryCalls.length = 0
    vi.clearAllMocks()
  })

  it("keeps lorebook debug character-only while allowing persona prompt preview", () => {
    render(
      <>
        <PromptAssemblyPreview
          serverChatId="chat-1"
          settingsFingerprint="fp-1"
          serverChatAssistantKind="persona"
        />
        <LorebookDebugPanel
          serverChatId="chat-1"
          settingsFingerprint="fp-1"
          serverChatAssistantKind="persona"
        />
      </>
    )

    fireEvent.click(screen.getByRole("button", { name: /Prompt preview/i }))
    fireEvent.click(screen.getByRole("button", { name: /Lorebook Debug/i }))

    expect(
      screen.getByText(
        "Lorebook debug stays character-only for persona chats. Use Prompt preview to inspect persona exemplar guidance instead."
      )
    ).toBeInTheDocument()

    const promptQueryCalls = queryCalls.filter(
      (entry) => entry?.queryKey?.[0] === "promptAssemblyPreview"
    )
    const lorebookQueryCalls = queryCalls.filter(
      (entry) => entry?.queryKey?.[0] === "lorebookDebugPanel"
    )
    expect(promptQueryCalls.some((entry) => entry?.enabled === true)).toBe(true)
    expect(lorebookQueryCalls.some((entry) => entry?.enabled === false)).toBe(
      true
    )
  })
})
