const QUICKSTART_MODE = "quickstart"

function isAbsoluteUrl(value) {
  try {
    return new URL(value).origin.length > 0
  } catch {
    return false
  }
}

export function validateNetworkingConfig(env = process.env) {
  const deploymentMode =
    String(env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE || "").trim() || "advanced"
  const internalApiOrigin = String(env.TLDW_INTERNAL_API_ORIGIN || "").trim()
  const publicApiUrl = String(env.NEXT_PUBLIC_API_URL || "").trim()

  if (
    deploymentMode === QUICKSTART_MODE &&
    internalApiOrigin.length === 0
  ) {
    throw new Error(
      "Invalid WebUI networking config: quickstart mode requires TLDW_INTERNAL_API_ORIGIN."
    )
  }

  if (
    deploymentMode === QUICKSTART_MODE &&
    publicApiUrl.length > 0 &&
    isAbsoluteUrl(publicApiUrl)
  ) {
    throw new Error(
      "Invalid WebUI networking config: quickstart mode must not set NEXT_PUBLIC_API_URL to an absolute browser API URL."
    )
  }

  return {
    deploymentMode,
    internalApiOrigin,
    publicApiUrl
  }
}

const isEntrypoint = process.argv[1] === new URL(import.meta.url).pathname

if (isEntrypoint) {
  validateNetworkingConfig(process.env)
}
