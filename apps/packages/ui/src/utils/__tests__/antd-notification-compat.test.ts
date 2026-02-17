import { describe, expect, it, vi } from "vitest"
import {
  normalizeNotificationConfig,
  patchNotificationApi
} from "../antd-notification-compat"

describe("antd notification compatibility helpers", () => {
  it("maps deprecated message field to title", () => {
    expect(
      normalizeNotificationConfig({
        message: "Done",
        description: "Saved"
      })
    ).toEqual({
      title: "Done",
      description: "Saved"
    })
  })

  it("drops deprecated message field when title already exists", () => {
    expect(
      normalizeNotificationConfig({
        title: "Already set",
        message: "Legacy",
        description: "Details"
      })
    ).toEqual({
      title: "Already set",
      description: "Details"
    })
  })

  it("patches notification methods idempotently", () => {
    const open = vi.fn()
    const success = vi.fn()
    const api = { open, success }

    patchNotificationApi(api)
    patchNotificationApi(api)

    api.open({ message: "Hello" })
    api.success({ message: "Success" })

    expect(open).toHaveBeenCalledWith({ title: "Hello" })
    expect(success).toHaveBeenCalledWith({ title: "Success" })
  })
})
