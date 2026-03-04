import { describe, expect, it } from "vitest"

import {
  DEFAULT_SIDEBAR_SHORTCUT_SELECTION,
  SIDEBAR_SHORTCUT_SELECTION_SETTING
} from "@/services/settings/ui-settings"
import { normalizeSettingValue } from "@/services/settings/registry"

const LEGACY_DEFAULT_SELECTION = [
  "quick-ingest",
  "chat",
  "prompts",
  "prompt-studio",
  "characters",
  "chat-dictionaries",
  "world-books",
  "knowledge-qa",
  "media",
  "document-workspace"
]

describe("sidebar shortcut defaults", () => {
  it("includes moderation playground in the default selection", () => {
    expect(DEFAULT_SIDEBAR_SHORTCUT_SELECTION).toContain("moderation-playground")
    expect(DEFAULT_SIDEBAR_SHORTCUT_SELECTION).toHaveLength(10)
  })

  it("migrates legacy default selection to include moderation playground", () => {
    const normalized = normalizeSettingValue(
      SIDEBAR_SHORTCUT_SELECTION_SETTING,
      LEGACY_DEFAULT_SELECTION
    )

    expect(normalized).toContain("moderation-playground")
    expect(normalized).not.toContain("prompt-studio")
    expect(normalized).toHaveLength(10)
  })

  it("keeps custom user selections unchanged", () => {
    const customSelection = ["quick-ingest", "chat", "prompts"]

    const normalized = normalizeSettingValue(
      SIDEBAR_SHORTCUT_SELECTION_SETTING,
      customSelection
    )

    expect(normalized).toEqual(customSelection)
  })
})
