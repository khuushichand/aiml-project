import { describe, expect, it, vi } from "vitest"
import type { ContentSection } from "@/components/Review/SectionNavigator"
import { scrollSectionIntoView } from "@/components/Review/reading-pane-section-navigation"

describe("scrollSectionIntoView", () => {
  it("prefers a matching section anchor over the first duplicate heading text", () => {
    const contentRoot = document.createElement("div")

    const firstHeading = document.createElement("h2")
    firstHeading.textContent = "Repeated Title"
    firstHeading.scrollIntoView = vi.fn()

    const secondHeading = document.createElement("h2")
    secondHeading.textContent = "Repeated Title"
    secondHeading.setAttribute("data-section-anchor", "section-4")
    secondHeading.scrollIntoView = vi.fn()

    contentRoot.append(firstHeading, secondHeading)

    const section: ContentSection = {
      id: "section-4",
      label: "Repeated Title",
      offset: 42
    }

    const scrolled = scrollSectionIntoView(contentRoot, section)

    expect(scrolled).toBe(true)
    expect(secondHeading.scrollIntoView).toHaveBeenCalledTimes(1)
    expect(firstHeading.scrollIntoView).not.toHaveBeenCalled()
  })
})
