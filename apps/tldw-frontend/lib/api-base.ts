export type DeploymentMode = "quickstart" | "advanced"

export type DeploymentEnv = {
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE?: string
  NEXT_PUBLIC_API_URL?: string
}

export type NetworkingIssue =
  | {
      kind: "loopback_api_not_browser_reachable"
      apiOrigin: string
      pageOrigin: string
    }

const DEFAULT_API_VERSION = "v1"

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, "")

const isLoopbackHost = (hostname: string): boolean =>
  hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1"

const parseOrigin = (origin: string): URL | null => {
  try {
    return new URL(origin)
  } catch {
    return null
  }
}

export const resolveDeploymentMode = (env: DeploymentEnv): DeploymentMode =>
  env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE === "quickstart" ? "quickstart" : "advanced"

export const resolvePublicApiOrigin = (env: DeploymentEnv, pageOrigin?: string): string => {
  if (resolveDeploymentMode(env) === "quickstart") {
    return ""
  }

  const apiOrigin = env.NEXT_PUBLIC_API_URL?.trim()
  if (apiOrigin) {
    return trimTrailingSlash(apiOrigin)
  }

  return pageOrigin ? trimTrailingSlash(pageOrigin) : ""
}

export const buildApiBaseUrl = (origin: string, version: string = DEFAULT_API_VERSION): string =>
  origin
    ? `${trimTrailingSlash(origin)}/api/${version || DEFAULT_API_VERSION}`
    : `/api/${version || DEFAULT_API_VERSION}`

export const detectNetworkingIssue = (
  env: DeploymentEnv,
  pageOrigin?: string
): NetworkingIssue | undefined => {
  const apiOrigin = resolvePublicApiOrigin(env, pageOrigin)
  if (!apiOrigin || !pageOrigin) {
    return undefined
  }

  const apiUrl = parseOrigin(apiOrigin)
  const pageUrl = parseOrigin(pageOrigin)

  if (!apiUrl || !pageUrl) {
    return undefined
  }

  if (isLoopbackHost(apiUrl.hostname) && !isLoopbackHost(pageUrl.hostname)) {
    return {
      kind: "loopback_api_not_browser_reachable",
      apiOrigin,
      pageOrigin: trimTrailingSlash(pageOrigin)
    }
  }

  return undefined
}
