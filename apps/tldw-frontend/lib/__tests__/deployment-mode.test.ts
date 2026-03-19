import { afterEach, describe, expect, it } from "vitest"

import {
  getDeploymentMode,
  isHostedSaaSMode
} from "@web/lib/deployment-mode"

const ORIGINAL_DEPLOYMENT_MODE =
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE

describe("deployment mode", () => {
  afterEach(() => {
    if (ORIGINAL_DEPLOYMENT_MODE === undefined) {
      delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
    } else {
      process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = ORIGINAL_DEPLOYMENT_MODE
    }
  })

  it("defaults to self_host when no hosted env is present", () => {
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE

    expect(getDeploymentMode()).toBe("self_host")
    expect(isHostedSaaSMode()).toBe(false)
  })

  it("returns hosted for NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=hosted", () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"

    expect(getDeploymentMode()).toBe("hosted")
    expect(isHostedSaaSMode()).toBe(true)
  })
})
