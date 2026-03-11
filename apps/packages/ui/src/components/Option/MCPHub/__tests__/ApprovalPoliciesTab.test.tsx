// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listApprovalPolicies: vi.fn(),
  createApprovalPolicy: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listApprovalPolicies: (...args: unknown[]) => mocks.listApprovalPolicies(...args),
  createApprovalPolicy: (...args: unknown[]) => mocks.createApprovalPolicy(...args)
}))

import { ApprovalPoliciesTab } from "../ApprovalPoliciesTab"

describe("ApprovalPoliciesTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listApprovalPolicies.mockResolvedValue([
      {
        id: 17,
        name: "Outside Profile",
        owner_scope_type: "user",
        owner_scope_id: 7,
        mode: "ask_outside_profile",
        rules: { duration_options: ["session"] },
        is_active: true
      }
    ])
    mocks.createApprovalPolicy.mockResolvedValue({
      id: 18,
      name: "Sensitive Writes",
      owner_scope_type: "global",
      owner_scope_id: null,
      mode: "ask_on_sensitive_actions",
      rules: {},
      is_active: true
    })
  })

  it("renders approval policies and opens the create form", async () => {
    const user = userEvent.setup()
    render(<ApprovalPoliciesTab />)

    expect(await screen.findByText("Outside Profile")).toBeTruthy()
    expect(screen.getByText("ask_outside_profile")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new approval policy/i }))
    expect(screen.getByLabelText(/policy name/i)).toBeTruthy()
    expect(screen.getByLabelText(/duration options/i)).toBeTruthy()
  })
})
