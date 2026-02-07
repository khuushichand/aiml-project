import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  deactivateRule,
  getAuditLog,
  listAlerts,
  listGovernancePolicies,
  listRelationships,
  listRules
} from "../guardian"

const { bgRequestMock } = vi.hoisted(() => ({
  bgRequestMock: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: bgRequestMock
}))

describe("guardian service API contracts", () => {
  beforeEach(() => {
    bgRequestMock.mockReset()
    bgRequestMock.mockResolvedValue({})
  })

  it("uses enabled_only for rules filtering", async () => {
    await listRules({
      category: "self harm",
      enabled_only: true
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/self-monitoring/rules?category=self%20harm&enabled_only=true",
      method: "GET"
    })
  })

  it("uses unread_only and offset for alerts", async () => {
    await listAlerts({
      rule_id: "rule/1",
      unread_only: true,
      limit: 25,
      offset: 5
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/self-monitoring/alerts?rule_id=rule%2F1&unread_only=true&limit=25&offset=5",
      method: "GET"
    })
  })

  it("uses policy_mode for governance policy listing", async () => {
    await listGovernancePolicies({
      policy_mode: "self"
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/self-monitoring/governance-policies?policy_mode=self",
      method: "GET"
    })
  })

  it("includes optional relationship role and status filters", async () => {
    await listRelationships({
      role: "dependent",
      status: "pending consent"
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/relationships?role=dependent&status=pending%20consent",
      method: "GET"
    })
  })

  it("uses offset for guardian audit log pagination", async () => {
    await getAuditLog({
      relationship_id: "rel/1",
      limit: 50,
      offset: 10
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/audit/rel%2F1?limit=50&offset=10",
      method: "GET"
    })
  })

  it("calls deactivate endpoint with encoded id and POST", async () => {
    await deactivateRule("rule/1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/self-monitoring/rules/rule%2F1/deactivate",
      method: "POST"
    })
  })
})
