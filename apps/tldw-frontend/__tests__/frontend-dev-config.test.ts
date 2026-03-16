import { readFileSync } from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { describe, expect, it } from "vitest"

const appDir = path.resolve(__dirname, "..")

const loadNextConfig = async () => {
  const moduleUrl = pathToFileURL(path.join(appDir, "next.config.mjs")).href
  const mod = await import(moduleUrl)
  return mod.default
}

describe("frontend dev config", () => {
  it("allows localhost loopback dev origins", async () => {
    const nextConfig = await loadNextConfig()

    expect(nextConfig.allowedDevOrigins).toEqual(
      expect.arrayContaining(["localhost", "127.0.0.1"])
    )
  })

  it("provides a webpack dev fallback script", () => {
    const packageJson = JSON.parse(
      readFileSync(path.join(appDir, "package.json"), "utf8")
    ) as {
      scripts?: Record<string, string>
    }

    expect(packageJson.scripts?.["dev:webpack"]).toBe("next dev --webpack")
  })
})
