import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  createHouseholdDraft,
  getHouseholdDrafts,
  getHouseholdDraftSnapshot,
  getLatestHouseholdDraft,
  getActivationSummary,
  getHouseholdInvitePreview,
  getHouseholdInviteTracker,
  acceptHouseholdInviteClaim,
  acceptHouseholdInviteRegister,
  provisionHouseholdMemberInvite,
  reissueHouseholdMemberInvite,
  resendPendingInvites,
  resendHouseholdMemberInvite,
  saveGuardrailPlanDraft,
  saveRelationshipDraft
} from "../family-wizard"

const { bgRequestMock } = vi.hoisted(() => ({
  bgRequestMock: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: bgRequestMock
}))

describe("family wizard service", () => {
  beforeEach(() => {
    bgRequestMock.mockReset()
    bgRequestMock.mockResolvedValue({})
  })

  it("calls create draft endpoint", async () => {
    await createHouseholdDraft({ name: "Home", mode: "family" })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts",
      method: "POST",
      body: { name: "Home", mode: "family" }
    })
  })

  it("calls relationship mapping endpoint", async () => {
    await saveRelationshipDraft("draft-1", {
      guardian_member_draft_id: "gm-1",
      dependent_member_draft_id: "dm-1",
      relationship_type: "parent",
      dependent_visible: true
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/relationships",
      method: "POST",
      body: {
        guardian_member_draft_id: "gm-1",
        dependent_member_draft_id: "dm-1",
        relationship_type: "parent",
        dependent_visible: true
      }
    })
  })

  it("calls guardrail plans endpoint", async () => {
    await saveGuardrailPlanDraft("draft-1", {
      dependent_member_draft_id: "member-1",
      dependent_user_id: "child-1",
      relationship_draft_id: "rel-draft-1",
      template_id: "default-child-safe",
      overrides: { notify_context: "snippet" }
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/plans",
      method: "POST",
      body: {
        dependent_member_draft_id: "member-1",
        dependent_user_id: "child-1",
        relationship_draft_id: "rel-draft-1",
        template_id: "default-child-safe",
        overrides: { notify_context: "snippet" }
      }
    })
  })

  it("calls activation summary endpoint", async () => {
    await getActivationSummary("draft-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/activation-summary",
      method: "GET"
    })
  })

  it("calls latest draft endpoint", async () => {
    await getLatestHouseholdDraft()

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/latest",
      method: "GET"
    })
  })

  it("calls drafts listing endpoint", async () => {
    await getHouseholdDrafts()

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts",
      method: "GET"
    })
  })

  it("calls draft snapshot endpoint", async () => {
    await getHouseholdDraftSnapshot("draft-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/snapshot",
      method: "GET"
    })
  })

  it("calls resend pending invites endpoint", async () => {
    await resendPendingInvites("draft-1", {
      dependent_user_ids: ["child-1", "child-2"],
      member_draft_ids: ["member-1", "member-2"]
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/invites/resend",
      method: "POST",
      body: {
        dependent_user_ids: ["child-1", "child-2"],
        member_draft_ids: ["member-1", "member-2"]
      }
    })
  })

  it("calls invite tracker endpoint", async () => {
    await getHouseholdInviteTracker("draft-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/tracker",
      method: "GET"
    })
  })

  it("calls invite provision endpoint", async () => {
    await provisionHouseholdMemberInvite("draft-1", "member-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/members/member-1/invite/provision",
      method: "POST"
    })
  })

  it("calls single invite resend endpoint", async () => {
    await resendHouseholdMemberInvite("draft-1", "invite-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/invites/invite-1/resend",
      method: "POST"
    })
  })

  it("calls single invite reissue endpoint", async () => {
    await reissueHouseholdMemberInvite("draft-1", "invite-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/drafts/draft-1/invites/invite-1/reissue",
      method: "POST"
    })
  })

  it("calls invite preview endpoint", async () => {
    await getHouseholdInvitePreview("token-1")

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/invites/preview?token=token-1",
      method: "GET"
    })
  })

  it("calls invite register acceptance endpoint", async () => {
    await acceptHouseholdInviteRegister({
      token: "token-1",
      username: "child_one",
      email: "child@example.com",
      password: "correct horse battery staple"
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/invites/accept/register",
      method: "POST",
      body: {
        token: "token-1",
        username: "child_one",
        email: "child@example.com",
        password: "correct horse battery staple"
      }
    })
  })

  it("calls invite claim acceptance endpoint", async () => {
    await acceptHouseholdInviteClaim({
      token: "token-1"
    })

    expect(bgRequestMock).toHaveBeenCalledWith({
      path: "/api/v1/guardian/wizard/invites/accept/claim",
      method: "POST",
      body: {
        token: "token-1"
      }
    })
  })
})
