import { beforeEach, describe, expect, it, vi } from "vitest"

const { storageState } = vi.hoisted(() => ({
  storageState: new Map<string, unknown>()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: async (key: string) => storageState.get(key),
    set: async (key: string, value: unknown) => {
      storageState.set(key, value)
    },
    remove: async (key: string) => {
      storageState.delete(key)
    }
  })
}))

import {
  getAllModelSettings,
  getModelSettings,
  setModelSetting,
  setModelSettings
} from "../model-settings"

describe("model-settings llama.cpp controls", () => {
  beforeEach(() => {
    storageState.clear()
  })

  it("persists llama.cpp default chat model settings", async () => {
    await setModelSetting("llamaThinkingBudgetTokens", 64)
    await setModelSetting("llamaGrammarMode", "library")
    await setModelSetting("llamaGrammarId", "grammar_1")
    await setModelSetting("llamaGrammarOverride", 'root ::= "override"')

    await expect(getAllModelSettings()).resolves.toMatchObject({
      llamaThinkingBudgetTokens: 64,
      llamaGrammarMode: "library",
      llamaGrammarId: "grammar_1",
      llamaGrammarOverride: 'root ::= "override"'
    })
  })

  it("persists per-model llama.cpp settings bundles", async () => {
    await setModelSettings({
      model_id: "llama.cpp/local-model",
      settings: {
        llamaGrammarMode: "inline",
        llamaGrammarInline: 'root ::= "ok"',
        llamaThinkingBudgetTokens: 24
      }
    })

    await expect(getModelSettings("llama.cpp/local-model")).resolves.toMatchObject({
      llamaGrammarMode: "inline",
      llamaGrammarInline: 'root ::= "ok"',
      llamaThinkingBudgetTokens: 24
    })
  })
})
