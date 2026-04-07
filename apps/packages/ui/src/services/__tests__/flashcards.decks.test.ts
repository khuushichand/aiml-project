import { beforeEach, describe, expect, it, vi } from "vitest"

const listSpy = vi.hoisted(() => vi.fn())

vi.mock("@/services/background-proxy", () => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/resource-client", () => ({
  createResourceClient: vi.fn(() => ({
    list: listSpy,
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn()
  }))
}))

import { listDecks } from "@/services/flashcards"

describe("flashcards deck service", () => {
  beforeEach(() => {
    listSpy.mockReset()
    listSpy.mockResolvedValue([])
  })

  it("passes workspace visibility filters as deck list query params", async () => {
    const controller = new AbortController()

    await listDecks({
      workspace_id: "workspace-7",
      include_workspace_items: true,
      signal: controller.signal
    })

    expect(listSpy).toHaveBeenCalledWith(
      {
        workspace_id: "workspace-7",
        include_workspace_items: true
      },
      {
        abortSignal: controller.signal
      }
    )
  })
})
