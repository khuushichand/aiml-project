import {
  buildBrowserHttpBase,
  detectBrowserNetworkingIssue,
  resolveBrowserTransport,
  resolveBrowserTransportMode,
  type BrowserNetworkingIssue,
  type BrowserTransportMode
} from "@/services/tldw/browser-networking"

export type DeploymentMode = BrowserTransportMode

export type DeploymentEnv = {
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE?: string
  NEXT_PUBLIC_API_URL?: string
}

export type NetworkingIssue = BrowserNetworkingIssue

const DEFAULT_API_VERSION = "v1"

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, "")

export const resolveDeploymentMode = (env: DeploymentEnv): DeploymentMode =>
  resolveBrowserTransportMode(env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE)

export const resolvePublicApiOrigin = (env: DeploymentEnv, pageOrigin?: string): string => {
  return buildBrowserHttpBase(
    resolveBrowserTransport({
      surface: "webui-page",
      deploymentMode: env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
      pageOrigin,
      apiOrigin: env.NEXT_PUBLIC_API_URL
    })
  )
}

export const buildApiBaseUrl = (origin: string, version: string = DEFAULT_API_VERSION): string =>
  origin
    ? `${trimTrailingSlash(origin)}/api/${version || DEFAULT_API_VERSION}`
    : `/api/${version || DEFAULT_API_VERSION}`

export const detectNetworkingIssue = (
  env: DeploymentEnv,
  pageOrigin?: string
): NetworkingIssue | undefined => {
  return detectBrowserNetworkingIssue({
    surface: "webui-page",
    deploymentMode: env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
    pageOrigin,
    apiOrigin: env.NEXT_PUBLIC_API_URL
  })
}
