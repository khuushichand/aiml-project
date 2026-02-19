import { describe, expect, it } from "vitest"
import {
  findInvalidEmailRecipients,
  isValidEmailAddress,
  normalizeEmailAddress
} from "../email-utils"

describe("email recipient validation", () => {
  it("normalizes addresses before validation", () => {
    expect(normalizeEmailAddress("  USER@Example.COM ")).toBe("user@example.com")
  })

  it("accepts and rejects representative addresses", () => {
    expect(isValidEmailAddress("alerts@example.com")).toBe(true)
    expect(isValidEmailAddress("alerts+ops@example.co.uk")).toBe(true)
    expect(isValidEmailAddress("invalid-address")).toBe(false)
    expect(isValidEmailAddress("missing-domain@")).toBe(false)
  })

  it("returns only invalid recipients from a list", () => {
    expect(
      findInvalidEmailRecipients([
        "alerts@example.com",
        "ops@example.org",
        "not-an-email",
        "missing-domain@"
      ])
    ).toEqual(["not-an-email", "missing-domain@"])
  })
})
