type TldwClientLike = {
  getConfig: () => Promise<Record<string, unknown> | null>
}

type TldwAuthLike = {
  getCurrentUser: () => Promise<unknown>
}

export const loadTldwClient = async (): Promise<TldwClientLike> => {
  const module = await import("@/services/tldw/TldwApiClient")
  return module.tldwClient as TldwClientLike
}

export const loadTldwAuth = async (): Promise<TldwAuthLike> => {
  const module = await import("@/services/tldw/TldwAuth")
  return module.tldwAuth as TldwAuthLike
}
