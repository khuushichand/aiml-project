import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { InlineSettingsPanel } from "../InlineSettingsPanel"

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultVal: unknown) => [defaultVal, vi.fn()]
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, f: string) => f })
}))

describe("InlineSettingsPanel", () => {
  it("renders language, task, and format controls", () => {
    const onChange = vi.fn()
    render(<InlineSettingsPanel onChange={onChange} />)

    expect(screen.getByLabelText("Language")).toBeInTheDocument()
    expect(screen.getByLabelText("Task")).toBeInTheDocument()
    expect(screen.getByLabelText("Format")).toBeInTheDocument()
  })

  it("hides segmentation params when segmentation is disabled", () => {
    const onChange = vi.fn()
    render(<InlineSettingsPanel onChange={onChange} />)

    // Default useSegmentation is false, so segmentation fields should not appear
    expect(screen.queryByLabelText("K")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Min segment size")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Lambda balance")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Expansion width")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Embeddings provider")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Embeddings model")).not.toBeInTheDocument()
  })

  it("shows reset to defaults button", () => {
    const onChange = vi.fn()
    render(<InlineSettingsPanel onChange={onChange} />)

    expect(
      screen.getByRole("button", { name: /reset to defaults/i })
    ).toBeInTheDocument()
  })
})
