import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { SavedSearchesMenu } from "../SavedSearchesMenu"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

describe("SavedSearchesMenu", () => {
  it("applies a saved search when clicked", () => {
    const onApply = vi.fn()
    const onCreateFromCurrent = vi.fn()
    render(
      <SavedSearchesMenu
        searches={[
          {
            id: "search-1",
            name: "Daily AI",
            query: { q: "ai", status: ["saved"] },
            sort: "updated_desc"
          }
        ]}
        onApply={onApply}
        onCreateFromCurrent={onCreateFromCurrent}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Daily AI/i }))
    expect(onApply).toHaveBeenCalledTimes(1)
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ id: "search-1", name: "Daily AI" })
    )
  })

  it("calls create-from-current handler", () => {
    const onApply = vi.fn()
    const onCreateFromCurrent = vi.fn()
    render(
      <SavedSearchesMenu
        searches={[]}
        onApply={onApply}
        onCreateFromCurrent={onCreateFromCurrent}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Save current/i }))
    expect(onCreateFromCurrent).toHaveBeenCalledTimes(1)
  })
})

