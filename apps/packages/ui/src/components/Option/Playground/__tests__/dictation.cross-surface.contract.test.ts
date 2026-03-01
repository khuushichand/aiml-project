import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const resolveSidepanelFormPath = () => {
  const candidates = [
    path.resolve(__dirname, "../../Sidepanel/Chat/form.tsx"),
    path.resolve(process.cwd(), "src/components/Sidepanel/Chat/form.tsx"),
    path.resolve(
      process.cwd(),
      "../packages/ui/src/components/Sidepanel/Chat/form.tsx"
    ),
    path.resolve(
      process.cwd(),
      "apps/packages/ui/src/components/Sidepanel/Chat/form.tsx"
    )
  ]
  return candidates.find((candidate) => fs.existsSync(candidate))
}

describe("dictation cross-surface contract", () => {
  it("keeps Playground and Sidepanel on the same shared dictation path", () => {
    const playgroundFormPath = path.resolve(__dirname, "../PlaygroundForm.tsx")
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundFormPath, "utf8")
    const sidepanelSource = fs.readFileSync(sidepanelFormPath, "utf8")

    expect(playgroundSource).toContain("useServerDictation({")
    expect(sidepanelSource).toContain("useServerDictation({")
    expect(playgroundSource).toContain("useDictationStrategy({")
    expect(sidepanelSource).toContain("useDictationStrategy({")

    expect(playgroundSource).toContain(
      "serverDictationErrorBridgeRef.current = dictationStrategy.recordServerError"
    )
    expect(playgroundSource).toContain(
      "serverDictationSuccessBridgeRef.current = dictationStrategy.recordServerSuccess"
    )
    expect(sidepanelSource).toContain(
      "serverDictationErrorBridgeRef.current = dictationStrategy.recordServerError"
    )
    expect(sidepanelSource).toContain(
      "serverDictationSuccessBridgeRef.current = dictationStrategy.recordServerSuccess"
    )
  })

  it("routes dictation controls through unified toggle intent handlers in both forms", () => {
    const playgroundFormPath = path.resolve(__dirname, "../PlaygroundForm.tsx")
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundFormPath, "utf8")
    const sidepanelSource = fs.readFileSync(sidepanelFormPath, "utf8")

    expect(playgroundSource).toContain("const handleDictationToggle = React.useCallback(() => {")
    expect(playgroundSource).toContain("switch (dictationToggleIntent)")
    expect(playgroundSource).toContain("onDictationToggle={handleDictationToggle}")
    expect(playgroundSource).toContain("onSelectDictation={handleDictationToggle}")
    expect(playgroundSource).not.toContain(
      "speechUsesServer ? handleServerDictationToggle : handleSpeechToggle"
    )

    expect(sidepanelSource).toContain("const handleDictationToggle = React.useCallback(() => {")
    expect(sidepanelSource).toContain("switch (dictationStrategy.toggleIntent)")
    expect(sidepanelSource).toContain("onClick={handleDictationToggle}")
    expect(sidepanelSource).not.toContain(
      "speechUsesServer ? startServerDictation : handleSpeechToggle"
    )
  })

  it("keeps transcript insertion attached to the composer message in both forms", () => {
    const playgroundFormPath = path.resolve(__dirname, "../PlaygroundForm.tsx")
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundFormPath, "utf8")
    const sidepanelSource = fs.readFileSync(sidepanelFormPath, "utf8")

    expect(playgroundSource).toContain("onTranscript: (text) => {")
    expect(playgroundSource).toContain(
      "setMessageValue(text, { collapseLarge: true, forceCollapse: true })"
    )
    expect(sidepanelSource).toContain(
      'onTranscript: (text) => form.setFieldValue("message", text)'
    )
  })
})
