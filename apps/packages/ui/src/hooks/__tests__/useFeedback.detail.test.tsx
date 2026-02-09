import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useFeedback } from "../useFeedback"
import { useFeedbackStore } from "@/store/feedback"

const mocks = vi.hoisted(() => ({
  submitExplicitFeedback: vi.fn().mockResolvedValue({ ok: true, feedback_id: "fb-1" }),
  updateChatRating: vi.fn(),
  notificationError: vi.fn(),
  setServerChatVersion: vi.fn()
}))

vi.mock("@/services/feedback", () => ({
  getFeedbackSessionId: () => "sess-test",
  submitExplicitFeedback: mocks.submitExplicitFeedback,
  updateChatRating: mocks.updateChatRating
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (selector: any) =>
    selector({
      serverChatVersion: null,
      setServerChatVersion: mocks.setServerChatVersion
    })
}))

vi.mock("../useAntdNotification", () => ({
  useAntdNotification: () => ({ error: mocks.notificationError })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

describe("useFeedback detail submission", () => {
  beforeEach(() => {
    mocks.submitExplicitFeedback.mockClear()
    mocks.updateChatRating.mockClear()
    mocks.notificationError.mockClear()
    useFeedbackStore.setState({ entries: {} })
    window.localStorage.clear()
  })

  it("submits rating + issues + notes in a single explicit request", async () => {
    const { result } = renderHook(() =>
      useFeedback({
        messageKey: "srv:M_1",
        conversationId: "C_1",
        messageId: "M_1",
        query: null
      })
    )

    let ok = false
    await act(async () => {
      ok = await result.current.submitDetail({
        rating: 3,
        issues: ["missing_details", "sources_unhelpful"],
        notes: "Needs source grounding."
      })
    })

    expect(ok).toBe(true)
    expect(mocks.submitExplicitFeedback).toHaveBeenCalledTimes(1)
    expect(mocks.submitExplicitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        conversation_id: "C_1",
        message_id: "M_1",
        session_id: "sess-test",
        feedback_type: "relevance",
        relevance_score: 3,
        issues: ["missing_details", "sources_unhelpful"],
        user_notes: "Needs source grounding.",
        idempotency_key: expect.any(String)
      })
    )
  })
})
