import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { QuizMarkdown } from "../QuizMarkdown"

describe("QuizMarkdown", () => {
  it("renders markdown formatting and hardened links", () => {
    render(
      <QuizMarkdown content={"**Bold text** and [Reference](https://example.com)"} />
    )

    expect(screen.getByText("Bold text")).toBeInTheDocument()
    const link = screen.getByRole("link", { name: "Reference" })
    expect(link).toHaveAttribute("href", "https://example.com")
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("does not render raw html tags as executable dom nodes", () => {
    const { container } = render(
      <QuizMarkdown content={"Question text <script>alert('xss')</script>"} />
    )

    expect(container.querySelector("script")).toBeNull()
    expect(screen.getByText(/Question text/)).toBeInTheDocument()
  })
})

