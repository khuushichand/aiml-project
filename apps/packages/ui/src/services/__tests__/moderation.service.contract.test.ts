import { beforeEach, describe, expect, it, vi } from "vitest"

import { getUserOverride } from "@/services/moderation"

const { bgRequestMock } = vi.hoisted(() => ({
  bgRequestMock: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: bgRequestMock
}))

describe("moderation service contracts", () => {
  beforeEach(() => {
    bgRequestMock.mockReset()
  })

  it("requests encoded user override path", async () => {
    bgRequestMock.mockResolvedValue({ exists: false, override: {} })

    await getUserOverride("user/one")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/moderation/users/user%2Fone",
      method: "GET"
    })
  })

  it("returns explicit existence metadata for missing override", async () => {
    bgRequestMock.mockResolvedValue({ exists: false, override: {} })

    const response = await getUserOverride("new-user")

    expect(response).toEqual({ exists: false, override: {} })
  })
})
