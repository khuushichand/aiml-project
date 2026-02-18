import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => {
  const values = new Map<string, string>()
  return {
    values,
    get: vi.fn(async (key: string) => values.get(key)),
    set: vi.fn(async (key: string, value: string) => {
      values.set(key, value)
    })
  }
})

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (...args: unknown[]) =>
      (state.get as (...args: unknown[]) => unknown)(...args),
    set: (...args: unknown[]) =>
      (state.set as (...args: unknown[]) => unknown)(...args)
  })
}))

const importApplication = async () => import("@/services/application")

describe("copilot prompt service contract", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.values.clear()
  })

  it("updates only provided copilot keys and keeps unrelated prompts unchanged", async () => {
    const { getAllCopilotPrompts, setAllCopilotPrompts } = await importApplication()

    await setAllCopilotPrompts([
      { key: "summary", prompt: "Initial summary {text}" },
      { key: "rephrase", prompt: "Initial rephrase {text}" }
    ])

    await setAllCopilotPrompts([{ key: "summary", prompt: "Updated summary {text}" }])

    const prompts = await getAllCopilotPrompts()
    expect(prompts.find((prompt) => prompt.key === "summary")?.prompt).toBe(
      "Updated summary {text}"
    )
    expect(prompts.find((prompt) => prompt.key === "rephrase")?.prompt).toBe(
      "Initial rephrase {text}"
    )
  })

  it("exposes upsertCopilotPrompts alias with the same semantics", async () => {
    const { getAllCopilotPrompts, upsertCopilotPrompts } = await importApplication()

    await upsertCopilotPrompts([{ key: "custom", prompt: "Custom pipeline: {text}" }])

    const prompts = await getAllCopilotPrompts()
    expect(prompts.find((prompt) => prompt.key === "custom")?.prompt).toBe(
      "Custom pipeline: {text}"
    )
  })
})
