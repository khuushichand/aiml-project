import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("AppProviders imports", () => {
  it("loads NotificationToastBridge from the web app alias", () => {
    const source = readFileSync(
      path.join(process.cwd(), "components", "AppProviders.tsx"),
      "utf8"
    )

    expect(source).toContain(
      'from "@web/components/notifications/NotificationToastBridge"'
    )
  })
})
