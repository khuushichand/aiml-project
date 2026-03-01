import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { Repo2TxtPage } from "../Repo2TxtPage"

describe("Repo2TxtPage flow", () => {
  it("keeps Generate disabled until a source is loaded", async () => {
    render(<Repo2TxtPage />)
    const generate = screen.getByRole("button", { name: /generate output/i })
    expect(generate).toBeDisabled()
    await userEvent.click(screen.getByRole("button", { name: /github/i }))
    expect(generate).toBeDisabled()
  })
})
