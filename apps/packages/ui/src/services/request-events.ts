export const BACKEND_UNREACHABLE_EVENT = "tldw:backend-unreachable"

export type BackendUnreachableDetail = {
  method: string
  path: string
  status?: number
  message: string
  source: "background" | "direct"
  timestamp: number
}

