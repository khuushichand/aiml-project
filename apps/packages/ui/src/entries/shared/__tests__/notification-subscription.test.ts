import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { NotificationStreamEvent } from "@/services/notifications"

const subscribeNotificationsStreamMock = vi.fn()
const getUnreadCountMock = vi.fn()
const notifyMock = vi.fn()

type MockStorage = {
  get: ReturnType<typeof vi.fn>
  set: ReturnType<typeof vi.fn>
}

let storageState = new Map<string, number | boolean>()
let storageMock: MockStorage

vi.mock("@/services/notifications", () => ({
  subscribeNotificationsStream: (...args: unknown[]) => subscribeNotificationsStreamMock(...args),
  getUnreadCount: (...args: unknown[]) => getUnreadCountMock(...args)
}))

vi.mock("@/services/background-helpers", () => ({
  notify: (...args: unknown[]) => notifyMock(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => storageMock
}))

import {
  resetStoredUnreadCount,
  startNotificationSubscription,
  stopNotificationSubscription
} from "@/entries/shared/notification-subscription"

describe("notification subscription", () => {
  beforeEach(() => {
    storageState = new Map()
    storageMock = {
      get: vi.fn(async (key: string) => storageState.get(key)),
      set: vi.fn(async (key: string, value: number | boolean) => {
        await Promise.resolve()
        storageState.set(key, value)
      })
    }

    subscribeNotificationsStreamMock.mockReset()
    getUnreadCountMock.mockReset()
    notifyMock.mockReset()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    stopNotificationSubscription()
  })

  it("increments unread count without losing updates when notifications arrive back-to-back", async () => {
    let onEvent: ((event: NotificationStreamEvent) => Promise<void> | void) | null = null
    subscribeNotificationsStreamMock.mockImplementation((options: { onEvent: typeof onEvent }) => {
      onEvent = options.onEvent
      return vi.fn()
    })
    getUnreadCountMock.mockResolvedValue({ unread_count: 0 })

    await startNotificationSubscription()

    expect(onEvent).toBeTruthy()

    await Promise.all([
      onEvent?.({
        event: "notification",
        payload: { title: "First", message: "One" }
      }),
      onEvent?.({
        event: "notification",
        payload: { title: "Second", message: "Two" }
      })
    ])

    expect(storageState.get("tldw:notifications:unreadCount")).toBe(2)
    expect(notifyMock).toHaveBeenCalledTimes(2)
  })

  it("logs debug details when the initial unread count fetch fails", async () => {
    const error = new Error("offline")
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {})
    subscribeNotificationsStreamMock.mockReturnValue(vi.fn())
    getUnreadCountMock.mockRejectedValue(error)

    await startNotificationSubscription()

    expect(debugSpy).toHaveBeenCalledWith(
      "[background] Failed to fetch initial unread count:",
      error
    )
  })

  it("logs debug details when a coalesced refresh fails", async () => {
    let onEvent: ((event: NotificationStreamEvent) => Promise<void> | void) | null = null
    const error = new Error("refresh failed")
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {})
    subscribeNotificationsStreamMock.mockImplementation((options: { onEvent: typeof onEvent }) => {
      onEvent = options.onEvent
      return vi.fn()
    })
    getUnreadCountMock
      .mockResolvedValueOnce({ unread_count: 3 })
      .mockRejectedValueOnce(error)

    await startNotificationSubscription()
    await onEvent?.({
      event: "notifications_coalesced",
      payload: { count: 2 }
    })

    expect(debugSpy).toHaveBeenCalledWith(
      "[background] Failed to refresh unread count after coalesced notifications:",
      error
    )
  })

  it("logs debug details when the subscription cannot start", async () => {
    const error = new Error("boom")
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {})
    getUnreadCountMock.mockResolvedValue({ unread_count: 0 })
    subscribeNotificationsStreamMock.mockImplementation(() => {
      throw error
    })

    await startNotificationSubscription()
    await resetStoredUnreadCount()

    expect(debugSpy).toHaveBeenCalledWith(
      "[background] Failed to start notification subscription:",
      error
    )
    expect(storageState.get("tldw:notifications:unreadCount")).toBe(0)
  })
})
