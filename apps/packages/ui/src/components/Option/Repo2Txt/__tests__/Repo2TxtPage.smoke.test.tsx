import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Repo2TxtPage } from "../Repo2TxtPage"

describe("Repo2TxtPage", () => {
  it("shows provider panel and output panel placeholders", () => {
    render(<Repo2TxtPage />)
    expect(screen.getByTestId("repo2txt-provider-panel")).toBeInTheDocument()
    expect(screen.getByTestId("repo2txt-output-panel")).toBeInTheDocument()
  })
})
