import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing system settings source: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("system settings code preview", () => {
  it("passes Prism keys directly instead of spreading them through JSX props", () => {
    const source = loadSource(
      "src/components/Option/Settings/system-settings.tsx",
      "apps/packages/ui/src/components/Option/Settings/system-settings.tsx"
    )

    expect(source).toContain('key={i}')
    expect(source).toContain('key={key}')
    expect(source).not.toContain('getLineProps({ line, key: i })')
    expect(source).not.toContain('getTokenProps({ token, key })')
  })
})
