import { describe, expect, it, vi } from "vitest"

vi.mock("@/utils/system-message", async () => {
  const { SystemMessage } = await import("@/types/messages")
  return {
    systemPromptFormatter: async ({
      content,
      appendable
    }: {
      content: string
      appendable?: boolean
    }) =>
      new SystemMessage({
        content,
        additional_kwargs: appendable ? { appendable: true } : {}
      })
  }
})

import { SystemMessage, HumanMessage } from "@/types/messages"
import { createDefaultActorSettings } from "@/types/actor"
import { maybeInjectActorMessage } from "@/utils/actor"

describe("maybeInjectActorMessage (appendable merge)", () => {
  it("concatenates actor system content when both blocks are appendable", async () => {
    const base = createDefaultActorSettings()
    base.isEnabled = true
    base.notes = "Actor note"
    base.templateMode = "override"
    base.chatPosition = "after"
    base.chatRole = "system"
    base.appendable = true

    const history = [
      new SystemMessage({
        content: "Base system",
        additional_kwargs: { appendable: true }
      }),
      new HumanMessage({ content: "Hi" })
    ]

    const result = await maybeInjectActorMessage(history, base, true)

    expect(result).toHaveLength(2)
    const merged = result[0] as SystemMessage
    expect(merged.content).toBe("Base system\n\nScene notes: Actor note")
    expect(merged.additional_kwargs.appendable).toBe(true)
  })

  it("replaces system content when appendable flags do not align", async () => {
    const base = createDefaultActorSettings()
    base.isEnabled = true
    base.notes = "Actor note"
    base.templateMode = "override"
    base.chatPosition = "after"
    base.chatRole = "system"
    base.appendable = true

    const history = [
      new SystemMessage({ content: "Base system" }),
      new HumanMessage({ content: "Hi" })
    ]

    const result = await maybeInjectActorMessage(history, base, true)

    expect(result).toHaveLength(2)
    const merged = result[0] as SystemMessage
    expect(merged.content).toBe("Scene notes: Actor note")
    expect(String(merged.content)).not.toContain("Base system")
  })
})
