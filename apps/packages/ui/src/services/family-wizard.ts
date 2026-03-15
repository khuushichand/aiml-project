import { bgRequest } from "@/services/background-proxy"
import { toAllowedPath } from "@/services/tldw/path-utils"

export type HouseholdMode = "family" | "institutional"
export type WizardActivationStatus =
  | "draft"
  | "invites_pending"
  | "partially_active"
  | "active"
  | "needs_attention"
export type RelationshipType = "parent" | "legal_guardian" | "institutional"
export type MemberRole = "guardian" | "dependent" | "caregiver"
export type PlanStatus = "queued" | "active" | "failed"

export interface HouseholdDraft {
  id: string
  owner_user_id: string
  name: string
  mode: HouseholdMode
  status: WizardActivationStatus
  created_at: string
  updated_at: string
}

export interface CreateHouseholdDraftBody {
  name: string
  mode: HouseholdMode
}

export interface UpdateHouseholdDraftBody {
  name?: string
  mode?: HouseholdMode
  status?: WizardActivationStatus
}

export interface HouseholdMemberDraft {
  id: string
  household_draft_id: string
  role: MemberRole
  display_name: string
  user_id: string | null
  email: string | null
  invite_required: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AddHouseholdMemberDraftBody {
  role: MemberRole
  display_name: string
  user_id?: string
  email?: string
  invite_required?: boolean
  metadata?: Record<string, unknown>
}

export interface RelationshipDraft {
  id: string
  household_draft_id: string
  guardian_member_draft_id: string
  dependent_member_draft_id: string
  relationship_type: RelationshipType
  dependent_visible: boolean
  status: "pending" | "active" | "declined" | "revoked"
  relationship_id: string | null
  created_at: string
  updated_at: string
}

export interface SaveRelationshipDraftBody {
  guardian_member_draft_id: string
  dependent_member_draft_id: string
  relationship_type?: RelationshipType
  dependent_visible?: boolean
}

export interface GuardrailPlanDraft {
  id: string
  household_draft_id: string
  dependent_user_id: string
  relationship_draft_id: string
  template_id: string
  overrides: Record<string, unknown>
  status: PlanStatus
  materialized_policy_id: string | null
  failure_reason: string | null
  created_at: string
  updated_at: string
}

export interface SaveGuardrailPlanDraftBody {
  dependent_user_id: string
  relationship_draft_id: string
  template_id: string
  overrides?: Record<string, unknown>
}

export interface ActivationSummaryItem {
  dependent_user_id: string
  relationship_status: "pending" | "active" | "declined" | "revoked"
  plan_status: PlanStatus
  message: string | null
}

export interface ActivationSummary {
  household_draft_id: string
  status: WizardActivationStatus
  active_count: number
  pending_count: number
  failed_count: number
  items: ActivationSummaryItem[]
}

export interface ResendPendingInvitesBody {
  dependent_user_ids: string[]
}

export interface ResendPendingInvitesResponse {
  household_draft_id: string
  resent_count: number
  skipped_count: number
  resent_user_ids: string[]
  skipped_user_ids: string[]
}

export interface HouseholdDraftSnapshot {
  household: HouseholdDraft
  members: HouseholdMemberDraft[]
  relationships: RelationshipDraft[]
  plans: GuardrailPlanDraft[]
}

export async function createHouseholdDraft(
  body: CreateHouseholdDraftBody
): Promise<HouseholdDraft> {
  return bgRequest<HouseholdDraft>({
    path: toAllowedPath("/api/v1/guardian/wizard/drafts"),
    method: "POST",
    body
  })
}

export async function getHouseholdDraft(draftId: string): Promise<HouseholdDraft> {
  return bgRequest<HouseholdDraft>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}`),
    method: "GET"
  })
}

export async function getLatestHouseholdDraft(): Promise<HouseholdDraft | null> {
  try {
    return await bgRequest<HouseholdDraft>({
      path: toAllowedPath("/api/v1/guardian/wizard/drafts/latest"),
      method: "GET"
    })
  } catch (error) {
    const status = (error as { status?: number } | null)?.status
    if (status === 404) return null
    throw error
  }
}

export async function getHouseholdDraftSnapshot(
  draftId: string
): Promise<HouseholdDraftSnapshot> {
  return bgRequest<HouseholdDraftSnapshot>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/snapshot`),
    method: "GET"
  })
}

export async function updateHouseholdDraft(
  draftId: string,
  body: UpdateHouseholdDraftBody
): Promise<HouseholdDraft> {
  return bgRequest<HouseholdDraft>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}`),
    method: "PATCH",
    body
  })
}

export async function addHouseholdMemberDraft(
  draftId: string,
  body: AddHouseholdMemberDraftBody
): Promise<HouseholdMemberDraft> {
  return bgRequest<HouseholdMemberDraft>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/members`),
    method: "POST",
    body
  })
}

export async function removeHouseholdMemberDraft(
  draftId: string,
  memberId: string
): Promise<{ detail: string }> {
  return bgRequest<{ detail: string }>({
    path: toAllowedPath(
      `/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/members/${encodeURIComponent(memberId)}`
    ),
    method: "DELETE"
  })
}

export async function saveRelationshipDraft(
  draftId: string,
  body: SaveRelationshipDraftBody
): Promise<RelationshipDraft> {
  return bgRequest<RelationshipDraft>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/relationships`),
    method: "POST",
    body
  })
}

export async function saveGuardrailPlanDraft(
  draftId: string,
  body: SaveGuardrailPlanDraftBody
): Promise<GuardrailPlanDraft> {
  return bgRequest<GuardrailPlanDraft>({
    path: toAllowedPath(`/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/plans`),
    method: "POST",
    body
  })
}

export async function getActivationSummary(
  draftId: string
): Promise<ActivationSummary> {
  return bgRequest<ActivationSummary>({
    path: toAllowedPath(
      `/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/activation-summary`
    ),
    method: "GET"
  })
}

export async function resendPendingInvites(
  draftId: string,
  body: ResendPendingInvitesBody
): Promise<ResendPendingInvitesResponse> {
  return bgRequest<ResendPendingInvitesResponse>({
    path: toAllowedPath(
      `/api/v1/guardian/wizard/drafts/${encodeURIComponent(draftId)}/invites/resend`
    ),
    method: "POST",
    body
  })
}
