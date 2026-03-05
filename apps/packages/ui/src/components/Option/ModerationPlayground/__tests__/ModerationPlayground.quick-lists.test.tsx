import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import * as moderationService from "@/services/moderation"
import { ModerationPlayground } from "../index"

const useQueryMock = vi.fn()

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: unknown) => useQueryMock(options)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

describe("ModerationPlayground quick phrase lists", () => {
  const settingsQueryResult = {
    data: {
      pii_enabled: false,
      categories_enabled: [] as string[],
      effective: { categories_enabled: [] as string[] }
    },
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined)
  }

  const policyQueryResult = {
    data: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "warn",
      output_action: "warn",
      categories_enabled: [] as string[],
      blocklist_count: 0
    },
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined)
  }

  const overridesQueryResult = {
    data: { overrides: {} as Record<string, unknown> },
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined)
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem("moderation-playground-onboarded", "true")

    useQueryMock.mockImplementation((options: { queryKey?: unknown[] } | undefined) => {
      const firstKey = options?.queryKey?.[0]
      const queryKey = typeof firstKey === "string" ? firstKey : ""
      if (queryKey === "moderation-settings") {
        return settingsQueryResult
      }
      if (queryKey === "moderation-policy") {
        return policyQueryResult
      }
      if (queryKey === "moderation-overrides") {
        return overridesQueryResult
      }
      return { data: null, isFetching: false, refetch: vi.fn().mockResolvedValue(undefined) }
    })

    vi.spyOn(moderationService, "getUserOverride").mockResolvedValue({})
    vi.spyOn(moderationService, "setUserOverride").mockResolvedValue({ persisted: true } as any)
    vi.spyOn(moderationService, "deleteUserOverride").mockResolvedValue({ status: "deleted" })
  })

  const switchToUserScopeAndLoadUser = async () => {
    fireEvent.click(screen.getByRole("radio", { name: "User (Individual)" }))
    fireEvent.change(screen.getByPlaceholderText("Enter User ID"), {
      target: { value: "alice" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Load user" }))

    await waitFor(() => {
      expect(moderationService.getUserOverride).toHaveBeenCalledWith("alice")
    })
  }

  it("renders quick phrase composer in user scope without advanced mode", () => {
    render(<ModerationPlayground />)

    fireEvent.click(screen.getByRole("radio", { name: "User (Individual)" }))

    expect(screen.getByText("User Phrase Lists")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("Add a word or phrase")).toBeInTheDocument()
  })

  it("adds ban and notify items to separate lists", async () => {
    render(<ModerationPlayground />)
    await switchToUserScopeAndLoadUser()

    const phraseInput = screen.getByPlaceholderText("Add a word or phrase")

    fireEvent.change(phraseInput, { target: { value: "danger phrase" } })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))

    fireEvent.click(screen.getByRole("radio", { name: "Notify list" }))
    fireEvent.change(phraseInput, { target: { value: "watch phrase" } })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))

    expect(screen.getByText("Banned phrases")).toBeInTheDocument()
    expect(screen.getByText("Notify phrases")).toBeInTheDocument()
    expect(screen.getByText("danger phrase")).toBeInTheDocument()
    expect(screen.getByText("watch phrase")).toBeInTheDocument()
  })

  it("prevents duplicate quick rules", async () => {
    render(<ModerationPlayground />)
    await switchToUserScopeAndLoadUser()

    const phraseInput = screen.getByPlaceholderText("Add a word or phrase")

    fireEvent.change(phraseInput, { target: { value: "duplicate phrase" } })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))

    fireEvent.change(phraseInput, { target: { value: "duplicate phrase" } })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))

    expect(screen.getAllByText("duplicate phrase")).toHaveLength(1)
  })

  it("blocks invalid regex quick rule", async () => {
    render(<ModerationPlayground />)
    await switchToUserScopeAndLoadUser()

    fireEvent.click(screen.getByRole("checkbox", { name: "Regex" }))
    fireEvent.change(screen.getByPlaceholderText("Add a word or phrase"), {
      target: { value: "(" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))

    expect(screen.queryByText("(")).not.toBeInTheDocument()
  })

  it("includes rules in setUserOverride payload on save", async () => {
    render(<ModerationPlayground />)
    await switchToUserScopeAndLoadUser()

    fireEvent.change(screen.getByPlaceholderText("Add a word or phrase"), {
      target: { value: "save me" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Add" }))
    fireEvent.click(screen.getByRole("button", { name: "Save user override settings" }))

    await waitFor(() => {
      expect(moderationService.setUserOverride).toHaveBeenCalled()
    })

    const call = vi.mocked(moderationService.setUserOverride).mock.calls.at(-1)
    expect(call?.[0]).toBe("alice")
    expect(call?.[1]).toMatchObject({
      rules: [
        expect.objectContaining({
          pattern: "save me",
          is_regex: false,
          action: "block",
          phase: "both"
        })
      ]
    })
  })
})
