import { describe, expect, it } from "vitest"

import { resolveCompanionHomeWebMock } from "../companion-home.web-mocks"

describe("resolveCompanionHomeWebMock", () => {
  it("returns deterministic fixture responses for supported companion home endpoints", () => {
    const result = resolveCompanionHomeWebMock("GET", "/api/v1/companion/goals")

    expect(result.kind).toBe("matched")
    expect(result.response.status).toBe(200)
    expect(JSON.parse(result.response.body)).toMatchObject({
      items: [
        expect.objectContaining({
          id: "goal-1",
          title: "Finish queue review"
        })
      ]
    })
  })

  it("marks unknown api requests as unhandled instead of falling through to a live backend", () => {
    const result = resolveCompanionHomeWebMock("GET", "/api/v1/companion/unexpected")

    expect(result.kind).toBe("unhandled")
    expect(result.response.status).toBe(501)
    expect(JSON.parse(result.response.body)).toMatchObject({
      error: "Unhandled Companion Home parity request",
      method: "GET",
      pathname: "/api/v1/companion/unexpected"
    })
  })
})
