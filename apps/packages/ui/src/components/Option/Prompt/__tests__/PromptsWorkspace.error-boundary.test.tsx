import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { PromptsWorkspace } from "../PromptsWorkspace"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || ""
      }
      return ""
    }
  })
}))

vi.mock("..", () => ({
  PromptBody: () => {
    throw new Error("prompt body crash")
  }
}))

describe("PromptsWorkspace error boundary integration", () => {
  it("renders Prompts page fallback when PromptBody throws", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

    render(<PromptsWorkspace />)
    expect(await screen.findByTestId("prompts-error-boundary")).toBeInTheDocument()

    consoleSpy.mockRestore()
  })
})
