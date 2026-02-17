import React from "react"
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { StatusBanner } from "../StatusBanner"

describe("StatusBanner", () => {
  it("sanitizes user-facing admin error details", () => {
    render(
      <StatusBanner
        state="inactive"
        error="Request failed: 503 (GET /api/v1/admin/mlx/status) config=/Users/dev/.config/tldw/config.txt"
      />
    )

    expect(screen.getByText("Status Error")).toBeTruthy()
    const fullText = document.body.textContent || ""
    expect(fullText).toContain("[admin-endpoint]")
    expect(fullText).toContain("[redacted-path]")
    expect(fullText).not.toContain("/api/v1/admin/mlx/status")
    expect(fullText).not.toContain("/Users/dev/.config/tldw/config.txt")
  })
})
