import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SharedWithMe } from "./SharedWithMe"

const sharingMocks = vi.hoisted(() => ({
  useSharedWithMe: vi.fn(),
  useCloneWorkspace: vi.fn(),
  mutate: vi.fn()
}))

vi.mock("@/hooks/useSharing", () => ({
  useSharedWithMe: () => sharingMocks.useSharedWithMe(),
  useCloneWorkspace: () => sharingMocks.useCloneWorkspace()
}))

describe("SharedWithMe", () => {
  beforeEach(() => {
    sharingMocks.mutate.mockReset()
    sharingMocks.useSharedWithMe.mockReturnValue({
      data: [
        {
          share_id: 7,
          workspace_id: "workspace-1",
          workspace_name: "Policy Deck",
          workspace_description: "Shared policy notes",
          owner_user_id: 42,
          access_level: "mystery_access",
          allow_clone: true
        }
      ],
      isLoading: false,
      error: null
    })
    sharingMocks.useCloneWorkspace.mockReturnValue({
      isPending: false,
      variables: null,
      mutate: sharingMocks.mutate
    })
  })

  it("renders fallback access labels and friendlier owner text", () => {
    render(<SharedWithMe />)

    expect(screen.getByText("Policy Deck")).toBeInTheDocument()
    expect(screen.getByText("mystery_access")).toBeInTheDocument()
    expect(screen.getByText("Shared by workspace owner (account 42)")).toBeInTheDocument()
  })

  it("shows clone failures from the mutation callback", async () => {
    render(<SharedWithMe />)

    fireEvent.click(screen.getByRole("button", { name: "Clone" }))

    expect(sharingMocks.mutate).toHaveBeenCalledTimes(1)
    const mutationOptions = sharingMocks.mutate.mock.calls[0]?.[1]
    expect(mutationOptions).toEqual(
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function)
      })
    )

    mutationOptions?.onError?.(new Error("Clone failed"))

    await waitFor(() => {
      expect(screen.getByText("Clone failed")).toBeInTheDocument()
    })
  })
})
