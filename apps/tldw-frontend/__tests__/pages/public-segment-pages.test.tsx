import { afterEach, describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import ResearchersPage from "@web/pages/for/researchers"
import JournalistsPage from "@web/pages/for/journalists"
import OSINTPage from "@web/pages/for/osint"

const ORIGINAL_DEPLOYMENT_MODE =
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE

const setHostedMode = (): void => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
}

const restoreDeploymentMode = (): void => {
  if (ORIGINAL_DEPLOYMENT_MODE === undefined) {
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  } else {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = ORIGINAL_DEPLOYMENT_MODE
  }
}

afterEach(() => {
  restoreDeploymentMode()
})

describe("public segment pages", () => {
  it("keeps the researchers page on the self-host path even when hosted mode is set", () => {
    setHostedMode()

    render(<ResearchersPage />)

    expect(screen.queryByText("Start Hosted Trial")).not.toBeInTheDocument()
    expect(screen.queryByText("Researcher Pro")).not.toBeInTheDocument()
    expect(screen.queryByText("Lab License")).not.toBeInTheDocument()
    expect(screen.getByText(/start self-hosting free/i)).toBeInTheDocument()
  })

  it("keeps the journalists page on the self-host path even when hosted mode is set", () => {
    setHostedMode()

    render(<JournalistsPage />)

    expect(screen.queryByText("Start Hosted Trial")).not.toBeInTheDocument()
    expect(screen.queryByText("Cloud Pro")).not.toBeInTheDocument()
    expect(screen.queryByText("Newsroom")).not.toBeInTheDocument()
    expect(screen.getByText(/start self-hosting free/i)).toBeInTheDocument()
  })

  it("keeps the osint page on the self-host path even when hosted mode is set", () => {
    setHostedMode()

    render(<OSINTPage />)

    expect(screen.queryByText("Start Hosted Evaluation")).not.toBeInTheDocument()
    expect(screen.queryByText("Professional")).not.toBeInTheDocument()
    expect(screen.queryByText("Enterprise")).not.toBeInTheDocument()
    expect(screen.getByText(/deploy self-hosted/i)).toBeInTheDocument()
  })
})
