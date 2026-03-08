import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { MyChatIdentityMenu } from "../MyChatIdentityMenu"

describe("MyChatIdentityMenu", () => {
  it("keeps user identity controls separate from persona navigation", () => {
    const onDisplayName = vi.fn()
    const onImage = vi.fn()
    const onPromptTemplates = vi.fn()
    const onClearImage = vi.fn()

    render(
      <MyChatIdentityMenu
        displayNameLabel="Set your name"
        imageLabel="Upload your image"
        promptTemplatesLabel="Prompt style templates"
        clearImageLabel="Remove your image"
        onDisplayName={onDisplayName}
        onImage={onImage}
        onPromptTemplates={onPromptTemplates}
        onClearImage={onClearImage}
      />
    )

    expect(screen.getByRole("heading", { name: "My Chat Identity" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Set your name" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Upload your image" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Prompt style templates" })
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Remove your image" })).toBeInTheDocument()
    expect(screen.queryByText("Scope rules")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Set your name" }))
    fireEvent.click(screen.getByRole("button", { name: "Upload your image" }))
    fireEvent.click(screen.getByRole("button", { name: "Prompt style templates" }))
    fireEvent.click(screen.getByRole("button", { name: "Remove your image" }))

    expect(onDisplayName).toHaveBeenCalledTimes(1)
    expect(onImage).toHaveBeenCalledTimes(1)
    expect(onPromptTemplates).toHaveBeenCalledTimes(1)
    expect(onClearImage).toHaveBeenCalledTimes(1)
  })
})
