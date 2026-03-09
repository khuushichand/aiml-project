import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const hookMocks = vi.hoisted(() => ({
  useCreateIngestionSourceMutation: vi.fn(),
  useUpdateIngestionSourceMutation: vi.fn()
}))

const routerMocks = vi.hoisted(() => ({
  navigate: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useNavigate: () => routerMocks.navigate
  }
})

vi.mock("@/hooks/use-ingestion-sources", () => ({
  useCreateIngestionSourceMutation: (...args: unknown[]) =>
    hookMocks.useCreateIngestionSourceMutation(...args),
  useUpdateIngestionSourceMutation: (...args: unknown[]) =>
    hookMocks.useUpdateIngestionSourceMutation(...args)
}))

import { SourceForm } from "@/components/Option/Sources/SourceForm"

describe("SourceForm", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    hookMocks.useCreateIngestionSourceMutation.mockReturnValue({
      mutateAsync: vi.fn(async () => ({ id: "42" })),
      isPending: false
    })
    hookMocks.useUpdateIngestionSourceMutation.mockReturnValue({
      mutateAsync: vi.fn(async () => ({ id: "42" })),
      isPending: false
    })
  })

  it("switches fields between local directory and archive source modes", async () => {
    render(<SourceForm mode="create" />)

    expect(screen.getByLabelText("Server directory path")).toBeInTheDocument()
    expect(
      screen.getByText(/path on the tldw server host, not a local browser or extension folder/i)
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "Archive snapshot" }))

    await waitFor(() => {
      expect(screen.queryByLabelText("Server directory path")).not.toBeInTheDocument()
    })
    expect(screen.getByText("Upload archive after creation")).toBeInTheDocument()
  })

  it("renders inline validation errors from a failed create request", async () => {
    const mutateAsync = vi.fn(async () => {
      throw new Error("Path outside allowed roots")
    })
    hookMocks.useCreateIngestionSourceMutation.mockReturnValue({
      mutateAsync,
      isPending: false
    })

    render(<SourceForm mode="create" />)

    fireEvent.change(screen.getByLabelText("Server directory path"), {
      target: { value: "/tmp/imports" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Create source" }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalled()
    })
    expect(await screen.findByText("Path outside allowed roots")).toBeInTheDocument()
  })

  it("navigates to the source detail route after a successful create", async () => {
    const mutateAsync = vi.fn(async () => ({ id: "42" }))
    hookMocks.useCreateIngestionSourceMutation.mockReturnValue({
      mutateAsync,
      isPending: false
    })

    render(<SourceForm mode="create" />)

    fireEvent.change(screen.getByLabelText("Server directory path"), {
      target: { value: "/srv/tldw/notes" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Create source" }))

    await waitFor(() => {
      expect(routerMocks.navigate).toHaveBeenCalledWith("/sources/42")
    })
  })
})
