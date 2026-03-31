import { describe, expect, it, vi } from "vitest"

vi.mock("~/services/tldw-server", () => ({
  promptForRag: vi.fn()
}))

vi.mock("@/utils/generate-history", () => ({
  generateHistory: vi.fn()
}))

vi.mock("@/models", () => ({
  pageAssistModel: vi.fn()
}))

vi.mock("@/utils/human-message", () => ({
  humanMessageFormatter: vi.fn()
}))

vi.mock("@/libs/reasoning", () => ({
  removeReasoning: vi.fn()
}))

vi.mock("@/utils/format-docs", () => ({
  formatDocs: vi.fn()
}))

vi.mock("@/services/app", () => ({
  getNoOfRetrievedDocs: vi.fn()
}))

vi.mock("@/services/rag/unified-rag", () => ({
  DEFAULT_RAG_SETTINGS: {
    include_note_ids: [],
    include_media_ids: [],
    top_k: 8,
    search_mode: "hybrid"
  }
}))

vi.mock("@/services/settings/registry", () => ({
  coerceBooleanOrNull: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {}
}))

vi.mock("@/utils/actor", () => ({
  maybeInjectActorMessage: vi.fn()
}))

vi.mock("@/utils/resolve-api-provider", () => ({
  resolveApiProviderForModel: vi.fn()
}))

vi.mock("../chatModePipeline", () => ({
  runChatPipeline: vi.fn()
}))

vi.mock("@/utils/output-formatting-guide", () => ({
  appendSystemPromptSuffix: vi.fn()
}))

import { __testing__ } from "../ragMode"

describe("ragMode sanitizer", () => {
  it("preserves legacy numeric include_note_ids arrays", () => {
    const sanitized = __testing__.sanitizeRagAdvancedOptions({
      include_note_ids: [101, 202]
    })

    expect(sanitized.include_note_ids).toEqual([101, 202])
  })

  it("normalizes mixed include_note_ids arrays to strings", () => {
    const sanitized = __testing__.sanitizeRagAdvancedOptions({
      include_note_ids: [101, "note-2"]
    })

    expect(sanitized.include_note_ids).toEqual(["101", "note-2"])
  })
})
