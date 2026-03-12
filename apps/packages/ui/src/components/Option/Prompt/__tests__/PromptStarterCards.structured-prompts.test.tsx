import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { PromptStarterCards } from "../PromptStarterCards"

describe("PromptStarterCards structured templates", () => {
  it("emits a structured starter prompt with preconfigured blocks", () => {
    const onUse = vi.fn()
    render(<PromptStarterCards onUse={onUse} />)

    fireEvent.click(
      screen.getByTestId("starter-use-code-review-assistant")
    )

    expect(onUse).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Code Review Assistant",
        promptFormat: "structured",
        structuredPromptDefinition: expect.objectContaining({
          format: "structured",
          blocks: expect.arrayContaining([
            expect.objectContaining({ role: "system" }),
            expect.objectContaining({ role: "developer" }),
            expect.objectContaining({ role: "user" })
          ]),
          variables: expect.arrayContaining([
            expect.objectContaining({ name: "code", required: true })
          ])
        })
      })
    )
  })
})
