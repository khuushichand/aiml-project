import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readPlaygroundFormSource = () =>
  fs.readFileSync(path.resolve(__dirname, "../PlaygroundForm.tsx"), "utf8")

const extractDestructureBlock = (source: string, assignee: string) => {
  const assignmentMarker = `} = ${assignee}`
  const assignmentIndex = source.indexOf(assignmentMarker)
  expect(assignmentIndex).toBeGreaterThan(-1)

  const declarationStart = source.lastIndexOf("const {", assignmentIndex)
  expect(declarationStart).toBeGreaterThan(-1)

  return source.slice(declarationStart, assignmentIndex)
}

describe("PlaygroundForm compare/settings guard", () => {
  it("keeps compare notice bindings owned by settingsHook instead of modelComparison", () => {
    const formSource = readPlaygroundFormSource()
    const modelComparisonBlock = extractDestructureBlock(
      formSource,
      "modelComparison"
    )
    const settingsHookBlock = extractDestructureBlock(formSource, "settingsHook")

    expect(modelComparisonBlock).not.toContain("compareHasPromptContext")
    expect(modelComparisonBlock).not.toContain("compareSharedContextLabels")
    expect(modelComparisonBlock).not.toContain(
      "compareInteroperabilityNotices"
    )

    expect(settingsHookBlock).toContain("compareSharedContextLabels")
    expect(settingsHookBlock).toContain("compareInteroperabilityNotices")
    expect(settingsHookBlock).toContain("contextConflictWarnings")
  })
})
