import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const testFileDirectory = dirname(fileURLToPath(import.meta.url))
const pagePath = resolve(testFileDirectory, "../../pages/chat-workflows.tsx")

describe("web chat workflows page route", () => {
  it("exposes a Next.js page shim for chat workflows", () => {
    expect(existsSync(pagePath)).toBe(true)

    const source = readFileSync(pagePath, "utf8")

    expect(source).toMatch(/dynamic\(\(\) => import\("@\/routes\/option-chat-workflows"\)/)
    expect(source).toMatch(/ssr:\s*false/)
  })
})
