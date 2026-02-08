import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { GeneratedAnswerCard } from "../GeneratedAnswerCard"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

describe("GeneratedAnswerCard", () => {
  it("renders markdown content instead of plain raw markdown text", () => {
    render(
      <GeneratedAnswerCard
        answer={"# Answer Title\n\n- first bullet\n- second bullet"}
        onCopy={vi.fn()}
        onInsert={vi.fn()}
      />
    )

    expect(
      screen.getByRole("heading", { name: "Answer Title" })
    ).toBeInTheDocument()
    expect(screen.getByText("first bullet")).toBeInTheDocument()
    expect(screen.getByText("second bullet")).toBeInTheDocument()
  })

  it("does not render executable HTML from answer content", () => {
    const { container } = render(
      <GeneratedAnswerCard
        answer={"Safe text <script>alert('xss')</script>"}
        onCopy={vi.fn()}
        onInsert={vi.fn()}
      />
    )

    expect(container.querySelector("script")).toBeNull()
    expect(container.textContent).toContain("Safe text <script>alert('xss')</script>")
  })
})
