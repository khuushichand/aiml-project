import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readOnboardingSource = () =>
  fs.readFileSync(
    path.resolve(__dirname, "..", "OnboardingConnectForm.tsx"),
    "utf8"
  )

describe("OnboardingConnectForm success screen guards", () => {
  it("renders a success screen container with data-testid", () => {
    const source = readOnboardingSource()
    expect(source).toContain('data-testid="onboarding-success-screen"')
  })

  it("has ingest, media, chat, and settings action handlers", () => {
    const source = readOnboardingSource()
    expect(source).toContain("handleOpenIngestFlow")
    expect(source).toContain("handleOpenMediaFlow")
    expect(source).toContain("handleOpenChatFlow")
    expect(source).toContain("handleOpenSettingsFlow")
    expect(source).toContain("handleOpenFamilyFlow")
  })

  it("includes provider and model selector on success screen", () => {
    const source = readOnboardingSource()
    expect(source).toContain("Set your defaults")
  })

  it("shows showSuccess state to gate the success screen", () => {
    const source = readOnboardingSource()
    expect(source).toContain("showSuccess")
  })

  it("includes intent selector cards on the success screen", () => {
    const source = readOnboardingSource()
    expect(source).toContain('data-testid="intent-selector"')
    expect(source).toContain("/settings/family-guardrails")
    expect(source).toContain("intentChat")
    expect(source).toContain("intentFamily")
    expect(source).toContain("intentResearch")
  })
})
