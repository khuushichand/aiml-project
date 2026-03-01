import { readFileSync } from "node:fs"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import OptionRepo2TxtRoute from "../option-repo2txt"

describe("repo2txt option route", () => {
  it("renders repo2txt route root", async () => {
    render(<OptionRepo2TxtRoute />)
    expect(await screen.findByTestId("repo2txt-route-root")).toBeInTheDocument()
  })

  it("registers /repo2txt in route registry", () => {
    const routeRegistrySource = readFileSync("src/routes/route-registry.tsx", "utf8")
    expect(routeRegistrySource).toContain('path: REPO2TXT_PATH')
  })
})
