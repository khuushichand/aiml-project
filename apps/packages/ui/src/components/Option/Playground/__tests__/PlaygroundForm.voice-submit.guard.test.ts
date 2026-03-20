import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readPlaygroundFormSource = () =>
  fs.readFileSync(path.resolve(__dirname, "../PlaygroundForm.tsx"), "utf8")

describe("PlaygroundForm voice submit guard", () => {
  it("routes voice chat submit through a bridge ref instead of the raw submitForm binding", () => {
    const source = readPlaygroundFormSource()
    const blockStart = source.indexOf("const voiceChatHook = usePlaygroundVoiceChat({")
    const blockEnd = source.indexOf("  const {\n    isListening,", blockStart)

    expect(blockStart).toBeGreaterThan(-1)
    expect(blockEnd).toBeGreaterThan(blockStart)

    const voiceChatBlock = source.slice(blockStart, blockEnd)

    expect(source).toContain(
      "const voiceChatSubmitFormRef = React.useRef<() => void>(() => undefined)"
    )
    expect(voiceChatBlock).toContain(
      "submitForm: () => voiceChatSubmitFormRef.current()"
    )
    expect(voiceChatBlock).not.toContain("\n    submitForm,\n")
  })

  it("syncs the voice chat submit bridge after initializing the submit hook", () => {
    const source = readPlaygroundFormSource()

    expect(source).toContain("voiceChatSubmitFormRef.current = () => {")
    expect(source).toContain("submitForm()")
  })
})
