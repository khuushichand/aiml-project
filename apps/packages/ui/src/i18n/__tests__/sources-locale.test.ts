import { describe, expect, it } from "vitest"

import { en } from "@/i18n/lang/en"

describe("sources locale wiring", () => {
  it("registers the english sources namespace and nav label", () => {
    expect((en as any).sources.title).toBe("Sources")
    expect((en as any).option.header.sources).toBe("Sources")
  })
})
