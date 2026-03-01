import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ProviderSelector } from "../ProviderSelector"

describe("ProviderSelector", () => {
  it("renders dedicated local directory and zip pickers", () => {
    const noop = vi.fn()

    render(
      <ProviderSelector
        provider="local"
        githubUrl=""
        busy={false}
        onSelectProvider={noop}
        onGithubUrlChange={noop}
        onLoadGithub={noop}
        onLocalFilesSelected={noop}
      />
    )

    const directoryInput = screen.getByTestId("repo2txt-local-directory-input")
    const zipInput = screen.getByTestId("repo2txt-local-zip-input")

    expect(directoryInput).toHaveAttribute("webkitdirectory")
    expect(directoryInput).toHaveAttribute("multiple")
    expect(zipInput).toHaveAttribute("accept", ".zip,application/zip")
  })
})
