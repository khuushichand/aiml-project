import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundMessage error recovery guard", () => {
  it("keeps retry/switch/continue recovery actions in the error bubble", () => {
    const sourcePath = path.resolve(__dirname, "../Message.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("playground:errorRecovery.retrySameModel")
    expect(source).toContain("playground:errorRecovery.switchModel")
    expect(source).toContain("playground:errorRecovery.tryProviderFallback")
    expect(source).toContain("playground:errorRecovery.continueFromPartial")
    expect(source).toContain("playground:errorRecovery.interruptedSummary")
    expect(source).toContain("interruptedGeneration")
    expect(source).toContain("Recommended next actions:")
    expect(source).toContain("role=\"alert\"")
    expect(source).toContain("aria-live=\"assertive\"")
    expect(source).toContain("role=\"status\"")
    expect(source).toContain("aria-live=\"polite\"")
    expect(source).toContain("tldw:open-model-settings")
    expect(source).toContain("playground:sources.askWithSources")
    expect(source).toContain("pinnedState")
  })
})
