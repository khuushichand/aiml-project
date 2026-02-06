import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { useQuery } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  PromptAssemblyPreview,
  normalizePreviewPayload
} from "../Settings/PromptAssemblyPreview"
import { tldwClient } from "@/services/tldw/TldwApiClient"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) =>
      options?.defaultValue || key
  })
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: () => ({
    messageSteeringMode: "none",
    messageSteeringForceNarrate: false
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getCharacterPromptPreview: vi.fn(),
    prepareCharacterCompletion: vi.fn()
  }
}))

const makeQueryResult = (overrides: Record<string, unknown> = {}) =>
  ({
    data: null,
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
    ...overrides
  }) as any

describe("PromptAssemblyPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useQuery).mockReturnValue(makeQueryResult())
  })

  it("calls prompt-preview endpoint (not completions prep) when opened", async () => {
    const queryCalls: any[] = []
    vi.mocked(useQuery).mockImplementation((options: any) => {
      queryCalls.push(options)
      return makeQueryResult()
    })
    vi.mocked(tldwClient.getCharacterPromptPreview).mockResolvedValue({
      sections: [],
      total_supplemental_effective_tokens: 0,
      supplemental_budget: 1200
    })

    render(
      <PromptAssemblyPreview serverChatId="chat-preview-1" settingsFingerprint="fp-1" />
    )

    fireEvent.click(
      screen.getByRole("button", {
        name: /Prompt preview/i
      })
    )

    const enabledCall = queryCalls.find((call) => call?.enabled === true)
    expect(enabledCall).toBeTruthy()
    await enabledCall.queryFn()

    expect(tldwClient.getCharacterPromptPreview).toHaveBeenCalledWith(
      "chat-preview-1",
      expect.objectContaining({
        include_character_context: true,
        limit: 250,
        offset: 0,
        continue_as_user: false,
        impersonate_user: false,
        force_narrate: false
      })
    )
    expect(tldwClient.prepareCharacterCompletion).not.toHaveBeenCalled()
  })

  it("normalizes server sections, warnings, and conflicts", () => {
    const summary = normalizePreviewPayload({
      sections: [
        {
          name: "message_steering",
          content: "Steering instruction",
          tokens_estimated: 7,
          tokens_effective: 5
        },
        {
          name: "greeting",
          content: "",
          tokens_estimated: 3
        }
      ],
      total_supplemental_effective_tokens: 5,
      supplemental_budget: 1200,
      budget_status: "ok",
      warnings: ["warning-1"],
      conflicts: [{ type: "scalar_conflict", message: "conflict-1" }],
      examples: ["example-1"]
    })

    expect(summary.supplementalTokens).toBe(5)
    expect(summary.supplementalBudget).toBe(1200)
    expect(summary.budgetStatus).toBe("ok")
    expect(summary.warnings).toEqual(["warning-1"])
    expect(summary.conflicts).toEqual([
      { type: "scalar_conflict", message: "conflict-1" }
    ])
    expect(summary.examples).toEqual(["example-1"])
    expect(summary.sections[0]).toEqual(
      expect.objectContaining({
        key: "message_steering",
        active: true,
        tokens: 5
      })
    )
    expect(summary.sections[1]).toEqual(
      expect.objectContaining({
        key: "greeting",
        active: true,
        tokens: 3
      })
    )
  })
})
