import { describe, expect, it } from "vitest"
import { resolveFallbackAudit } from "../routing-fallback-audit"

describe("routing-fallback-audit", () => {
  it("detects fallback usage and route path changes", () => {
    const result = resolveFallbackAudit({
      routing_policy: "auto-fallback",
      requested_provider: "openai",
      requested_model: "gpt-4o-mini",
      resolved_provider: "anthropic",
      resolved_model: "claude-3-5-sonnet",
      routing_attempts: 2,
      fallback_reason: "Rate limited upstream"
    })

    expect(result).toEqual({
      policy: "auto",
      requestedTarget: "openai/gpt-4o-mini",
      resolvedTarget: "anthropic/claude-3-5-sonnet",
      fallbackApplied: true,
      attempts: 2,
      reason: "Rate limited upstream"
    })
  })

  it("reports pinned policy when provider is fixed without fallback", () => {
    const result = resolveFallbackAudit({
      routing: {
        policy: "provider-pinned",
        requested_provider: "openrouter",
        resolved_provider: "openrouter",
        resolved_model: "openai/gpt-4.1-mini"
      },
      routing_attempts: 1
    })

    expect(result).toEqual({
      policy: "pinned",
      requestedTarget: "openrouter",
      resolvedTarget: "openrouter/openai/gpt-4.1-mini",
      fallbackApplied: false,
      attempts: 1,
      reason: null
    })
  })

  it("returns null when no routing metadata is present", () => {
    expect(resolveFallbackAudit({ total_tokens: 120 })).toBeNull()
  })
})
