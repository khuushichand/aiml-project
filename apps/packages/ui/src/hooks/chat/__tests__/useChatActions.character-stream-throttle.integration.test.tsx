import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("useChatActions character stream throttling", () => {
  it("throttles per-token character stream updates via scheduled flushes", () => {
    const sourcePath = path.resolve(__dirname, "../useChatActions.ts")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("const STREAMING_UPDATE_INTERVAL_MS = 80")
    expect(source).toContain("const scheduleStreamingUpdate = (text: string, reasoningTime: number)")
    expect(source).toContain("scheduleStreamingUpdate(`${fullText}▋`, timetaken)")
    expect(source).toContain("flushStreamingUpdate()")
    expect(source).toContain("cancelStreamingUpdate()")
    expect(source).not.toContain("if (chunkState.token) {\n          setMessages((prev) =>")
  })
})
