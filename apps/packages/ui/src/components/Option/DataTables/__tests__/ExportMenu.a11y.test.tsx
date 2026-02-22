import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ExportMenu } from "../ExportMenu"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue ?? _key
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    exportDataTable: vi.fn()
  }
}))

vi.mock("@/utils/download-blob", () => ({
  downloadBlob: vi.fn()
}))

describe("ExportMenu accessibility", () => {
  it("uses labeled controls with mobile-safe touch target sizing", () => {
    render(<ExportMenu tableId="table-1" tableName="Demo table" />)

    const button = screen.getByRole("button", { name: "Export" })
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass("min-h-[44px]")
    expect(button).toHaveClass("min-w-[44px]")
  })
})
