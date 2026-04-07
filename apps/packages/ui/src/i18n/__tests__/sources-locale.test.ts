import { describe, expect, it } from "vitest"

import i18n, { ensureI18nNamespaces } from "@/i18n"
import option from "@/assets/locale/en/option.json"

describe("sources locale wiring", () => {
  it("loads shared and route-local english namespaces on demand", async () => {
    i18n.removeResourceBundle("en", "common")
    i18n.removeResourceBundle("en", "sources")

    expect(i18n.hasResourceBundle("en", "common")).toBe(false)
    expect(i18n.hasResourceBundle("en", "sources")).toBe(false)

    await ensureI18nNamespaces(["common"], "en")
    expect(i18n.hasResourceBundle("en", "common")).toBe(true)
    expect((i18n.getResourceBundle("en", "common") as any).noData).toBe("No data")

    await ensureI18nNamespaces(["sources"], "en")
    expect(i18n.hasResourceBundle("en", "sources")).toBe(true)
    expect((i18n.getResourceBundle("en", "sources") as any).title).toBe("Sources")
    expect((option as any).header.sources).toBe("Sources")
  })
})
