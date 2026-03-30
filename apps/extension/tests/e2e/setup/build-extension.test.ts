import fs from "node:fs"
import path from "node:path"

import { afterEach, describe, expect, it, vi } from "vitest"

const realReadFileSync = fs.readFileSync
const realExistsSync = fs.existsSync
const realStatSync = fs.statSync

afterEach(() => {
  vi.resetModules()
  vi.restoreAllMocks()
})

describe("extension playwright globalSetup", () => {
  it("skips rebuilding when a non-dev .output chrome build already exists", async () => {
    const execSync = vi.fn()
    vi.doMock("node:child_process", () => ({
      execSync
    }))

    const moduleUrl = new URL(import.meta.url)
    const setupDir = path.dirname(moduleUrl.pathname)
    const projectRoot = path.resolve(setupDir, "..", "..", "..")
    const outputChromePath = path.resolve(projectRoot, ".output/chrome-mv3")
    const outputManifestPath = path.join(outputChromePath, "manifest.json")
    const outputBackgroundPath = path.join(outputChromePath, "background.js")
    const outputOptionsPath = path.join(outputChromePath, "options.html")

    vi.spyOn(fs, "existsSync").mockImplementation((targetPath) => {
      const normalized = String(targetPath)
      if (normalized === outputChromePath) return true
      if (normalized === outputManifestPath) return true
      if (normalized === outputBackgroundPath) return true
      if (normalized === outputOptionsPath) return true
      return realExistsSync(targetPath)
    })

    vi.spyOn(fs, "readFileSync").mockImplementation((targetPath, options) => {
      if (String(targetPath) === outputOptionsPath) {
        return "<html><body>production build</body></html>" as any
      }
      return realReadFileSync(targetPath as any, options as any)
    })

    vi.spyOn(fs, "statSync").mockImplementation((targetPath, options) => {
      if (String(targetPath) === outputManifestPath) {
        return {
          mtimeMs: Date.now()
        } as fs.Stats
      }
      return realStatSync(targetPath as any, options as any)
    })

    vi.spyOn(fs, "readdirSync").mockImplementation(() => [])

    const globalSetup = (await import("./build-extension")).default

    await globalSetup()

    expect(execSync).not.toHaveBeenCalled()
  })

  it("prefers a valid .output build over an invalid build/chrome-mv3 directory", async () => {
    const execSync = vi.fn()
    vi.doMock("node:child_process", () => ({
      execSync
    }))

    const moduleUrl = new URL(import.meta.url)
    const setupDir = path.dirname(moduleUrl.pathname)
    const projectRoot = path.resolve(setupDir, "..", "..", "..")
    const buildChromePath = path.resolve(projectRoot, "build/chrome-mv3")
    const outputChromePath = path.resolve(projectRoot, ".output/chrome-mv3")
    const outputManifestPath = path.join(outputChromePath, "manifest.json")
    const outputBackgroundPath = path.join(outputChromePath, "background.js")
    const outputOptionsPath = path.join(outputChromePath, "options.html")

    vi.spyOn(fs, "existsSync").mockImplementation((targetPath) => {
      const normalized = String(targetPath)
      if (normalized === buildChromePath) return true
      if (normalized === outputChromePath) return true
      if (normalized === outputManifestPath) return true
      if (normalized === outputBackgroundPath) return true
      if (normalized === outputOptionsPath) return true
      return realExistsSync(targetPath)
    })

    vi.spyOn(fs, "readFileSync").mockImplementation((targetPath, options) => {
      if (String(targetPath) === outputOptionsPath) {
        return "<html><body>production build</body></html>" as any
      }
      return realReadFileSync(targetPath as any, options as any)
    })

    vi.spyOn(fs, "statSync").mockImplementation((targetPath, options) => {
      if (String(targetPath) === outputManifestPath) {
        return {
          mtimeMs: Date.now()
        } as fs.Stats
      }
      return realStatSync(targetPath as any, options as any)
    })

    vi.spyOn(fs, "readdirSync").mockImplementation(() => [])

    const globalSetup = (await import("./build-extension")).default

    await globalSetup()

    expect(execSync).not.toHaveBeenCalled()
  })
})
