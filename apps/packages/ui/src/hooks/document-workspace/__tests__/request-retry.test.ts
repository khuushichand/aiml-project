import { describe, expect, it } from "vitest"

import {
  getErrorStatus,
  isNotFoundError,
  shouldRetryDocumentWorkspaceQuery,
} from "@/hooks/document-workspace/request-retry"

describe("document workspace retry helpers", () => {
  it("extracts status from error-like objects", () => {
    expect(getErrorStatus({ status: 404 })).toBe(404)
    expect(getErrorStatus({ status: "404" })).toBeUndefined()
    expect(getErrorStatus(new Error("boom"))).toBeUndefined()
    expect(getErrorStatus(null)).toBeUndefined()
  })

  it("identifies 404 responses", () => {
    expect(isNotFoundError({ status: 404 })).toBe(true)
    expect(isNotFoundError({ status: 500 })).toBe(false)
    expect(isNotFoundError(undefined)).toBe(false)
  })

  it("never retries 404 responses", () => {
    expect(shouldRetryDocumentWorkspaceQuery(0, { status: 404 }, 3)).toBe(false)
    expect(shouldRetryDocumentWorkspaceQuery(2, { status: 404 }, 3)).toBe(false)
  })

  it("retries non-404 responses up to max retries", () => {
    expect(shouldRetryDocumentWorkspaceQuery(0, { status: 500 }, 2)).toBe(true)
    expect(shouldRetryDocumentWorkspaceQuery(1, { status: 500 }, 2)).toBe(true)
    expect(shouldRetryDocumentWorkspaceQuery(2, { status: 500 }, 2)).toBe(false)
  })
})
