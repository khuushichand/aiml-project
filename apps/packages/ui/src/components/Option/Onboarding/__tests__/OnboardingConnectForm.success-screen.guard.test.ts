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

  it("has selectedIntent state for persona-specific guided flow", () => {
    const source = readOnboardingSource()
    expect(source).toContain("selectedIntent")
    expect(source).toContain("setSelectedIntent")
  })

  it("shows family persona steps when family intent is selected", () => {
    const source = readOnboardingSource()
    expect(source).toContain('data-testid="intent-steps-family"')
    expect(source).toContain("familyStep1")
    expect(source).toContain("familyStep2")
    expect(source).toContain("familyStep3")
    expect(source).toContain("familyStepsTitle")
  })

  it("shows research persona steps when research intent is selected", () => {
    const source = readOnboardingSource()
    expect(source).toContain('data-testid="intent-steps-research"')
    expect(source).toContain("researchStep1")
    expect(source).toContain("researchStep2")
    expect(source).toContain("researchStep3")
    expect(source).toContain("researchStepsTitle")
  })

  it("provides back button and skip-to-chat in guided steps", () => {
    const source = readOnboardingSource()
    expect(source).toContain("backToChoices")
    expect(source).toContain("skipToChat")
    expect(source).toContain("getStarted")
  })

  it("chat intent navigates directly without extra steps", () => {
    const source = readOnboardingSource()
    // Chat card should call handleOpenChatFlow directly, not setSelectedIntent("chat")
    expect(source).toContain('onClick={handleOpenChatFlow}')
    expect(source).not.toContain('setSelectedIntent("chat")')
  })

  it("preserves persona when guided users skip to chat", () => {
    const source = readOnboardingSource()
    expect(source).toContain("const handleGoToChat = useCallback")
    expect(source).toContain('onClick={handleGoToChat}')
    expect(source).not.toContain('<Button onClick={handleOpenChatFlow}>')
  })
})
