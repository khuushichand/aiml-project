import { readFileSync } from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

const appDir = path.resolve(__dirname, "..")
const repoRoot = path.resolve(appDir, "..", "..")
const nextConfigPath = path.join(appDir, "next.config.mjs")
const validateNetworkingConfigPath = path.join(
  appDir,
  "scripts",
  "validate-networking-config.mjs"
)
const makefilePath = path.join(repoRoot, "Makefile")

const ORIGINAL_ENV = {
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
  TLDW_INTERNAL_API_ORIGIN: process.env.TLDW_INTERNAL_API_ORIGIN,
}

const restoreEnv = () => {
  if (ORIGINAL_ENV.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE === undefined) {
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  } else {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE =
      ORIGINAL_ENV.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  }

  if (ORIGINAL_ENV.TLDW_INTERNAL_API_ORIGIN === undefined) {
    delete process.env.TLDW_INTERNAL_API_ORIGIN
  } else {
    process.env.TLDW_INTERNAL_API_ORIGIN = ORIGINAL_ENV.TLDW_INTERNAL_API_ORIGIN
  }
}

const loadNextConfig = async (env: {
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE?: string
  TLDW_INTERNAL_API_ORIGIN?: string
}) => {
  if (env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE === undefined) {
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  } else {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE =
      env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  }

  if (env.TLDW_INTERNAL_API_ORIGIN === undefined) {
    delete process.env.TLDW_INTERNAL_API_ORIGIN
  } else {
    process.env.TLDW_INTERNAL_API_ORIGIN = env.TLDW_INTERNAL_API_ORIGIN
  }

  const moduleUrl = pathToFileURL(nextConfigPath)
  moduleUrl.searchParams.set("t", `${Date.now()}-${Math.random()}`)
  const mod = await import(moduleUrl.href)
  return mod.default
}

const loadValidateNetworkingConfig = async () => {
  const moduleUrl = pathToFileURL(validateNetworkingConfigPath)
  moduleUrl.searchParams.set("t", `${Date.now()}-${Math.random()}`)
  const mod = await import(moduleUrl.href)
  return mod.validateNetworkingConfig as (env?: Record<string, string | undefined>) => {
    deploymentMode: string
    internalApiOrigin: string
    publicApiUrl: string
  }
}

describe("frontend quickstart networking", () => {
  beforeEach(() => {
    restoreEnv()
  })

  afterEach(() => {
    restoreEnv()
  })

  it("adds a quickstart same-origin proxy rewrite for /api/:path*", async () => {
    const nextConfig = await loadNextConfig({
      NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart",
      TLDW_INTERNAL_API_ORIGIN: "http://app:8000",
    })

    expect(nextConfig.rewrites).toEqual(expect.any(Function))

    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual(
      expect.arrayContaining([
        {
          source: "/api/:path*",
          destination: "http://app:8000/api/:path*",
        },
      ])
    )
  })

  it("requires TLDW_INTERNAL_API_ORIGIN in quickstart mode", async () => {
    const validateNetworkingConfig = await loadValidateNetworkingConfig()

    expect(() =>
      validateNetworkingConfig({
        NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart",
        TLDW_INTERNAL_API_ORIGIN: "",
      })
    ).toThrow(/TLDW_INTERNAL_API_ORIGIN/i)
  })

  it("does not add the quickstart proxy rewrite outside quickstart mode", async () => {
    const nextConfig = await loadNextConfig({
      NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "advanced",
      TLDW_INTERNAL_API_ORIGIN: "http://app:8000",
    })

    const rewrites = await nextConfig.rewrites()

    expect(rewrites).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "/api/:path*",
          destination: "http://app:8000/api/:path*",
        }),
      ])
    )
  })

  it("normalizes a trailing slash from the internal quickstart API origin", async () => {
    const nextConfig = await loadNextConfig({
      NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: "quickstart",
      TLDW_INTERNAL_API_ORIGIN: "http://app:8000/",
    })

    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual(
      expect.arrayContaining([
        {
          source: "/api/:path*",
          destination: "http://app:8000/api/:path*",
        },
      ])
    )
  })

  it("defaults quickstart Makefile wiring to quickstart deployment mode", () => {
    const makefile = readFileSync(makefilePath, "utf8")

    expect(makefile).toContain(
      "NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE ?= quickstart"
    )
    expect(makefile).toContain("TLDW_INTERNAL_API_ORIGIN ?= http://app:8000")
  })
})
