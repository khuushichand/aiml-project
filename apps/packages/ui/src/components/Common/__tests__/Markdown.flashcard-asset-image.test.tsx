import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const acquireFlashcardAssetObjectUrl = vi.hoisted(() => vi.fn())
const releaseFlashcardAssetObjectUrl = vi.hoisted(() => vi.fn())

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultValue: unknown) =>
    React.useState(defaultValue)
}))

vi.mock("@/services/flashcard-assets", () => ({
  acquireFlashcardAssetObjectUrl,
  releaseFlashcardAssetObjectUrl
}))

import Markdown from "../Markdown"

describe("Markdown flashcard asset images", () => {
  beforeEach(() => {
    acquireFlashcardAssetObjectUrl.mockReset()
    releaseFlashcardAssetObjectUrl.mockReset()
  })

  it("renders managed flashcard images via authenticated object URLs", async () => {
    acquireFlashcardAssetObjectUrl.mockResolvedValue("blob:asset-1")

    const { unmount } = render(
      <Markdown message="Before ![Slide](flashcard-asset://asset-1) after" />
    )

    const image = await screen.findByRole("img", { name: "Slide" })
    expect(image).toHaveAttribute("src", "blob:asset-1")
    expect(acquireFlashcardAssetObjectUrl).toHaveBeenCalledWith("asset-1")

    unmount()

    expect(releaseFlashcardAssetObjectUrl).toHaveBeenCalledWith("asset-1")
  })

  it("shows an inline fallback when a managed image cannot be resolved", async () => {
    acquireFlashcardAssetObjectUrl.mockRejectedValue(new Error("boom"))

    render(<Markdown message="![Broken](flashcard-asset://asset-404)" />)

    await waitFor(() => {
      expect(screen.getByText("Image unavailable: Broken")).toBeInTheDocument()
    })
  })
})
