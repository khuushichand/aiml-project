type ChromePermissionsRequest = {
  origins: string[]
}

type ChromePermissions = {
  request?: (
    options: ChromePermissionsRequest,
    callback: (granted: boolean) => void
  ) => void
  contains?: (
    options: ChromePermissionsRequest,
    callback: (granted: boolean) => void
  ) => void
}

export type HostPermissionRequestResult = {
  supported: boolean
  origin?: string
}

export const requestOptionalHostPermission = (
  url?: string | null,
  onResult?: (granted: boolean, origin: string) => void,
  onError?: (error: Error) => void
): HostPermissionRequestResult => {
  const trimmed = typeof url === "string" ? url.trim() : ""
  if (!trimmed) return { supported: false }

  let origin: string
  try {
    origin = new URL(trimmed).origin
  } catch (err) {
    if (onError) {
      onError(err as Error)
    }
    return { supported: false }
  }

  const chromePermissions = (globalThis as { chrome?: { permissions?: ChromePermissions } })
    .chrome?.permissions
  if (!chromePermissions?.request) {
    return { supported: false, origin }
  }

  const origins = [`${origin}/*`]
  const doRequest = () => {
    chromePermissions.request?.({ origins }, (granted) => {
      if (onResult) {
        onResult(granted, origin)
      }
    })
  }

  if (chromePermissions.contains) {
    chromePermissions.contains({ origins }, (granted) => {
      if (granted) {
        if (onResult) onResult(true, origin)
        return
      }
      doRequest()
    })
  } else {
    doRequest()
  }

  return { supported: true, origin }
}
