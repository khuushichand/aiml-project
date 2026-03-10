import { bgRequest } from "@/services/background-proxy"

export type CompanionActivityItem = {
  id: string
  event_type: string
  source_type: string
  source_id: string
  surface: string
  tags: string[]
  provenance: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
}

export type CompanionKnowledgeCard = {
  id: string
  card_type: string
  title: string
  summary: string
  evidence: Array<Record<string, unknown>>
  score: number
  status: string
  updated_at: string
}

export type CompanionGoal = {
  id: string
  title: string
  description: string | null
  goal_type: string
  config: Record<string, unknown>
  progress: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

export type CompanionGoalCreate = {
  title: string
  description?: string
  goal_type: string
  config?: Record<string, unknown>
  progress?: Record<string, unknown>
  status?: string
}

export type CompanionGoalUpdate = {
  title?: string
  description?: string | null
  config?: Record<string, unknown>
  progress?: Record<string, unknown>
  status?: string
}

export type CompanionReflection = {
  id: string
  cadence: string | null
  title: string | null
  summary: string
  evidence: Array<Record<string, unknown>>
  provenance: Record<string, unknown>
  created_at: string
}

export type CompanionNotification = {
  id: number
  user_id?: string
  kind: string
  title: string
  message: string
  severity: string
  link_type?: string | null
  link_id?: string | null
  created_at: string
  read_at?: string | null
  dismissed_at?: string | null
}

type CompanionActivityListResponse = {
  items: CompanionActivityItem[]
  total: number
  limit: number
  offset: number
}

type CompanionKnowledgeListResponse = {
  items: CompanionKnowledgeCard[]
  total: number
}

type CompanionGoalListResponse = {
  items: CompanionGoal[]
  total: number
}

type NotificationsListResponse = {
  items: CompanionNotification[]
  total: number
}

export type CompanionWorkspaceSnapshot = {
  activity: CompanionActivityItem[]
  activityTotal: number
  knowledge: CompanionKnowledgeCard[]
  knowledgeTotal: number
  goals: CompanionGoal[]
  activeGoalCount: number
  reflections: CompanionReflection[]
  reflectionNotifications: CompanionNotification[]
}

export type FetchCompanionWorkspaceOptions = {
  activityLimit?: number
  knowledgeStatus?: string
  notificationsLimit?: number
}

const buildQuery = (params?: Record<string, unknown>): string => {
  if (!params) return ""
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value == null) return
    query.set(key, String(value))
  })
  const qs = query.toString()
  return qs ? `?${qs}` : ""
}

const isCompanionReflectionActivity = (item: CompanionActivityItem): boolean =>
  item.event_type === "companion_reflection_generated" ||
  item.source_type === "companion_reflection"

const toReflection = (item: CompanionActivityItem): CompanionReflection => {
  const metadata = item.metadata || {}
  const title =
    typeof metadata.title === "string" && metadata.title.trim().length > 0
      ? metadata.title.trim()
      : null
  const summary =
    typeof metadata.summary === "string" && metadata.summary.trim().length > 0
      ? metadata.summary.trim()
      : title || item.event_type
  const cadence =
    typeof metadata.cadence === "string" && metadata.cadence.trim().length > 0
      ? metadata.cadence.trim()
      : null
  const evidence = Array.isArray(metadata.evidence)
    ? (metadata.evidence as Array<Record<string, unknown>>)
    : []
  return {
    id: item.id,
    cadence,
    title,
    summary,
    evidence,
    provenance: item.provenance || {},
    created_at: item.created_at
  }
}

export const fetchCompanionActivity = async (params?: {
  limit?: number
  offset?: number
}): Promise<CompanionActivityListResponse> => {
  const qs = buildQuery(params || {})
  return bgRequest<CompanionActivityListResponse>({
    path: `/api/v1/companion/activity${qs}` as any,
    method: "GET"
  })
}

export const fetchCompanionKnowledge = async (params?: {
  status?: string
}): Promise<CompanionKnowledgeListResponse> => {
  const qs = buildQuery(params || {})
  return bgRequest<CompanionKnowledgeListResponse>({
    path: `/api/v1/companion/knowledge${qs}` as any,
    method: "GET"
  })
}

export const fetchCompanionGoals = async (params?: {
  status?: string
}): Promise<CompanionGoalListResponse> => {
  const qs = buildQuery(params || {})
  return bgRequest<CompanionGoalListResponse>({
    path: `/api/v1/companion/goals${qs}` as any,
    method: "GET"
  })
}

export const createCompanionGoal = async (
  payload: CompanionGoalCreate
): Promise<CompanionGoal> => {
  return bgRequest<CompanionGoal>({
    path: "/api/v1/companion/goals" as any,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export const updateCompanionGoal = async (
  goalId: string,
  payload: CompanionGoalUpdate
): Promise<CompanionGoal> => {
  return bgRequest<CompanionGoal>({
    path: `/api/v1/companion/goals/${goalId}` as any,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export const setCompanionGoalStatus = async (
  goalId: string,
  status: string
): Promise<CompanionGoal> => {
  return updateCompanionGoal(goalId, { status })
}

export const fetchCompanionReflectionNotifications = async (params?: {
  limit?: number
  offset?: number
}): Promise<NotificationsListResponse> => {
  const qs = buildQuery(params || {})
  return bgRequest<NotificationsListResponse>({
    path: `/api/v1/notifications${qs}` as any,
    method: "GET"
  })
}

export const fetchCompanionWorkspaceSnapshot = async (
  options: FetchCompanionWorkspaceOptions = {}
): Promise<CompanionWorkspaceSnapshot> => {
  const activityLimit = options.activityLimit ?? 25
  const knowledgeStatus = options.knowledgeStatus ?? "active"
  const notificationsLimit = options.notificationsLimit ?? 50

  const [activityResponse, knowledgeResponse, goalsResponse, notificationsResponse] =
    await Promise.all([
      fetchCompanionActivity({ limit: activityLimit, offset: 0 }),
      fetchCompanionKnowledge({ status: knowledgeStatus }),
      fetchCompanionGoals(),
      fetchCompanionReflectionNotifications({
        limit: notificationsLimit,
        offset: 0
      }).catch(() => ({
        items: [],
        total: 0
      }))
    ])

  const reflections = activityResponse.items
    .filter(isCompanionReflectionActivity)
    .map(toReflection)

  return {
    activity: activityResponse.items.filter(
      (item) => !isCompanionReflectionActivity(item)
    ),
    activityTotal: activityResponse.total,
    knowledge: knowledgeResponse.items,
    knowledgeTotal: knowledgeResponse.total,
    goals: goalsResponse.items,
    activeGoalCount: goalsResponse.items.filter((goal) => goal.status === "active")
      .length,
    reflections,
    reflectionNotifications: notificationsResponse.items.filter(
      (item) => item.kind === "companion_reflection"
    )
  }
}
