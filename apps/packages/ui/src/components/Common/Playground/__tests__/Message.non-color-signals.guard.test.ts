import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundMessage non-color signal guard", () => {
  it("keeps icon+text redundancy for mood and compare states", () => {
    const messageSourcePath = path.resolve(__dirname, "../Message.tsx")
    const messageStateSourcePath = path.resolve(__dirname, "../useMessageState.ts")
    const messageSource = fs.readFileSync(messageSourcePath, "utf8")
    const messageStateSource = fs.readFileSync(messageStateSourcePath, "utf8")

    expect(messageSource).toContain("message-mood-indicator")
    expect(messageStateSource).toContain("Mood:")
    expect(messageSource).toContain("playground:composer.compareSelectedTag")
    expect(messageSource).toContain("aria-pressed={props.compareSelected}")
    expect(messageSource).toContain("AlertTriangle")
    expect(messageSource).toContain("CheckCircle2")
    expect(messageSource).toMatch(/(error\.label|playground:compareErrorTitle)/)
    expect(messageSource).toContain("playground:composer.compareChosenLabel")
  })
})
