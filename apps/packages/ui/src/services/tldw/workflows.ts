import { bgRequest } from "@/services/background-proxy"
import type {
  WorkflowPreflightRequest,
  WorkflowPreflightResult,
  WorkflowRunInvestigation,
  WorkflowStepAttemptsResponse,
  WorkflowStepTypeInfo
} from "@/types/workflow-editor"

const STEP_TYPES_TTL_MS = 5 * 60 * 1000

let stepTypesPromise: Promise<WorkflowStepTypeInfo[]> | null = null
let stepTypesFetchedAt: number | null = null

const normalizeStepTypes = (payload: unknown): WorkflowStepTypeInfo[] => {
  if (!Array.isArray(payload)) return []
  return payload
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null
      const data = entry as WorkflowStepTypeInfo
      if (!data.name) return null
      return data
    })
    .filter(Boolean) as WorkflowStepTypeInfo[]
}

export const getWorkflowStepTypes = async (
  force = false
): Promise<WorkflowStepTypeInfo[]> => {
  const now = Date.now()
  if (!force && stepTypesPromise) {
    if (!stepTypesFetchedAt) return stepTypesPromise
    if (now - stepTypesFetchedAt < STEP_TYPES_TTL_MS) {
      return stepTypesPromise
    }
  }

  stepTypesPromise = (async () => {
    try {
      const data = await bgRequest<WorkflowStepTypeInfo[]>({
        path: "/api/v1/workflows/step-types",
        method: "GET"
      })
      stepTypesFetchedAt = Date.now()
      return normalizeStepTypes(data)
    } catch (error) {
      stepTypesPromise = null
      stepTypesFetchedAt = null
      throw error
    }
  })()

  return stepTypesPromise
}

export const getWorkflowInvestigation = async (
  runId: string
): Promise<WorkflowRunInvestigation> =>
  bgRequest<WorkflowRunInvestigation>({
    path: `/api/v1/workflows/runs/${runId}/investigation`,
    method: "GET"
  })

export const getWorkflowStepAttempts = async (
  runId: string,
  stepId: string
): Promise<WorkflowStepAttemptsResponse> =>
  bgRequest<WorkflowStepAttemptsResponse>({
    path: `/api/v1/workflows/runs/${runId}/steps/${stepId}/attempts`,
    method: "GET"
  })

export const preflightWorkflowDefinition = async (
  body: WorkflowPreflightRequest
): Promise<WorkflowPreflightResult> =>
  bgRequest<WorkflowPreflightResult>({
    path: "/api/v1/workflows/preflight",
    method: "POST",
    body
  })
