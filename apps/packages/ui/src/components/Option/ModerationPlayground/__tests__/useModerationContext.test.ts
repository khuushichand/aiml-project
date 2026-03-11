import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"

import { useModerationContext } from "../hooks/useModerationContext"

describe("useModerationContext", () => {
  it("returns initial state with server scope", () => {
    const { result } = renderHook(() => useModerationContext())
    expect(result.current.scope).toBe("server")
    expect(result.current.userIdDraft).toBe("")
    expect(result.current.activeUserId).toBeNull()
  })

  it("setScope to user keeps activeUserId", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setActiveUserId("u1"))
    act(() => result.current.setScope("user"))
    expect(result.current.scope).toBe("user")
    expect(result.current.activeUserId).toBe("u1")
  })

  it("setScope to server clears activeUserId", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setActiveUserId("u1"))
    act(() => result.current.setScope("server"))
    expect(result.current.scope).toBe("server")
    expect(result.current.activeUserId).toBeNull()
  })

  it("loadUser sets activeUserId from trimmed draft", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setUserIdDraft("  user123  "))
    act(() => result.current.loadUser())
    expect(result.current.activeUserId).toBe("user123")
  })

  it("loadUser does nothing if draft is empty/whitespace", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setUserIdDraft("   "))
    act(() => result.current.loadUser())
    expect(result.current.activeUserId).toBeNull()
  })

  it("clearUser resets activeUserId and userIdDraft", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setUserIdDraft("user1"))
    act(() => result.current.setActiveUserId("user1"))
    act(() => result.current.clearUser())
    expect(result.current.activeUserId).toBeNull()
    expect(result.current.userIdDraft).toBe("")
  })

  it("setUserIdDraft updates the draft value", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setUserIdDraft("new-user"))
    expect(result.current.userIdDraft).toBe("new-user")
  })

  it("setActiveUserId can be set directly", () => {
    const { result } = renderHook(() => useModerationContext())
    act(() => result.current.setActiveUserId("direct-set"))
    expect(result.current.activeUserId).toBe("direct-set")
  })
})
