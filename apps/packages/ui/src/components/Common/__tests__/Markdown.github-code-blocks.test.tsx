import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import Markdown from "../Markdown"

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultValue: unknown) =>
    React.useState(defaultValue)
}))

describe("Markdown github code block variant", () => {
  it("renders fenced text and python blocks as inline markdown code sections", () => {
    const markdown = [
      "```text",
      "plaintext here",
      "```",
      "",
      "```python",
      "python_code = 1",
      "```"
    ].join("\n")

    const { container } = render(
      <Markdown message={markdown} codeBlockVariant="github" />
    )

    expect(screen.getByText("plaintext here")).toBeInTheDocument()
    expect(screen.getByText("python_code")).toBeInTheDocument()
    expect(container.querySelectorAll("pre")).toHaveLength(2)
  })
})
