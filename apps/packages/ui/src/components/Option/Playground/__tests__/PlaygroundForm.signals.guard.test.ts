import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundForm signal surface guard", () => {
  it("keeps mention/slash affordance and state-change/degradation signals", () => {
    const formSourcePath = path.resolve(__dirname, "../PlaygroundForm.tsx")
    const contextPanelSourcePath = path.resolve(
      __dirname,
      "../ContextFootprintPanel.tsx"
    )
    const formSource = fs.readFileSync(formSourcePath, "utf8")
    const contextPanelSource = fs.readFileSync(contextPanelSourcePath, "utf8")

    expect(formSource).toContain("Type a message... (/ commands, @ mentions)")
    expect(formSource).toContain("Changed since last send:")
    expect(formSource).toContain("playground:composer.providerDegraded")
    expect(formSource).toContain("playground:composer.presetChanged")
    expect(formSource).toContain("playground:composer.jsonModeEnabledNotice")
    expect(formSource).toContain("playground:composer.jsonModeHint")
    expect(formSource).toContain("playground:composer.characterAppliesNextTurn")
    expect(formSource).toContain("playground:composer.characterPendingNotice")
    expect(formSource).toContain("ContextFootprintPanel")
    expect(formSource).toContain("playground:composer.compareActivationTitle")
    expect(formSource).toContain("playground:composer.compareActivationBody")
    expect(formSource).toContain(
      "playground:composer.validationCompareMinModelsInline"
    )
    expect(formSource).toContain("useMobileComposerViewport")
    expect(formSource).toContain("data-mobile-keyboard")
    expect(formSource).toContain("scrollMarginBottom")
    expect(formSource).toContain("previousSendStateRef")
    expect(formSource).toContain("onSuccess: () =>")
    expect(formSource).toContain("onError: (error) =>")
    expect(formSource).toContain("textAreaFocus()")
    expect(formSource).toContain("tldw:focus-composer")
    expect(formSource).toContain("el.focus()")
    expect(formSource).toContain("tldw:toggle-compare-mode")
    expect(formSource).toContain("tldw:toggle-mode-launcher")
    expect(formSource).toContain("playground:composer.context.contextMix")
    expect(formSource).toContain("playground:composer.conflict.contextFootprint")
    expect(formSource).toContain("playgroundStartupTemplateBundles")
    expect(formSource).toContain('data-testid="startup-template-controls"')
    expect(formSource).toContain("startup-template-preview-modal")
    expect(formSource).toContain(
      "playground:composer.startupTemplatePreviewTitle"
    )
    expect(formSource).toContain("resolveStartupTemplatePrompt")
    expect(contextPanelSource).toContain("playground:tokens.contextBreakdownTitle")
  })
})
