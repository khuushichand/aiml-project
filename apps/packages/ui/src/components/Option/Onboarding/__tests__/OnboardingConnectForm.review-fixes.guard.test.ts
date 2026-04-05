import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readOnboardingSource = () =>
  fs.readFileSync(path.resolve(__dirname, "..", "OnboardingConnectForm.tsx"), "utf8")

describe("OnboardingConnectForm review fixes", () => {
  it("keeps researcher shortcut persistence best-effort for ingest flow", () => {
    const source = readOnboardingSource()

    expect(source).toContain('const handleOpenIngestFlow = useCallback(async () => {')
    expect(source).toContain('console.debug("[OnboardingConnectForm] Failed to persist researcher shortcuts", err)')
    expect(source).toContain('await finishAndNavigate("/media", { openQuickIngestIntro: true })')
  })

  it("does not keep an unused actions dependency in the chat flow callback", () => {
    const source = readOnboardingSource()
    const chatFlowBlock = source.match(/const handleOpenChatFlow = useCallback\(async \(\) => \{[\s\S]*?\n  \}, \[([^\]]*)\]\)/)

    expect(chatFlowBlock?.[1]).toBe("finishAndNavigate")
  })
})
