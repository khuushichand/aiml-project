// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

// Mock the hook to control the return value
const mockQuota = {
  level: "ok" as "ok" | "warning" | "exceeded",
  ratio: 0,
  usedBytes: 0,
  budgetBytes: 5 * 1024 * 1024,
  availableBytes: 5 * 1024 * 1024,
  canWrite: () => true,
  refresh: vi.fn()
}

vi.mock("@/hooks/useStorageQuota", () => ({
  useStorageQuota: () => mockQuota
}))

import { StorageQuotaBanner } from "../StorageQuotaBanner"

describe("StorageQuotaBanner", () => {
  beforeEach(() => {
    sessionStorage.clear()
    mockQuota.level = "ok"
    mockQuota.ratio = 0
  })

  it("renders nothing when level is ok", () => {
    const { container } = render(<StorageQuotaBanner />)
    expect(container.innerHTML).toBe("")
  })

  it("renders warning banner at 80%+", () => {
    mockQuota.level = "warning"
    mockQuota.ratio = 0.82
    mockQuota.usedBytes = 4.1 * 1024 * 1024
    render(<StorageQuotaBanner />)
    expect(screen.getByTestId("storage-quota-banner-warning")).toBeInTheDocument()
    expect(screen.getByText(/82%/)).toBeInTheDocument()
  })

  it("renders exceeded banner at 95%+", () => {
    mockQuota.level = "exceeded"
    mockQuota.ratio = 0.97
    mockQuota.usedBytes = 4.85 * 1024 * 1024
    render(<StorageQuotaBanner />)
    expect(screen.getByTestId("storage-quota-banner-exceeded")).toBeInTheDocument()
  })

  it("exceeded banner cannot be dismissed", () => {
    mockQuota.level = "exceeded"
    mockQuota.ratio = 0.97
    render(<StorageQuotaBanner />)
    // Alert with type=error and no closable prop should not have close button
    expect(screen.queryByRole("button", { name: /close/i })).not.toBeInTheDocument()
  })
})
