import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({
  defaults: {
    defaultProjectId: null as number | null,
    autoSyncWorkspacePrompts: true
  },
  prompts: new Map<string, any>()
}))

const mocks = vi.hoisted(() => ({
  getPromptStudioDefaults: vi.fn(),
  setPromptStudioDefaults: vi.fn(),
  listProjects: vi.fn(),
  createProject: vi.fn(),
  createPrompt: vi.fn(),
  updatePrompt: vi.fn(),
  getPrompt: vi.fn(),
  promptGet: vi.fn(),
  promptUpdate: vi.fn(),
  promptWhere: vi.fn()
}))

vi.mock("@/services/prompt-studio-settings", () => ({
  getPromptStudioDefaults: (...args: unknown[]) =>
    (mocks.getPromptStudioDefaults as (...args: unknown[]) => unknown)(...args),
  setPromptStudioDefaults: (...args: unknown[]) =>
    (mocks.setPromptStudioDefaults as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/services/prompt-studio", () => ({
  listProjects: (...args: unknown[]) =>
    (mocks.listProjects as (...args: unknown[]) => unknown)(...args),
  createProject: (...args: unknown[]) =>
    (mocks.createProject as (...args: unknown[]) => unknown)(...args),
  createPrompt: (...args: unknown[]) =>
    (mocks.createPrompt as (...args: unknown[]) => unknown)(...args),
  updatePrompt: (...args: unknown[]) =>
    (mocks.updatePrompt as (...args: unknown[]) => unknown)(...args),
  getPrompt: (...args: unknown[]) =>
    (mocks.getPrompt as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/db/dexie/schema", () => ({
  db: {
    prompts: {
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
  PageAssistDatabase: class {
    async getAllPrompts() {
      return Array.from(state.prompts.values())
    }
  }
}))

vi.mock("@/db/dexie/helpers", () => ({
  generateID: () => "generated-local-id"
}))

const importPromptSync = async () => import("@/services/prompt-sync")

describe("prompt-sync auto-sync defaults", () => {
  beforeEach(() => {
    state.defaults = {
      defaultProjectId: null,
      autoSyncWorkspacePrompts: true
    }
    state.prompts.clear()

    mocks.getPromptStudioDefaults.mockReset()
    mocks.setPromptStudioDefaults.mockReset()
    mocks.listProjects.mockReset()
    mocks.createProject.mockReset()
    mocks.createPrompt.mockReset()
    mocks.updatePrompt.mockReset()
    mocks.getPrompt.mockReset()
    mocks.promptGet.mockReset()
    mocks.promptUpdate.mockReset()
    mocks.promptWhere.mockReset()

    mocks.getPromptStudioDefaults.mockImplementation(async () => ({
      ...state.defaults
    }))
    mocks.setPromptStudioDefaults.mockImplementation(async (updates: Record<string, unknown>) => {
      state.defaults = { ...state.defaults, ...updates }
      return { ...state.defaults }
    })
    mocks.listProjects.mockResolvedValue({ data: { data: [] } })
    mocks.createProject.mockResolvedValue({ data: { data: { id: 17, name: "Workspace Prompts" } } })
    mocks.createPrompt.mockResolvedValue({
      data: {
        data: {
          id: 101,
          project_id: 17,
          name: "Prompt",
          system_prompt: null,
          user_prompt: "hello",
          version_number: 1,
          updated_at: "2026-02-17T00:00:00Z"
        }
      }
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

  it("enables auto-sync by default and can be disabled", async () => {
    const { shouldAutoSyncWorkspacePrompts } = await importPromptSync()

    await expect(shouldAutoSyncWorkspacePrompts()).resolves.toBe(true)

    state.defaults.autoSyncWorkspacePrompts = false
    await expect(shouldAutoSyncWorkspacePrompts()).resolves.toBe(false)
  })

  it("uses configured default project when available", async () => {
    state.defaults.defaultProjectId = 42
    const { resolveAutoSyncProjectId } = await importPromptSync()

    await expect(resolveAutoSyncProjectId()).resolves.toBe(42)
    expect(mocks.listProjects).not.toHaveBeenCalled()
  })

  it("chooses and persists first available project when default is missing", async () => {
    mocks.listProjects.mockResolvedValue({
      data: { data: [{ id: 7, name: "Team prompts" }] }
    })
    const { resolveAutoSyncProjectId } = await importPromptSync()

    await expect(resolveAutoSyncProjectId()).resolves.toBe(7)
    expect(mocks.setPromptStudioDefaults).toHaveBeenCalledWith(
      expect.objectContaining({ defaultProjectId: 7 })
    )
  })

  it("auto-creates a sync project and syncs prompt when none exists", async () => {
    state.prompts.set("local-1", {
      id: "local-1",
      title: "Prompt",
      name: "Prompt",
      content: "hello",
      user_prompt: "hello",
      is_system: false,
      createdAt: 1,
      updatedAt: 1,
      syncStatus: "local"
    })
    const { autoSyncPrompt } = await importPromptSync()

    const result = await autoSyncPrompt("local-1")
    expect(result.success).toBe(true)
    expect(result.syncStatus).toBe("synced")
    expect(mocks.createProject).toHaveBeenCalledTimes(1)
    expect(mocks.createPrompt).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 17, name: "Prompt" })
    )
    expect(state.prompts.get("local-1")).toEqual(
      expect.objectContaining({
        serverId: 101,
        studioProjectId: 17,
        syncStatus: "synced"
      })
    )
  })

  it("marks prompt pending when project resolution fails", async () => {
    state.prompts.set("local-2", {
      id: "local-2",
      title: "Pending prompt",
      name: "Pending prompt",
      content: "test",
      is_system: false,
      createdAt: 1,
      updatedAt: 1,
      syncStatus: "local"
    })
    mocks.createProject.mockRejectedValueOnce(new Error("forbidden"))
    const { autoSyncPrompt } = await importPromptSync()

    const result = await autoSyncPrompt("local-2")
    expect(result.success).toBe(false)
    expect(result.syncStatus).toBe("pending")
    expect(state.prompts.get("local-2")).toEqual(
      expect.objectContaining({
        syncStatus: "pending"
      })
    )
  })
})
