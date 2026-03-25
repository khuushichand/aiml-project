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
  it("keeps Playground and Sidepanel on the same shared dictation source path", () => {
    const playgroundVoiceChatPath = path.resolve(
      __dirname,
      "../hooks/usePlaygroundVoiceChat.ts"
    )
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundVoiceChatPath, "utf8")
    const sidepanelSource = fs.readFileSync(sidepanelFormPath, "utf8")

    expect(playgroundSource).toContain('useAudioSourcePreferences("dictation")')
    expect(sidepanelSource).toContain('useAudioSourcePreferences("dictation")')
    expect(playgroundSource).toContain("resolveAudioCapturePlan({")
    expect(sidepanelSource).toContain("resolveAudioCapturePlan({")
    expect(playgroundSource).toContain(
      'dictationModeOverride === "browser" && !browserDictationCompatible'
    )
    expect(sidepanelSource).toContain(
      'dictationModeOverride === "browser" && !browserDictationCompatible'
    )
    expect(playgroundSource).toContain('canUseServerStt ? ("server" as const) : ("unavailable" as const)')
    expect(sidepanelSource).toContain('canUseServerStt ? ("server" as const) : ("unavailable" as const)')
    expect(playgroundSource).toContain("resolvedModeOverride,")
    expect(sidepanelSource).toContain("resolvedModeOverride,")
    expect(playgroundSource).toContain("resolvedDictationSourcePreference.sourceKind")
    expect(sidepanelSource).toContain("resolvedDictationSourcePreference.sourceKind")
    expect(playgroundSource).toContain("audioInputDevices.some(")
    expect(sidepanelSource).toContain("audioInputDevices.some(")
    expect(playgroundSource).toContain("dictationSourceReady")
    expect(sidepanelSource).toContain("dictationSourceReady")
    expect(playgroundSource).toContain("pendingDictationStart")
    expect(sidepanelSource).toContain("pendingDictationStart")
    expect(playgroundSource).toContain("hasAudioCatalogSettled")
    expect(sidepanelSource).toContain("hasAudioCatalogSettled")

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
    expect(playgroundSource).toContain(
      "const snapshot = dictationDiagnosticsSnapshotRef.current"
    )
    expect(sidepanelSource).toContain(
      "const snapshot = dictationDiagnosticsSnapshotRef.current"
    )
    expect(playgroundSource).toContain("requestedSourceKind:")
    expect(playgroundSource).toContain("resolvedSourceKind:")
    expect(sidepanelSource).toContain("requestedSourceKind:")
    expect(sidepanelSource).toContain("resolvedSourceKind:")
  })

  it("routes dictation controls through unified toggle intent handlers in both forms", () => {
    const playgroundVoiceChatPath = path.resolve(
      __dirname,
      "../hooks/usePlaygroundVoiceChat.ts"
    )
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundVoiceChatPath, "utf8")
    const sidepanelSource = fs.readFileSync(sidepanelFormPath, "utf8")

    expect(playgroundSource).toContain("const handleDictationToggle = React.useCallback(() => {")
    expect(playgroundSource).toContain("switch (dictationToggleIntent)")
    expect(playgroundSource).toContain("startServerDictation(requestedServerDictationSource)")

    expect(sidepanelSource).toContain("const handleDictationToggle = React.useCallback(() => {")
    expect(sidepanelSource).toContain("switch (dictationStrategy.toggleIntent)")
    expect(sidepanelSource).toContain("startServerDictation(requestedServerDictationSource)")
  })

  it("keeps transcript insertion attached to the composer message in both forms", () => {
    const playgroundVoiceChatPath = path.resolve(
      __dirname,
      "../hooks/usePlaygroundVoiceChat.ts"
    )
    const sidepanelFormPath = resolveSidepanelFormPath()
    if (!sidepanelFormPath) {
      throw new Error("Unable to locate Sidepanel chat form source")
    }

    const playgroundSource = fs.readFileSync(playgroundVoiceChatPath, "utf8")
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
