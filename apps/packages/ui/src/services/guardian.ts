/**
 * Guardian & Self-Monitoring service - API client for guardian controls
 * and self-monitoring endpoints.
 */

import { bgRequest } from "@/services/background-proxy"
import { appendPathQuery, toAllowedPath } from "@/services/tldw/path-utils"

// ---------------------------------------------------------------------------
// Self-Monitoring types
// ---------------------------------------------------------------------------

export interface SelfMonitoringRule {
  id: string
  user_id: string
  governance_policy_id: string | null
  name: string
  category: string
  patterns: string[]
  pattern_type: string
  except_patterns: string[]
  rule_type: string
  action: string
  phase: string
  severity: string
  display_mode: string
  block_message: string | null
  context_note: string | null
  notification_frequency: string
  notification_channels: string[]
  webhook_url: string | null
  trusted_contact_email: string | null
  crisis_resources_enabled: boolean
  cooldown_minutes: number
  bypass_protection: string
  bypass_partner_user_id: string | null
  escalation_session_threshold: number
  escalation_session_action: string | null
  escalation_window_days: number
  escalation_window_threshold: number
  escalation_window_action: string | null
  min_context_length: number
  enabled: boolean
  can_disable: boolean
  pending_deactivation_at: string | null
  created_at: string
  updated_at: string
}

export interface SelfMonitoringRuleCreate {
  name: string
  category: string
  patterns: string[]
  pattern_type?: "literal" | "regex"
  except_patterns?: string[]
  rule_type?: "block" | "notify"
  action?: "block" | "redact" | "notify"
  phase?: "input" | "output" | "both"
  severity?: "info" | "warning" | "critical"
  display_mode?: "inline_banner" | "sidebar_note" | "post_session_summary" | "silent_log"
  block_message?: string | null
  context_note?: string | null
  notification_frequency?: "every_message" | "once_per_conversation" | "once_per_day" | "once_per_session"
  notification_channels?: string[]
  webhook_url?: string | null
  trusted_contact_email?: string | null
  crisis_resources_enabled?: boolean
  cooldown_minutes?: number
  bypass_protection?: "none" | "cooldown" | "confirmation" | "partner_approval"
  bypass_partner_user_id?: string | null
  escalation_session_threshold?: number
  escalation_session_action?: string | null
  escalation_window_days?: number
  escalation_window_threshold?: number
  escalation_window_action?: string | null
  min_context_length?: number
  governance_policy_id?: string | null
  enabled?: boolean
}

export type SelfMonitoringRuleUpdate = Partial<SelfMonitoringRuleCreate>

export interface SelfMonitoringRuleList {
  items: SelfMonitoringRule[]
  total: number
}

export interface SelfMonitoringAlert {
  id: string
  rule_id: string
  rule_name: string
  category: string
  severity: string
  matched_pattern: string
  context_snippet: string | null
  snippet_mode: string
  conversation_id: string | null
  session_id: string | null
  chat_type: string | null
  phase: string
  action_taken: string
  notification_sent: boolean
  notification_channels_used: string[]
  crisis_resources_shown: boolean
  display_mode: string
  escalation_info: Record<string, unknown> | null
  is_read: boolean
  created_at: string
}

export interface SelfMonitoringAlertList {
  items: SelfMonitoringAlert[]
  total: number
}

export interface UnreadCount {
  unread_count: number
}

export interface RuleDeactivationResponse {
  ok: boolean
  status: "disabled_immediately" | "pending_deactivation"
  deactivation_at?: string
  reason?: string
}

// ---------------------------------------------------------------------------
// Governance policy types
// ---------------------------------------------------------------------------

export interface GovernancePolicy {
  id: string
  owner_user_id: string
  name: string
  description: string
  policy_mode: string
  scope_chat_types: string
  enabled: boolean
  schedule_start: string | null
  schedule_end: string | null
  schedule_days: string | null
  schedule_timezone: string
  transparent: boolean
  created_at: string
  updated_at: string
}

export interface GovernancePolicyCreate {
  name: string
  description: string
  policy_mode?: "guardian" | "self"
  scope_chat_types?: string
  enabled?: boolean
  schedule_start?: string | null
  schedule_end?: string | null
  schedule_days?: string | null
  schedule_timezone?: string
  transparent?: boolean
}

export interface GovernancePolicyList {
  items: GovernancePolicy[]
  total: number
}

// ---------------------------------------------------------------------------
// Guardian relationship types
// ---------------------------------------------------------------------------

export interface GuardianRelationship {
  id: string
  guardian_user_id: string
  dependent_user_id: string
  relationship_type: string
  status: string
  consent_given_by_dependent: boolean
  consent_given_at: string | null
  dependent_visible: boolean
  dissolution_reason: string | null
  dissolved_at: string | null
  created_at: string
  updated_at: string
}

export interface GuardianRelationshipCreate {
  dependent_user_id: string
  relationship_type?: "parent" | "legal_guardian" | "institutional"
  dependent_visible?: boolean
}

export interface GuardianRelationshipList {
  items: GuardianRelationship[]
  total: number
}

// ---------------------------------------------------------------------------
// Supervised policy types
// ---------------------------------------------------------------------------

export interface SupervisedPolicy {
  id: string
  relationship_id: string
  policy_type: string
  category: string
  pattern: string
  pattern_type: string
  action: string
  phase: string
  severity: string
  notify_guardian: boolean
  notify_context: string
  message_to_dependent: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SupervisedPolicyCreate {
  relationship_id: string
  policy_type?: "block" | "notify"
  category: string
  pattern: string
  pattern_type?: "literal" | "regex"
  action?: "block" | "redact" | "warn" | "notify"
  phase?: "input" | "output" | "both"
  severity?: "info" | "warning" | "critical"
  notify_guardian?: boolean
  notify_context?: "topic_only" | "snippet" | "full_message"
  message_to_dependent?: string | null
  enabled?: boolean
}

export type SupervisedPolicyUpdate = Partial<Omit<SupervisedPolicyCreate, "relationship_id">>

export interface SupervisedPolicyList {
  items: SupervisedPolicy[]
  total: number
}

// ---------------------------------------------------------------------------
// Audit log types
// ---------------------------------------------------------------------------

export interface AuditLogEntry {
  id: string
  relationship_id: string
  actor_user_id: string
  action: string
  target_user_id: string | null
  policy_id: string | null
  detail: string
  created_at: string
}

export interface AuditLogList {
  items: AuditLogEntry[]
  total: number
}

export interface DependentGuardian {
  relationship_id: string
  relationship_type: string
  monitoring_active?: boolean
  policy_count?: number
  categories?: string[]
}

export interface DependentStatusResponse {
  supervised: boolean
  guardians: DependentGuardian[]
}

// ---------------------------------------------------------------------------
// Crisis resource types
// ---------------------------------------------------------------------------

export interface CrisisResource {
  name: string
  description: string
  contact: string
  url: string | null
  available_24_7: boolean
}

export interface CrisisResourceList {
  resources: CrisisResource[]
  disclaimer: string
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export interface DetailResponse {
  detail: string
}

// ---------------------------------------------------------------------------
// Self-Monitoring API functions
// ---------------------------------------------------------------------------

export async function listRules(params?: {
  category?: string
  enabled_only?: boolean
}): Promise<SelfMonitoringRuleList> {
  let query = ""
  if (params) {
    const parts: string[] = []
    if (params.category) parts.push(`category=${encodeURIComponent(params.category)}`)
    if (params.enabled_only !== undefined) parts.push(`enabled_only=${params.enabled_only}`)
    if (parts.length) query = `?${parts.join("&")}`
  }
  return bgRequest<SelfMonitoringRuleList>({
    path: appendPathQuery(toAllowedPath("/api/v1/self-monitoring/rules"), query),
    method: "GET"
  })
}

export async function createRule(body: SelfMonitoringRuleCreate): Promise<SelfMonitoringRule> {
  return bgRequest<SelfMonitoringRule>({
    path: toAllowedPath("/api/v1/self-monitoring/rules"),
    method: "POST",
    body
  })
}

export async function getRule(id: string): Promise<SelfMonitoringRule> {
  return bgRequest<SelfMonitoringRule>({
    path: toAllowedPath(`/api/v1/self-monitoring/rules/${encodeURIComponent(id)}`),
    method: "GET"
  })
}

export async function updateRule(id: string, body: SelfMonitoringRuleUpdate): Promise<SelfMonitoringRule> {
  return bgRequest<SelfMonitoringRule>({
    path: toAllowedPath(`/api/v1/self-monitoring/rules/${encodeURIComponent(id)}`),
    method: "PATCH",
    body
  })
}

export async function deleteRule(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/self-monitoring/rules/${encodeURIComponent(id)}`),
    method: "DELETE"
  })
}

export async function deactivateRule(id: string): Promise<RuleDeactivationResponse> {
  return bgRequest<RuleDeactivationResponse>({
    path: toAllowedPath(`/api/v1/self-monitoring/rules/${encodeURIComponent(id)}/deactivate`),
    method: "POST"
  })
}

export async function listAlerts(params?: {
  rule_id?: string
  unread_only?: boolean
  limit?: number
  offset?: number
}): Promise<SelfMonitoringAlertList> {
  let query = ""
  if (params) {
    const parts: string[] = []
    if (params.rule_id) parts.push(`rule_id=${encodeURIComponent(params.rule_id)}`)
    if (params.unread_only !== undefined) parts.push(`unread_only=${params.unread_only}`)
    if (params.limit !== undefined) parts.push(`limit=${params.limit}`)
    if (params.offset !== undefined) parts.push(`offset=${params.offset}`)
    if (parts.length) query = `?${parts.join("&")}`
  }
  return bgRequest<SelfMonitoringAlertList>({
    path: appendPathQuery(toAllowedPath("/api/v1/self-monitoring/alerts"), query),
    method: "GET"
  })
}

export async function markAlertsRead(alertIds: string[]): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath("/api/v1/self-monitoring/alerts/mark-read"),
    method: "POST",
    body: { alert_ids: alertIds }
  })
}

export async function getUnreadCount(): Promise<UnreadCount> {
  return bgRequest<UnreadCount>({
    path: toAllowedPath("/api/v1/self-monitoring/alerts/unread-count"),
    method: "GET"
  })
}

export async function listGovernancePolicies(params?: {
  policy_mode?: string
}): Promise<GovernancePolicyList> {
  let query = ""
  if (params) {
    const parts: string[] = []
    if (params.policy_mode) parts.push(`policy_mode=${encodeURIComponent(params.policy_mode)}`)
    if (parts.length) query = `?${parts.join("&")}`
  }
  return bgRequest<GovernancePolicyList>({
    path: appendPathQuery(toAllowedPath("/api/v1/self-monitoring/governance-policies"), query),
    method: "GET"
  })
}

export async function createGovernancePolicy(body: GovernancePolicyCreate): Promise<GovernancePolicy> {
  return bgRequest<GovernancePolicy>({
    path: toAllowedPath("/api/v1/self-monitoring/governance-policies"),
    method: "POST",
    body
  })
}

export async function deleteGovernancePolicy(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/self-monitoring/governance-policies/${encodeURIComponent(id)}`),
    method: "DELETE"
  })
}

export async function getCrisisResources(): Promise<CrisisResourceList> {
  return bgRequest<CrisisResourceList>({
    path: toAllowedPath("/api/v1/self-monitoring/crisis-resources"),
    method: "GET"
  })
}

// ---------------------------------------------------------------------------
// Guardian API functions
// ---------------------------------------------------------------------------

export async function listRelationships(params?: {
  role?: "guardian" | "dependent"
  status?: string
}): Promise<GuardianRelationshipList> {
  let query = ""
  if (params) {
    const parts: string[] = []
    if (params.role) parts.push(`role=${encodeURIComponent(params.role)}`)
    if (params.status) parts.push(`status=${encodeURIComponent(params.status)}`)
    if (parts.length) query = `?${parts.join("&")}`
  }
  return bgRequest<GuardianRelationshipList>({
    path: appendPathQuery(toAllowedPath("/api/v1/guardian/relationships"), query),
    method: "GET"
  })
}

export async function createRelationship(body: GuardianRelationshipCreate): Promise<GuardianRelationship> {
  return bgRequest<GuardianRelationship>({
    path: toAllowedPath("/api/v1/guardian/relationships"),
    method: "POST",
    body
  })
}

export async function getRelationship(id: string): Promise<GuardianRelationship> {
  return bgRequest<GuardianRelationship>({
    path: toAllowedPath(`/api/v1/guardian/relationships/${encodeURIComponent(id)}`),
    method: "GET"
  })
}

export async function acceptRelationship(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/guardian/relationships/${encodeURIComponent(id)}/accept`),
    method: "POST"
  })
}

export async function suspendRelationship(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/guardian/relationships/${encodeURIComponent(id)}/suspend`),
    method: "POST"
  })
}

export async function reactivateRelationship(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/guardian/relationships/${encodeURIComponent(id)}/reactivate`),
    method: "POST"
  })
}

export async function dissolveRelationship(id: string, reason?: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/guardian/relationships/${encodeURIComponent(id)}/dissolve`),
    method: "POST",
    body: reason ? { reason } : undefined
  })
}

export async function listPolicies(params?: {
  relationship_id?: string
  enabled_only?: boolean
}): Promise<SupervisedPolicyList> {
  let query = ""
  if (params) {
    const parts: string[] = []
    if (params.relationship_id) parts.push(`relationship_id=${encodeURIComponent(params.relationship_id)}`)
    if (params.enabled_only !== undefined) parts.push(`enabled_only=${params.enabled_only}`)
    if (parts.length) query = `?${parts.join("&")}`
  }
  return bgRequest<SupervisedPolicyList>({
    path: appendPathQuery(toAllowedPath("/api/v1/guardian/policies"), query),
    method: "GET"
  })
}

export async function createPolicy(body: SupervisedPolicyCreate): Promise<SupervisedPolicy> {
  return bgRequest<SupervisedPolicy>({
    path: toAllowedPath("/api/v1/guardian/policies"),
    method: "POST",
    body
  })
}

export async function updatePolicy(id: string, body: SupervisedPolicyUpdate): Promise<SupervisedPolicy> {
  return bgRequest<SupervisedPolicy>({
    path: toAllowedPath(`/api/v1/guardian/policies/${encodeURIComponent(id)}`),
    method: "PATCH",
    body
  })
}

export async function deletePolicy(id: string): Promise<DetailResponse> {
  return bgRequest<DetailResponse>({
    path: toAllowedPath(`/api/v1/guardian/policies/${encodeURIComponent(id)}`),
    method: "DELETE"
  })
}

export async function getAuditLog(params: {
  relationship_id: string
  limit?: number
  offset?: number
}): Promise<AuditLogList> {
  let query = ""
  const parts: string[] = []
  if (params.limit !== undefined) parts.push(`limit=${params.limit}`)
  if (params.offset !== undefined) parts.push(`offset=${params.offset}`)
  if (parts.length) query = `?${parts.join("&")}`
  return bgRequest<AuditLogList>({
    path: appendPathQuery(
      toAllowedPath(`/api/v1/guardian/audit/${encodeURIComponent(params.relationship_id)}`),
      query
    ),
    method: "GET"
  })
}

export async function getPolicy(id: string): Promise<SupervisedPolicy> {
  return bgRequest<SupervisedPolicy>({
    path: toAllowedPath(`/api/v1/guardian/policies/${encodeURIComponent(id)}`),
    method: "GET"
  })
}

export async function getDependentStatus(): Promise<DependentStatusResponse> {
  return bgRequest<DependentStatusResponse>({
    path: toAllowedPath("/api/v1/guardian/dependent/status"),
    method: "GET"
  })
}
