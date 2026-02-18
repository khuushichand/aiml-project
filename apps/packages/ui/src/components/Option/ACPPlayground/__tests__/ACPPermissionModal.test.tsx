import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { ACPPermissionModal } from "../ACPPermissionModal"
import type { ACPPendingPermission } from "@/services/acp/types"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        typeof fallbackOrOptions.defaultValue === "string"
      ) {
        return fallbackOrOptions.defaultValue
      }
      return maybeOptions?.defaultValue || key
    },
  }),
}))

const pendingPermissions: ACPPendingPermission[] = [
  {
    request_id: "req-1",
    tool_name: "fs.writeTextFile",
    tool_arguments: { path: "/tmp/demo.txt" },
    tier: "batch",
    timeout_seconds: 30,
    requestedAt: new Date(),
  },
  {
    request_id: "req-2",
    tool_name: "exec.bash",
    tool_arguments: { command: "echo ok" },
    tier: "individual",
    timeout_seconds: 30,
    requestedAt: new Date(),
  },
]

describe("ACPPermissionModal", () => {
  it("renders current permission and queue indicator", () => {
    render(
      <ACPPermissionModal
        pendingPermissions={pendingPermissions}
        approvePermission={vi.fn()}
        denyPermission={vi.fn()}
      />
    )

    expect(screen.getByText("Permission Required")).toBeInTheDocument()
    expect(screen.getByText("fs.writeTextFile")).toBeInTheDocument()
    expect(screen.getByText(/permission requests queued/i)).toBeInTheDocument()
  })

  it("sends approve and deny actions for the current permission", () => {
    const approvePermission = vi.fn()
    const denyPermission = vi.fn()

    render(
      <ACPPermissionModal
        pendingPermissions={pendingPermissions}
        approvePermission={approvePermission}
        denyPermission={denyPermission}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Approve" }))
    expect(approvePermission).toHaveBeenCalledWith("req-1", undefined)

    fireEvent.click(screen.getByRole("checkbox"))
    fireEvent.click(screen.getByRole("button", { name: "Approve" }))
    expect(approvePermission).toHaveBeenLastCalledWith("req-1", "batch")

    fireEvent.click(screen.getByRole("button", { name: "Deny" }))
    expect(denyPermission).toHaveBeenCalledWith("req-1")
  })
})
