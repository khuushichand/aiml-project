import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { BookOpen } from "lucide-react"
import { TabIconLabel } from "../TabIconLabel"

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("TabIconLabel", () => {
  it("renders visible text and aria label for icon-first tabs", () => {
    render(<TabIconLabel label="References" icon={<BookOpen className="h-4 w-4" />} />)

    expect(screen.getByText("References")).toBeInTheDocument()
    expect(screen.getByLabelText("References")).toBeInTheDocument()
  })
})
