import React from "react"
import { Form } from "antd"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { WorldBookForm } from "../Manager"

type HarnessProps = {
  mode?: "create" | "edit"
  worldBooks?: Array<{ id?: number; name?: string }>
  submitting?: boolean
  currentWorldBookId?: number | null
  onSubmit?: (values: Record<string, any>) => void
}

const WorldBookFormHarness: React.FC<HarnessProps> = ({
  mode = "create",
  worldBooks = [],
  submitting = false,
  currentWorldBookId = null,
  onSubmit = vi.fn()
}) => {
  const [form] = Form.useForm()
  return (
    <WorldBookForm
      mode={mode}
      form={form}
      worldBooks={worldBooks}
      submitting={submitting}
      currentWorldBookId={currentWorldBookId}
      onSubmit={onSubmit}
    />
  )
}

describe("WorldBookForm", () => {
  it("renders create-mode labels and optional description text", () => {
    render(<WorldBookFormHarness />)

    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByText("Description (optional)")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument()
  })

  it("submits create mode with backend-aligned defaults", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<WorldBookFormHarness onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText("Name"), "Arcana")
    await user.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Arcana",
        enabled: true,
        scan_depth: 3,
        token_budget: 500,
        recursive_scanning: false
      })
    )
  })

  it("blocks create submit when name duplicates an existing world book", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(
      <WorldBookFormHarness
        onSubmit={onSubmit}
        worldBooks={[
          { id: 1, name: "Arcana" },
          { id: 2, name: "Compendium" }
        ]}
      />
    )

    await user.type(screen.getByLabelText("Name"), "arcana")
    await user.click(screen.getByRole("button", { name: "Create" }))

    expect(await screen.findByText('A world book named "arcana" already exists.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("allows edit mode to keep the same name for the current world book", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(
      <WorldBookFormHarness
        mode="edit"
        onSubmit={onSubmit}
        currentWorldBookId={1}
        worldBooks={[
          { id: 1, name: "Arcana" },
          { id: 2, name: "Compendium" }
        ]}
      />
    )

    await user.type(screen.getByLabelText("Name"), "Arcana")
    await user.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  })
})
