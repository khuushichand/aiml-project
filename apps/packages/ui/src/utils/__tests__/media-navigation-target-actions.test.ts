import { afterEach, describe, expect, it, vi } from "vitest"

import {
  applyMediaNavigationTarget,
  MEDIA_NAVIGATION_TARGET_EVENT
} from "@/utils/media-navigation-target-actions"

describe("media-navigation-target-actions", () => {
  afterEach(() => {
    document.body.innerHTML = ""
    vi.restoreAllMocks()
  })

  it("scrolls to internal anchor for href targets", () => {
    document.body.innerHTML = '<section id="section-2">Section</section>'
    const target = document.getElementById("section-2") as HTMLElement
    const scrollSpy = vi.fn()
    target.scrollIntoView = scrollSpy as any

    const handled = applyMediaNavigationTarget({
      target_type: "href",
      target_start: null,
      target_end: null,
      target_href: "#section-2"
    })

    expect(handled).toBe(true)
    expect(scrollSpy).toHaveBeenCalledTimes(1)
  })

  it("rejects external href targets", () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent")
    const handled = applyMediaNavigationTarget({
      target_type: "href",
      target_start: null,
      target_end: null,
      target_href: "https://example.com/path"
    })

    expect(handled).toBe(false)
    expect(dispatchSpy).not.toHaveBeenCalled()
  })

  it("dispatches seek event for time_range targets", () => {
    const handler = vi.fn()
    window.addEventListener(MEDIA_NAVIGATION_TARGET_EVENT, handler)

    const handled = applyMediaNavigationTarget(
      {
        target_type: "time_range",
        target_start: 42,
        target_end: 58,
        target_href: null
      },
      { mediaId: 99 }
    )

    expect(handled).toBe(true)
    expect(handler).toHaveBeenCalledTimes(1)
    const customEvent = handler.mock.calls[0]?.[0] as CustomEvent
    expect(customEvent.detail.media_id).toBe("99")
    expect(customEvent.detail.target.target_type).toBe("time_range")
    expect(customEvent.detail.target.target_start).toBe(42)

    window.removeEventListener(MEDIA_NAVIGATION_TARGET_EVENT, handler)
  })

  it("seeks HTML media element when available for time_range targets", () => {
    document.body.innerHTML = '<audio id="player"></audio>'
    const player = document.getElementById("player") as HTMLMediaElement
    player.currentTime = 0

    const handled = applyMediaNavigationTarget({
      target_type: "time_range",
      target_start: 12.5,
      target_end: 20,
      target_href: null
    })

    expect(handled).toBe(true)
    expect(player.currentTime).toBe(12.5)
  })

  it("dispatches event for page targets even when page node is absent", () => {
    const handler = vi.fn()
    window.addEventListener(MEDIA_NAVIGATION_TARGET_EVENT, handler)

    const handled = applyMediaNavigationTarget(
      {
        target_type: "page",
        target_start: 5,
        target_end: null,
        target_href: null
      },
      { mediaId: "abc" }
    )

    expect(handled).toBe(true)
    expect(handler).toHaveBeenCalledTimes(1)
    const customEvent = handler.mock.calls[0]?.[0] as CustomEvent
    expect(customEvent.detail.media_id).toBe("abc")
    expect(customEvent.detail.target.target_type).toBe("page")

    window.removeEventListener(MEDIA_NAVIGATION_TARGET_EVENT, handler)
  })
})

