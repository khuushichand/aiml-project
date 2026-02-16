export type CharactersDestinationMode =
  | "options-in-place"
  | "options-tab"
  | "web-route"

type BuildCharactersRouteOptions = {
  from: string
  create?: boolean
}

export const buildCharactersRoute = ({
  from,
  create = false
}: BuildCharactersRouteOptions): string => {
  const params = new URLSearchParams({ from })
  if (create) {
    params.set("create", "true")
  }
  return `/characters?${params.toString()}`
}

export const buildCharactersHash = (
  options: BuildCharactersRouteOptions
): string => `#${buildCharactersRoute(options)}`

export const resolveCharactersDestinationMode = ({
  pathname,
  extensionRuntime
}: {
  pathname?: string
  extensionRuntime: boolean
}): CharactersDestinationMode => {
  if ((pathname || "").includes("options.html")) {
    return "options-in-place"
  }
  return extensionRuntime ? "options-tab" : "web-route"
}
