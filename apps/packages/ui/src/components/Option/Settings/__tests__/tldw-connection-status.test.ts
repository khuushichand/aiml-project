import { describe, expect, it } from "vitest"
import {
  getCoreStatusLabel,
  getRagStatusLabel
} from "../tldw-connection-status"

const fallbackT = (_key: string, defaultValue: string) => defaultValue

describe("tldw connection status labels", () => {
  it("maps unknown statuses to explicit not-yet-checked copy", () => {
    expect(getCoreStatusLabel(fallbackT, "unknown")).toBe(
      "Core: not checked yet"
    )
    expect(getRagStatusLabel(fallbackT, "unknown")).toBe(
      "RAG: not checked yet"
    )
  })

  it("keeps explicit labels for active and terminal states", () => {
    expect(getCoreStatusLabel(fallbackT, "checking")).toBe("Core: checking…")
    expect(getCoreStatusLabel(fallbackT, "connected")).toBe("Core: reachable")
    expect(getCoreStatusLabel(fallbackT, "failed")).toBe("Core: unreachable")
    expect(getRagStatusLabel(fallbackT, "checking")).toBe("RAG: checking…")
    expect(getRagStatusLabel(fallbackT, "healthy")).toBe("RAG: healthy")
    expect(getRagStatusLabel(fallbackT, "unhealthy")).toBe(
      "RAG: needs attention"
    )
  })
})
