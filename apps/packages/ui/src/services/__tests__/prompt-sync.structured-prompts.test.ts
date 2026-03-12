import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({
  prompts: new Map<string, any>()
}))

const mocks = vi.hoisted(() => ({
  createPrompt: vi.fn(),
  getPrompt: vi.fn(),
  promptAdd: vi.fn(),
  promptGet: vi.fn(),
  promptUpdate: vi.fn(),
  promptWhere: vi.fn()
}))

vi.mock("@/services/prompt-studio-settings", () => ({
  getPromptStudioDefaults: async () => ({
    defaultProjectId: null,
    autoSyncWorkspacePrompts: true
  }),
  setPromptStudioDefaults: async () => undefined
}))

vi.mock("@/services/prompt-studio", () => ({
  listProjects: vi.fn(async () => ({ data: { data: [] } })),
  createProject: vi.fn(async () => ({ data: { data: { id: 42 } } })),
  createPrompt: (...args: unknown[]) =>
    (mocks.createPrompt as (...args: unknown[]) => unknown)(...args),
  updatePrompt: vi.fn(),
  getPrompt: (...args: unknown[]) =>
    (mocks.getPrompt as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/db/dexie/schema", () => ({
  db: {
    prompts: {
      add: (...args: unknown[]) =>
        (mocks.promptAdd as (...args: unknown[]) => unknown)(...args),
      get: (...args: unknown[]) =>
        (mocks.promptGet as (...args: unknown[]) => unknown)(...args),
      update: (...args: unknown[]) =>
        (mocks.promptUpdate as (...args: unknown[]) => unknown)(...args),
      where: (...args: unknown[]) =>
        (mocks.promptWhere as (...args: unknown[]) => unknown)(...args)
    }
  }
}))

vi.mock("@/db/dexie/chat", () => ({
  PageAssistDatabase: class {}
}))

vi.mock("@/db/dexie/helpers", () => ({
  generateID: () => "generated-local-id"
}))

const importPromptSync = async () => import("@/services/prompt-sync")

const makeDefinition = (content: string) => ({
  schema_version: 1,
  format: "structured",
  variables: [
    {
      name: "topic",
      required: true,
      input_type: "text"
    }
  ],
  blocks: [
    {
      id: "task",
      name: "Task",
      role: "user",
      content,
      enabled: true,
      order: 10,
      is_template: true
    }
  ]
})

describe("prompt-sync structured prompt support", () => {
  beforeEach(() => {
    state.prompts.clear()

    mocks.createPrompt.mockReset()
    mocks.getPrompt.mockReset()
    mocks.promptAdd.mockReset()
    mocks.promptGet.mockReset()
    mocks.promptUpdate.mockReset()
    mocks.promptWhere.mockReset()

    mocks.promptAdd.mockImplementation(async (prompt: any) => {
      state.prompts.set(prompt.id, prompt)
    })
    mocks.promptGet.mockImplementation(async (id: string) => state.prompts.get(id))
    mocks.promptUpdate.mockImplementation(async (id: string, updates: Record<string, unknown>) => {
      const current = state.prompts.get(id)
      if (!current) return
      state.prompts.set(id, { ...current, ...updates })
    })
    mocks.promptWhere.mockImplementation((field: string) => ({
      equals: (value: unknown) => ({
        first: async () => {
          for (const prompt of state.prompts.values()) {
            if (prompt?.[field] === value) return prompt
          }
          return undefined
        }
      })
    }))
  })

  it("pushes structured prompt fields to Prompt Studio create payloads", async () => {
    state.prompts.set("local-structured", {
      id: "local-structured",
      title: "Structured Prompt",
      name: "Structured Prompt",
      content: "Explain {{topic}}",
      is_system: false,
      system_prompt: "Legacy system snapshot",
      user_prompt: "Explain {{topic}}",
      promptFormat: "structured",
      promptSchemaVersion: 1,
      structuredPromptDefinition: makeDefinition("Explain {{topic}}"),
      fewShotExamples: [
        {
          inputs: { topic: "Indexes" },
          outputs: { answer: "Use the covering index." }
        }
      ],
      modulesConfig: [
        {
          type: "style_rules",
          enabled: true,
          config: { tone: "concise" }
        }
      ],
      createdAt: 1,
      updatedAt: 1,
      syncStatus: "local"
    })

    mocks.createPrompt.mockResolvedValue({
      data: {
        data: {
          id: 101,
          project_id: 42,
          name: "Structured Prompt",
          system_prompt: "Legacy system snapshot",
          user_prompt: "Explain {{topic}}",
          prompt_format: "structured",
          prompt_schema_version: 1,
          prompt_definition: makeDefinition("Explain {{topic}}"),
          version_number: 1,
          updated_at: "2026-03-10T00:00:00Z"
        }
      }
    })

    const { pushToStudio } = await importPromptSync()
    await pushToStudio("local-structured", 42)

    expect(mocks.createPrompt).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 42,
        prompt_format: "structured",
        prompt_schema_version: 1,
        prompt_definition: makeDefinition("Explain {{topic}}"),
        few_shot_examples: [
          {
            inputs: { topic: "Indexes" },
            outputs: { answer: "Use the covering index." }
          }
        ],
        modules_config: [
          {
            type: "style_rules",
            enabled: true,
            config: { tone: "concise" }
          }
        ]
      })
    )
  })

  it("pulls structured prompt fields into the local prompt record", async () => {
    mocks.getPrompt.mockResolvedValue({
      data: {
        data: {
          id: 501,
          project_id: 9,
          name: "Server Structured Prompt",
          system_prompt: "Legacy system snapshot",
          user_prompt: "Explain {{topic}}",
          prompt_format: "structured",
          prompt_schema_version: 1,
          prompt_definition: makeDefinition("Explain {{topic}}"),
          few_shot_examples: [
            {
              inputs: { topic: "SQLite" },
              outputs: { answer: "Use FTS5." }
            }
          ],
          modules_config: [
            {
              type: "style_rules",
              enabled: true,
              config: { tone: "formal" }
            }
          ],
          version_number: 2,
          updated_at: "2026-03-10T00:00:00Z"
        }
      }
    })

    const { pullFromStudio } = await importPromptSync()
    await pullFromStudio(501)

    expect(state.prompts.get("generated-local-id")).toEqual(
      expect.objectContaining({
        promptFormat: "structured",
        promptSchemaVersion: 1,
        structuredPromptDefinition: makeDefinition("Explain {{topic}}"),
        fewShotExamples: [
          {
            inputs: { topic: "SQLite" },
            outputs: { answer: "Use FTS5." }
          }
        ],
        modulesConfig: [
          {
            type: "style_rules",
            enabled: true,
            config: { tone: "formal" }
          }
        ]
      })
    )
  })

  it("treats structured definition changes as sync conflicts even when legacy text matches", async () => {
    state.prompts.set("local-conflict-structured", {
      id: "local-conflict-structured",
      title: "Structured Prompt",
      name: "Structured Prompt",
      content: "Explain {{topic}}",
      is_system: false,
      system_prompt: "Legacy system snapshot",
      user_prompt: "Explain {{topic}}",
      promptFormat: "structured",
      promptSchemaVersion: 1,
      structuredPromptDefinition: makeDefinition("Explain {{topic}}"),
      createdAt: 1,
      updatedAt: 20,
      serverId: 77,
      syncStatus: "synced",
      serverUpdatedAt: "2026-03-10T00:00:00Z",
      lastSyncedAt: 10
    })

    mocks.getPrompt.mockResolvedValue({
      data: {
        data: {
          id: 77,
          project_id: 9,
          name: "Structured Prompt",
          system_prompt: "Legacy system snapshot",
          user_prompt: "Explain {{topic}}",
          prompt_format: "structured",
          prompt_schema_version: 1,
          prompt_definition: makeDefinition("Summarize {{topic}}"),
          version_number: 2,
          updated_at: "2026-03-10T01:00:00Z"
        }
      }
    })

    const { getSyncStatus } = await importPromptSync()
    await expect(getSyncStatus("local-conflict-structured")).resolves.toEqual(
      expect.objectContaining({
        status: "conflict",
        hasConflict: true
      })
    )
  })

  it("treats few-shot or module changes as sync conflicts for legacy prompts", async () => {
    state.prompts.set("local-conflict-legacy", {
      id: "local-conflict-legacy",
      title: "Legacy Prompt",
      name: "Legacy Prompt",
      content: "Explain topic",
      is_system: false,
      system_prompt: "Legacy system snapshot",
      user_prompt: "Explain topic",
      fewShotExamples: [
        {
          inputs: { topic: "SQLite" },
          outputs: { answer: "Use indexes." }
        }
      ],
      modulesConfig: [
        {
          type: "style_rules",
          enabled: true,
          config: { tone: "concise" }
        }
      ],
      createdAt: 1,
      updatedAt: 20,
      serverId: 88,
      syncStatus: "synced",
      serverUpdatedAt: "2026-03-10T00:00:00Z",
      lastSyncedAt: 10
    })

    mocks.getPrompt.mockResolvedValue({
      data: {
        data: {
          id: 88,
          project_id: 9,
          name: "Legacy Prompt",
          system_prompt: "Legacy system snapshot",
          user_prompt: "Explain topic",
          few_shot_examples: [
            {
              inputs: { topic: "SQLite" },
              outputs: { answer: "Use FTS5." }
            }
          ],
          modules_config: [
            {
              type: "style_rules",
              enabled: true,
              config: { tone: "formal" }
            }
          ],
          version_number: 2,
          updated_at: "2026-03-10T01:00:00Z"
        }
      }
    })

    const { getSyncStatus } = await importPromptSync()
    await expect(getSyncStatus("local-conflict-legacy")).resolves.toEqual(
      expect.objectContaining({
        status: "conflict",
        hasConflict: true
      })
    )
  })
})
