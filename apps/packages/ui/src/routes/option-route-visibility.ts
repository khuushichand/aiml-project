export const HOSTED_VISIBLE_OPTION_PATHS = new Set([
  "/",
  "/chat",
  "/media",
  "/knowledge",
  "/collections"
])

export const isHostedVisibleOptionPath = (path: string) =>
  HOSTED_VISIBLE_OPTION_PATHS.has(path)
