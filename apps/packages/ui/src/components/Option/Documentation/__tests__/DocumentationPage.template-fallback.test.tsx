import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import DocumentationPage from "../DocumentationPage"
import { vi } from "vitest"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValue?: string,
      options?: Record<string, unknown>
    ) => {
      const template = defaultValue ?? key
      if (!options) return template
      return template.replace(/\{\{\s*([^}]+)\s*\}\}/g, (_, rawKey: string) => {
        const token = rawKey.trim()
        const value = options[token]
        return value == null ? `{{${token}}}` : String(value)
      })
    }
  })
}))

vi.mock("@/components/Common/Markdown", () => ({
  default: ({ message }: { message: string }) => <div>{message}</div>
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("DocumentationPage template fallback", () => {
  it("renders resolved fallback copy instead of raw template variables", async () => {
    const { container } = render(<DocumentationPage />)

    expect(
      screen.getByText(
        "Sources: Docs/User_Documentation and Docs/Published"
      )
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(container.textContent || "").toContain(
        "Add markdown files under Docs/User_Documentation to populate this section."
      )
    })

    expect(
      screen.getByRole("tab", { name: /tldw browser extension \(1\)/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("tab", { name: /tldw_server \(1\)/i })
    ).toBeInTheDocument()

    const text = container.textContent || ""
    expect(text).not.toContain("{{path}}")
    expect(text).not.toContain("{{extensionPath}}")
    expect(text).not.toContain("{{serverPath}}")
  })
})
