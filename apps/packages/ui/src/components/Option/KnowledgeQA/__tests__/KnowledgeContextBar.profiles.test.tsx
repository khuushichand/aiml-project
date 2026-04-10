import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeContextBar } from "../context/KnowledgeContextBar"

const PROFILES_STORAGE_KEY = "tldw:knowledge-qa:saved-profiles"
const storageState = new Map<string, unknown>()

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    const [value, setValue] = React.useState(() =>
      storageState.has(key) ? storageState.get(key) : defaultValue
    )

    const updateValue = async (nextValue: unknown) => {
      const resolved =
        typeof nextValue === "function"
          ? (nextValue as (previousValue: unknown) => unknown)(
              storageState.has(key) ? storageState.get(key) : defaultValue
            )
          : nextValue
      storageState.set(key, resolved)
      setValue(resolved)
      return resolved
    }

    return [value, updateValue] as const
  },
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn().mockResolvedValue(undefined),
    getProviders: vi.fn().mockResolvedValue({
      default_provider: "openai",
      providers: [{ name: "openai", display_name: "OpenAI", models: ["gpt-4o-mini"] }],
    }),
    listMedia: vi.fn().mockResolvedValue({ items: [] }),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}))

function renderContextBar(overrides: Record<string, unknown> = {}) {
  const defaults = {
    preset: "balanced" as const,
    onPresetChange: vi.fn(),
    sources: ["media_db" as const],
    onSourcesChange: vi.fn(),
    includeMediaIds: [] as number[],
    onIncludeMediaIdsChange: vi.fn(),
    includeNoteIds: [] as string[],
    onIncludeNoteIdsChange: vi.fn(),
    webEnabled: true,
    onToggleWeb: vi.fn(),
    generationProvider: null,
    generationModel: null,
    onGenerationProviderChange: vi.fn(),
    onGenerationModelChange: vi.fn(),
    contextChangedSinceLastRun: false,
    onOpenSettings: vi.fn(),
  }

  const props = { ...defaults, ...overrides }
  return { ...render(<KnowledgeContextBar {...props} />), props }
}

function openProfileMenu() {
  fireEvent.click(screen.getByRole("button", { name: /Profiles/i }))
}

function enterSaveMode() {
  fireEvent.click(screen.getByText("Save current settings..."))
}

function typeProfileName(name: string) {
  fireEvent.change(screen.getByPlaceholderText("Profile name"), {
    target: { value: name },
  })
}

function clickSaveButton() {
  fireEvent.click(screen.getByRole("button", { name: "Save" }))
}

describe("KnowledgeContextBar saved search profiles", () => {
  beforeEach(() => {
    storageState.clear()
  })

  afterEach(() => {
    storageState.clear()
  })

  describe("profile save", () => {
    it("saves current settings through the shared storage hook when a name is provided", () => {
      renderContextBar({
        preset: "fast",
        sources: ["media_db", "notes"],
        webEnabled: true,
      })

      openProfileMenu()
      expect(screen.getByText("No saved profiles yet.")).toBeInTheDocument()

      enterSaveMode()
      typeProfileName("My Research Setup")
      clickSaveButton()

      const stored = storageState.get(PROFILES_STORAGE_KEY) as Array<Record<string, unknown>>
      expect(stored).toHaveLength(1)
      expect(stored[0]).toEqual({
        name: "My Research Setup",
        sources: ["media_db", "notes"],
        preset: "fast",
        enableWebFallback: true,
      })
    })

    it("replaces a profile with the same name instead of duplicating", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        {
          name: "Existing",
          sources: ["media_db"],
          preset: "balanced",
          enableWebFallback: false,
        },
      ])

      renderContextBar({
        preset: "thorough",
        sources: ["notes"],
        webEnabled: true,
      })

      openProfileMenu()
      enterSaveMode()
      typeProfileName("Existing")
      clickSaveButton()

      const stored = storageState.get(PROFILES_STORAGE_KEY) as Array<Record<string, unknown>>
      expect(stored).toHaveLength(1)
      expect(stored[0].preset).toBe("thorough")
      expect(stored[0].sources).toEqual(["notes"])
      expect(stored[0].enableWebFallback).toBe(true)
    })
  })

  describe("profile load", () => {
    it("applies saved profile settings when clicked", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        {
          name: "Deep Research",
          sources: ["media_db", "notes", "chats"],
          preset: "thorough",
          enableWebFallback: false,
        },
      ])

      const { props } = renderContextBar({
        preset: "fast",
        sources: ["media_db"],
        webEnabled: true,
      })

      openProfileMenu()
      fireEvent.click(screen.getByRole("menuitem", { name: /Deep Research/i }))

      expect(props.onSourcesChange).toHaveBeenCalledWith(["media_db", "notes", "chats"])
      expect(props.onPresetChange).toHaveBeenCalledWith("thorough")
      expect(props.onToggleWeb).toHaveBeenCalledTimes(1)
    })

    it("does not toggle web when profile matches current state", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        {
          name: "Quick Check",
          sources: ["media_db"],
          preset: "fast",
          enableWebFallback: true,
        },
      ])

      const { props } = renderContextBar({
        preset: "balanced",
        sources: ["notes"],
        webEnabled: true,
      })

      openProfileMenu()
      fireEvent.click(screen.getByRole("menuitem", { name: /Quick Check/i }))

      expect(props.onToggleWeb).not.toHaveBeenCalled()
    })
  })

  describe("profile delete", () => {
    it("removes the profile from shared storage when delete is clicked", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        {
          name: "Profile A",
          sources: ["media_db"],
          preset: "fast",
          enableWebFallback: true,
        },
        {
          name: "Profile B",
          sources: ["notes"],
          preset: "balanced",
          enableWebFallback: false,
        },
      ])

      renderContextBar()

      openProfileMenu()
      fireEvent.click(
        screen.getByRole("button", { name: "Delete profile Profile A" })
      )

      const stored = storageState.get(PROFILES_STORAGE_KEY) as Array<Record<string, unknown>>
      expect(stored).toHaveLength(1)
      expect(stored[0].name).toBe("Profile B")
    })

    it("keeps the delete action discoverable for keyboard users", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        {
          name: "Profile A",
          sources: ["media_db"],
          preset: "fast",
          enableWebFallback: true,
        },
      ])

      renderContextBar()

      openProfileMenu()
      const deleteButton = screen.getByRole("button", {
        name: "Delete profile Profile A",
      })

      expect(deleteButton.className).toContain("group-focus-within:visible")
    })
  })

  describe("max profiles limit", () => {
    it("disables save button and shows limit message when 5 profiles exist", () => {
      const profiles = Array.from({ length: 5 }, (_, i) => ({
        name: `Profile ${i + 1}`,
        sources: ["media_db"] as string[],
        preset: "fast",
        enableWebFallback: true,
      }))
      storageState.set(PROFILES_STORAGE_KEY, profiles)

      renderContextBar()

      openProfileMenu()

      const limitButton = screen.getByText("Limit reached (5)")
      expect(limitButton).toBeInTheDocument()
      expect(limitButton.closest("button")).toBeDisabled()
    })
  })

  describe("corrupt storage", () => {
    it("renders without saved profiles when stored data is corrupt", () => {
      storageState.set(PROFILES_STORAGE_KEY, "{{not valid json")

      renderContextBar()

      openProfileMenu()
      expect(screen.getByText("No saved profiles yet.")).toBeInTheDocument()
    })

    it("filters out invalid entries from stored data", () => {
      storageState.set(PROFILES_STORAGE_KEY, [
        { name: "Valid", sources: ["media_db"], preset: "fast", enableWebFallback: true },
        { name: "", sources: ["media_db"], preset: "fast", enableWebFallback: true },
        { name: "Bad preset", sources: ["media_db"], preset: "bogus", enableWebFallback: true },
        { name: "Bad source", sources: ["bogus"], preset: "fast", enableWebFallback: true },
        { name: 123, sources: "not-an-array", preset: "fast", enableWebFallback: true },
        null,
        "just a string",
      ])

      renderContextBar()

      openProfileMenu()
      expect(screen.getByRole("menuitem", { name: /Valid/i })).toBeInTheDocument()
      expect(screen.queryByRole("menuitem", { name: /Bad preset/i })).not.toBeInTheDocument()
      expect(screen.queryByRole("menuitem", { name: /Bad source/i })).not.toBeInTheDocument()
      expect(screen.queryByText("123")).not.toBeInTheDocument()
    })
  })

  describe("empty name prevention", () => {
    it("disables save button when profile name is empty", () => {
      renderContextBar()

      openProfileMenu()
      enterSaveMode()

      expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
    })

    it("disables save button when profile name is whitespace only", () => {
      renderContextBar()

      openProfileMenu()
      enterSaveMode()
      typeProfileName("   ")

      expect(screen.getByRole("button", { name: "Save" })).toBeDisabled()
    })

    it("does not persist anything when Enter is pressed with empty name", () => {
      renderContextBar()

      openProfileMenu()
      enterSaveMode()

      fireEvent.keyDown(screen.getByPlaceholderText("Profile name"), { key: "Enter" })

      expect(storageState.has(PROFILES_STORAGE_KEY)).toBe(false)
    })
  })
})
